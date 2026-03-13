from __future__ import annotations

import os
import shlex
import shutil
import subprocess
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
from .network import LaunchPolicy
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
        api_env_name = provider.get("api_key_env_name")
        configured_value = str(pool.get("api_key", ""))
        if configured_value and configured_value != "replace_me_or_use_api_key_env":
            return configured_value
        if api_env_name:
            return str(os.environ.get(api_env_name, ""))
        return ""

    def provider_auth_mode(self, provider: dict[str, Any]) -> str:
        raw_mode = str(provider.get("auth_mode") or "").strip().lower()
        if raw_mode:
            return raw_mode
        if bool(provider.get("session_auth")):
            return "session"
        return "api_key"

    def provider_probe_timeout(self, provider: dict[str, Any], pool: dict[str, Any]) -> float:
        raw_timeout = pool.get("session_probe_timeout_sec", provider.get("session_probe_timeout_sec", 3.0))
        try:
            timeout = float(raw_timeout)
        except (TypeError, ValueError):
            return 3.0
        return min(max(timeout, 0.2), 30.0)

    def provider_probe_values(
        self,
        pool_name: str,
        provider_name: str,
        pool: dict[str, Any],
        binary: str,
        binary_path: str,
    ) -> dict[str, str]:
        return {
            "binary": binary,
            "binary_path": binary_path,
            "model": str(pool.get("model", "")),
            "provider": provider_name,
            "resource_pool": pool_name,
        }

    def provider_auth_status(
        self,
        pool_name: str,
        provider_name: str,
        provider: dict[str, Any],
        pool: dict[str, Any],
        binary: str,
        binary_path: str,
    ) -> tuple[str, bool, str, bool]:
        auth_mode = self.provider_auth_mode(provider)
        if auth_mode == "session":
            session_probe = pool.get("session_probe_command") or provider.get("session_probe_command")
            if session_probe:
                try:
                    probe_command = format_command(
                        session_probe,
                        self.provider_probe_values(pool_name, provider_name, pool, binary, binary_path),
                    )
                except Exception as exc:
                    return auth_mode, False, f"session probe formatting failed for pool {pool_name}: {exc}", False
                try:
                    result = run_command(probe_command, timeout=self.provider_probe_timeout(provider, pool))
                except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
                    return auth_mode, False, f"session probe failed for pool {pool_name}: {exc}", False
                output = result.stdout.strip() or result.stderr.strip()
                if result.returncode == 0:
                    detail = output or f"session ready for pool {pool_name}"
                    return auth_mode, True, detail, False
                detail = output or f"session auth unavailable for pool {pool_name}"
                return auth_mode, False, detail, False
            return auth_mode, True, f"session auth enabled for pool {pool_name}", False

        api_env_name = str(provider.get("api_key_env_name") or "").strip()
        api_key = self.configured_api_key(provider, pool)
        if api_key:
            return (
                auth_mode,
                True,
                (f"api key available via {api_env_name}" if api_env_name else "api key configured"),
                True,
            )
        if api_env_name:
            return auth_mode, False, f"api key missing for pool {pool_name}; expected env {api_env_name}", False
        return auth_mode, False, f"api key missing for pool {pool_name}", False

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

    def evaluate_resource_pool(self, pool_name: str) -> dict[str, Any]:
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
        active_workers = len(pool_usage["running_agents"])
        work_quality = self.score_work_quality(stats, active_workers)
        stats["last_work_quality"] = work_quality

        connection_quality = 1.0 if launch_ready else 0.0
        if launch_ready and latency_ms < 25:
            connection_quality = 1.0
        elif launch_ready and latency_ms < 100:
            connection_quality = 0.9
        elif launch_ready:
            connection_quality = 0.8

        base_priority = int(pool.get("priority", 100))
        score = round(base_priority * 100 + connection_quality * 30 + work_quality * 70, 3)

        failure_detail = stats.get("last_failure", "")
        if not binary_path:
            failure_detail = f"provider binary missing for pool {pool_name}: {binary or 'unassigned'}"
        elif not auth_ready:
            failure_detail = auth_detail

        return {
            "resource_pool": pool_name,
            "provider": provider_name,
            "model": pool.get("model", "unassigned"),
            "priority": base_priority,
            "binary": binary or "unassigned",
            "binary_found": bool(binary_path),
            "recursion_guard": recursion_guard,
            "launch_wrapper": launch_wrapper,
            "auth_mode": auth_mode,
            "auth_ready": auth_ready,
            "auth_detail": auth_detail,
            "api_key_present": has_api_key,
            "launch_ready": launch_ready,
            "connection_quality": connection_quality,
            "work_quality": work_quality,
            "score": score,
            "latency_ms": latency_ms,
            "active_workers": active_workers,
            "running_agents": pool_usage["running_agents"],
            "usage": pool_usage["usage"],
            "progress_pct": pool_usage["progress_pct"],
            "last_activity_at": pool_usage["last_activity_at"],
            "last_failure": failure_detail,
        }

    def provider_queue(self) -> list[dict[str, Any]]:
        evaluations = [self.evaluate_resource_pool(pool_name) for pool_name in self.resource_pools]
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

    def launch_policy_state(self) -> dict[str, Any]:
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
        if worker.get("resource_pool"):
            return [str(worker["resource_pool"])]
        configured_queue = worker.get("resource_pool_queue")
        if isinstance(configured_queue, list) and configured_queue:
            return configured_queue
        return [item["resource_pool"] for item in self.provider_queue()]

    def best_pool_for_provider(self, provider_name: str) -> tuple[str, dict[str, Any]]:
        ordered_candidates = [item for item in self.provider_queue() if item["provider"] == provider_name]
        if not ordered_candidates:
            raise RuntimeError(f"no eligible resource pool candidates exist for provider {provider_name}")
        for item in ordered_candidates:
            if item["launch_ready"]:
                return item["resource_pool"], item
        return ordered_candidates[0]["resource_pool"], ordered_candidates[0]

    def best_pool_for_worker(self, worker: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        queue = self.provider_queue()
        evaluations = {item["resource_pool"]: item for item in queue}
        ordered_candidates = []
        for pool_name in self.candidate_pools_for_worker(worker):
            if pool_name in evaluations:
                ordered_candidates.append(evaluations[pool_name])
        ordered_candidates.sort(key=lambda item: (-item["score"], -item["priority"], item["resource_pool"]))
        for item in ordered_candidates:
            if item["launch_ready"]:
                return item["resource_pool"], item
        if ordered_candidates:
            return ordered_candidates[0]["resource_pool"], ordered_candidates[0]
        raise RuntimeError(f"worker {worker['agent']} has no eligible resource pool candidates")

    def resolve_pool_for_launch(self, worker: dict[str, Any], policy: LaunchPolicy) -> tuple[str, dict[str, Any]]:
        if policy.strategy == "elastic":
            return self.best_pool_for_worker(worker)
        provider_name = policy.provider or self.initial_provider_name()
        return self.best_pool_for_provider(provider_name)
