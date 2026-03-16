from __future__ import annotations

import shlex
import shutil
import time
from typing import Any

from .constants import (
    CONTROL_PLANE_ALLOW_NESTED_ENV,
    CONTROL_PLANE_GUARD_MODE_ENV,
    CONTROL_PLANE_RECURSION_POLICY_ENV,
    CONTROL_PLANE_WORKER_AGENT_ENV,
    CONTROL_PLANE_WORKER_CONTEXT_ENV,
    CONTROL_PLANE_WRAPPED_PROVIDER_ENV,
    DEFAULT_INITIAL_PROVIDER,
    LAUNCH_STRATEGIES,
    PROVIDER_AUTH_MODES,
    STATE_DIR,
    WRAPPER_DIR,
)
from .contracts import LaunchPolicyState, ProviderQueueItem
from .network import LaunchPolicy
from .services import (
    best_pool_for_provider,
    best_pool_for_worker,
    configured_api_key,
    provider_auth_mode,
    provider_auth_status,
    provider_probe_timeout,
    provider_probe_values,
    provider_queue_item,
    queue_pool_candidates,
)
from .utils import format_command, load_yaml, run_command, slugify


class ProviderMixin:
    """Methods for provider authentication, probing, quality scoring, pool evaluation, and launch-policy resolution."""

    def default_provider_stat_entry(self) -> dict[str, Any]:
        return {
            "launch_successes": 0,
            "launch_failures": 0,
            "clean_exits": 0,
            "failed_exits": 0,
            "last_failure": "",
            "last_latency_ms": None,
            "last_probe_ok": False,
            "last_work_quality": 0.0,
        }

    def configured_api_key(self, provider: dict[str, Any], pool: dict[str, Any]) -> str:
        return configured_api_key(provider, pool)

    def provider_auth_mode(self, provider: dict[str, Any]) -> str:
        return provider_auth_mode(provider)

    def provider_probe_timeout(self, provider: dict[str, Any], pool: dict[str, Any]) -> float:
        return provider_probe_timeout(provider, pool)

    def provider_probe_values(
        self,
        pool_name: str,
        provider_name: str,
        pool: dict[str, Any],
        binary: str,
        binary_path: str,
    ) -> dict[str, str]:
        return provider_probe_values(pool_name, provider_name, pool, binary, binary_path)

    def provider_auth_status(
        self,
        pool_name: str,
        provider_name: str,
        provider: dict[str, Any],
        pool: dict[str, Any],
        binary: str,
        binary_path: str,
    ) -> tuple[str, bool, str, bool]:
        return provider_auth_status(
            pool_name=pool_name,
            provider_name=provider_name,
            provider=provider,
            pool=pool,
            binary=binary,
            binary_path=binary_path,
            format_command_fn=format_command,
            run_command_fn=run_command,
        )

    def provider_uses_exec_wrapper(self, provider_name: str, provider: dict[str, Any]) -> bool:
        configured = provider.get("single_layer_wrapper")
        if configured is not None:
            return bool(configured)
        return provider_name == "ducc"

    def provider_recursion_guard_mode(self, provider_name: str, provider: dict[str, Any]) -> str:
        return "env+exec-wrapper" if self.provider_uses_exec_wrapper(provider_name, provider) else "env-only"

    def provider_wrapper_path(self, provider_name: str):
        return WRAPPER_DIR / f"{slugify(provider_name)}_single_layer.sh"

    def ensure_provider_exec_wrapper(self, provider_name: str):
        WRAPPER_DIR.mkdir(parents=True, exist_ok=True)
        wrapper_path = self.provider_wrapper_path(provider_name)
        wrapper_text = "\n".join(
            [
                "#!/bin/sh",
                "set -eu",
                f"unset {CONTROL_PLANE_ALLOW_NESTED_ENV} 2>/dev/null || true",
                "unset CLAUDECODE 2>/dev/null || true",
                f'export {CONTROL_PLANE_WORKER_CONTEXT_ENV}="${{{CONTROL_PLANE_WORKER_CONTEXT_ENV}:-1}}"',
                f'export {CONTROL_PLANE_RECURSION_POLICY_ENV}="${{{CONTROL_PLANE_RECURSION_POLICY_ENV}:-forbid-nested-control-plane}}"',
                f'export {CONTROL_PLANE_GUARD_MODE_ENV}="${{{CONTROL_PLANE_GUARD_MODE_ENV}:-env+exec-wrapper}}"',
                f'export {CONTROL_PLANE_WRAPPED_PROVIDER_ENV}="{provider_name}"',
                'exec "$@"',
                "",
            ]
        )
        if not wrapper_path.exists() or wrapper_path.read_text(encoding="utf-8") != wrapper_text:
            wrapper_path.write_text(wrapper_text, encoding="utf-8")
            wrapper_path.chmod(0o755)
        return wrapper_path

    def guarded_worker_env(
        self, worker: dict[str, Any], provider_name: str, provider: dict[str, Any]
    ) -> dict[str, str]:
        recursion_guard = self.provider_recursion_guard_mode(provider_name, provider)
        return {
            CONTROL_PLANE_WORKER_CONTEXT_ENV: "1",
            CONTROL_PLANE_WORKER_AGENT_ENV: str(worker["agent"]),
            CONTROL_PLANE_RECURSION_POLICY_ENV: "forbid-nested-control-plane",
            CONTROL_PLANE_GUARD_MODE_ENV: recursion_guard,
            CONTROL_PLANE_WRAPPED_PROVIDER_ENV: provider_name,
        }

    def score_work_quality(self, stats: dict[str, Any], active_workers: int) -> float:
        successes = int(stats.get("launch_successes", 0))
        launch_failures = int(stats.get("launch_failures", 0))
        clean_exits = int(stats.get("clean_exits", 0))
        failed_exits = int(stats.get("failed_exits", 0))
        numerator = successes + clean_exits + active_workers
        denominator = numerator + launch_failures + failed_exits + 1
        return round(numerator / denominator, 3)

    def evaluate_resource_pool(self, pool_name: str) -> ProviderQueueItem:
        pool = self.resource_pools[pool_name]
        provider_name = str(pool.get("provider", "unassigned"))
        provider = self.providers.get(provider_name, {})
        recursion_guard = self.provider_recursion_guard_mode(provider_name, provider)
        launch_wrapper = (
            str(self.provider_wrapper_path(provider_name))
            if self.provider_uses_exec_wrapper(provider_name, provider)
            else ""
        )
        stats = self.provider_stats.setdefault(
            pool_name,
            {
                "launch_successes": 0,
                "launch_failures": 0,
                "clean_exits": 0,
                "failed_exits": 0,
                "last_failure": "",
                "last_latency_ms": None,
                "last_probe_ok": False,
                "last_work_quality": 0.0,
            },
        )
        start = time.perf_counter()
        binary = None
        template = provider.get("command_template")
        if isinstance(template, str):
            parts = shlex.split(template)
            binary = parts[0] if parts else None
        elif isinstance(template, list) and template:
            binary = str(template[0])
        binary_path = shutil.which(binary) if binary else None
        auth_mode, auth_ready, auth_detail, has_api_key = self.provider_auth_status(
            pool_name,
            provider_name,
            provider,
            pool,
            str(binary or ""),
            str(binary_path or ""),
        )
        launch_ready = bool(binary_path) and auth_ready
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        stats["last_latency_ms"] = latency_ms
        stats["last_probe_ok"] = launch_ready

        pool_usage = self.pool_usage_summary(pool_name)
        work_quality = self.score_work_quality(stats, len(pool_usage["running_agents"]))
        stats["last_work_quality"] = work_quality

        return provider_queue_item(
            pool_name=pool_name,
            provider_name=provider_name,
            model=str(pool.get("model", "unassigned")),
            priority=int(pool.get("priority", 100)),
            binary=str(binary or "unassigned"),
            binary_found=bool(binary_path),
            recursion_guard=recursion_guard,
            launch_wrapper=launch_wrapper,
            auth_mode=auth_mode,
            auth_ready=auth_ready,
            auth_detail=auth_detail,
            api_key_present=has_api_key,
            latency_ms=latency_ms,
            work_quality=work_quality,
            pool_usage=pool_usage,
            last_failure=str(stats.get("last_failure", "")),
        )

    def provider_queue(self) -> list[ProviderQueueItem]:
        evaluations: list[ProviderQueueItem] = [self.evaluate_resource_pool(pool_name) for pool_name in self.resource_pools]
        return sorted(evaluations, key=lambda item: (-item["score"], -item["priority"], item["resource_pool"]))

    def has_launch_history(self) -> bool:
        if self.processes:
            return True
        worker_agents = {str(worker.get("agent", "")).strip() for worker in self.workers if worker.get("agent")}
        if not worker_agents:
            return False
        runtime_workers = load_yaml(STATE_DIR / "agent_runtime.yaml").get("workers", [])
        for entry in runtime_workers:
            agent = str(entry.get("agent", "")).strip()
            if agent not in worker_agents:
                continue
            status = str(entry.get("status", "")).strip()
            if status and status not in {"not_started", "not-started", "unassigned"}:
                return True
        heartbeat_workers = load_yaml(STATE_DIR / "heartbeats.yaml").get("agents", [])
        for entry in heartbeat_workers:
            agent = str(entry.get("agent", "")).strip()
            if agent not in worker_agents:
                continue
            state = str(entry.get("state", "")).strip()
            last_seen = str(entry.get("last_seen", "")).strip()
            if state and state not in {"not_started", "not-started"}:
                return True
            if last_seen and last_seen.lower() != "none":
                return True
        return False

    def default_launch_policy(self) -> LaunchPolicy:
        if not self.has_launch_history():
            return LaunchPolicy(strategy="initial_provider", provider=self.initial_provider_name())
        return LaunchPolicy(strategy="elastic")

    def parse_launch_policy(self, payload: dict[str, Any]) -> LaunchPolicy:
        default_policy = self.default_launch_policy()
        raw_strategy = str(payload.get("strategy") or default_policy.strategy).strip() or default_policy.strategy
        if raw_strategy == "initial_copilot":
            raw_strategy = "initial_provider"
        if raw_strategy not in LAUNCH_STRATEGIES:
            raise ValueError(f"unknown launch strategy: {raw_strategy}")

        provider = str(payload.get("provider") or "").strip() or None
        model = str(payload.get("model") or "").strip() or None

        if raw_strategy == "initial_provider":
            provider = self.initial_provider_name()
        elif raw_strategy == "selected_model":
            if not provider:
                raise ValueError("provider is required when strategy is selected_model")
            if provider not in self.providers:
                raise ValueError(f"unknown provider for selected_model: {provider}")
            if not model:
                raise ValueError("model is required when strategy is selected_model")

        if provider and provider not in self.providers:
            raise ValueError(f"unknown provider: {provider}")
        return LaunchPolicy(strategy=raw_strategy, provider=provider, model=model)

    def launch_policy_state(self) -> LaunchPolicyState:
        default_policy = self.default_launch_policy()
        return {
            "default_strategy": default_policy.strategy,
            "default_provider": default_policy.provider,
            "default_model": default_policy.model,
            "available_strategies": sorted(LAUNCH_STRATEGIES),
            "available_providers": sorted(self.providers.keys()),
            "initial_provider": self.initial_provider_name(),
            "has_launch_history": self.has_launch_history(),
        }

    def candidate_pools_for_worker(self, worker: dict[str, Any]) -> list[str]:
        return queue_pool_candidates(worker, self.provider_queue())

    def best_pool_for_provider(self, provider_name: str) -> tuple[str, dict[str, Any]]:
        return best_pool_for_provider(provider_name, self.provider_queue())

    def best_pool_for_worker(self, worker: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        return best_pool_for_worker(worker, self.provider_queue())

    def resolve_pool_for_launch(self, worker: dict[str, Any], policy: LaunchPolicy) -> tuple[str, dict[str, Any]]:
        if policy.strategy == "elastic":
            return self.best_pool_for_worker(worker)
        provider_name = policy.provider or self.initial_provider_name()
        return self.best_pool_for_provider(provider_name)
