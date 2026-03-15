from __future__ import annotations

from pathlib import Path
from typing import Any

from .constants import DEFAULT_WORKTREE_DIR, REPO_ROOT, STATE_DIR
from .services import (
    build_task_profile,
    initial_provider_name,
    provider_preference_default,
    recommended_pool_plan,
    select_task_record_for_worker,
    suggested_branch_name,
    suggested_task_id,
    task_policy_config,
    task_policy_defaults,
    task_policy_rule_matches,
    task_policy_rules,
    task_policy_types,
)
from .utils import dedupe_strings, is_placeholder_path, load_yaml


class RoutingMixin:
    """Methods for task routing, worker resolution, and resource pool planning."""

    def runtime_worker_entries(self) -> list[dict[str, Any]]:
        runtime = load_yaml(STATE_DIR / "agent_runtime.yaml")
        items = runtime.get("workers", [])
        return items if isinstance(items, list) else []

    def reference_workspace_root(self, config: dict[str, Any] | None = None) -> str:
        cfg = config or self.config
        project = cfg.get("project", {}) if isinstance(cfg, dict) else {}
        if not isinstance(project, dict):
            return ""
        return str(project.get("reference_workspace_root") or project.get("paddle_repo_path") or "").strip()

    def reference_inputs(self, config: dict[str, Any] | None = None) -> list[str]:
        cfg = config or self.config
        project = cfg.get("project", {}) if isinstance(cfg, dict) else {}
        if not isinstance(project, dict):
            return []
        configured = project.get("reference_inputs", [])
        values = configured if isinstance(configured, list) else []
        reference_root = self.reference_workspace_root(cfg)
        if reference_root:
            values = [reference_root, *values]
        return dedupe_strings(values)

    def prompt_context_files(self, config: dict[str, Any] | None = None) -> list[str]:
        cfg = config or self.config
        project = cfg.get("project", {}) if isinstance(cfg, dict) else {}
        if not isinstance(project, dict):
            return []
        values = project.get("prompt_context_files", [])
        return dedupe_strings(values if isinstance(values, list) else [])

    def task_policy_config(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        return task_policy_config(config or self.config)

    def provider_preference_default(self, config: dict[str, Any] | None = None) -> list[str]:
        return provider_preference_default(config or self.config)

    def initial_provider_name(self, config: dict[str, Any] | None = None) -> str:
        return initial_provider_name(config or self.config)

    def target_repo_root(self, config: dict[str, Any] | None = None) -> Path:
        cfg = config or self.config
        project = cfg.get("project", {}) if isinstance(cfg, dict) else {}
        if isinstance(project, dict):
            raw_path = str(project.get("local_repo_root") or "").strip()
            if raw_path and not is_placeholder_path(raw_path):
                path = Path(raw_path).expanduser()
                if path.exists():
                    return path
        return REPO_ROOT

    def task_policy_defaults(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        return task_policy_defaults(config or self.config)

    def task_policy_types(self, config: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
        return task_policy_types(config or self.config)

    def task_policy_rules(self, config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return task_policy_rules(config or self.config)

    def task_policy_rule_matches(self, rule: dict[str, Any], worker: dict[str, Any], task: dict[str, Any]) -> bool:
        return task_policy_rule_matches(rule, worker, task)

    def task_record_for_worker(self, worker: dict[str, Any]) -> dict[str, Any]:
        return select_task_record_for_worker(self.backlog_items(), worker)

    def suggested_task_id(self, worker: dict[str, Any]) -> str:
        return suggested_task_id(worker, self.backlog_items())

    def task_profile_for_worker(self, worker: dict[str, Any]) -> dict[str, Any]:
        return build_task_profile(worker, self.backlog_items(), self.config)

    def suggested_branch_name(self, worker: dict[str, Any]) -> str:
        return suggested_branch_name(worker, self.task_profile_for_worker(worker))

    def suggested_test_command(self, worker: dict[str, Any]) -> str:
        profile = self.task_profile_for_worker(worker)
        return str(profile.get("suggested_test_command") or "").strip()

    def recommended_pool_plan(self, worker: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        cfg = config or self.config
        resource_pools = cfg.get("resource_pools", {}) if isinstance(cfg, dict) else {}
        profile = self.task_profile_for_worker(worker)
        return recommended_pool_plan(
            worker=worker,
            resource_pools=resource_pools if isinstance(resource_pools, dict) else {},
            defaults=self.worker_defaults(cfg),
            provider_queue=self.provider_queue(),
            profile=profile,
        )

    def suggested_worktree_path(self, worker: dict[str, Any], config: dict[str, Any] | None = None) -> str:
        cfg = config or self.config
        if not isinstance(cfg, dict) or not isinstance(worker, dict):
            return ""
        project = cfg.get("project", {})
        if not isinstance(project, dict):
            return ""
        agent = str(worker.get("agent", "")).strip()
        if not agent:
            return ""
        local_repo_root = str(project.get("local_repo_root", "")).strip()
        repository_name = str(project.get("repository_name", "")).strip()
        DEFAULT_WORKTREE_DIR.mkdir(parents=True, exist_ok=True)
        if local_repo_root and not is_placeholder_path(local_repo_root):
            base_name = repository_name or Path(local_repo_root).expanduser().name or "workspace"
        else:
            base_name = repository_name or "workspace"
        safe_base_name = "_".join(part for part in base_name.replace("-", "_").split("_") if part) or "workspace"
        return str((DEFAULT_WORKTREE_DIR / f"{safe_base_name}_{agent.lower()}").resolve())

    def merge_worker_config(self, worker: dict[str, Any], defaults: dict[str, Any] | None = None) -> dict[str, Any]:
        if not isinstance(worker, dict):
            return {}

        merged = dict(worker)
        worker_defaults = defaults if isinstance(defaults, dict) else self.worker_defaults()

        inheritable_fields = (
            "resource_pool",
            "environment_type",
            "environment_path",
            "sync_command",
            "test_command",
            "submit_strategy",
        )
        for field_name in inheritable_fields:
            raw_value = merged.get(field_name)
            if raw_value in {None, ""} and worker_defaults.get(field_name) not in {None, ""}:
                merged[field_name] = worker_defaults[field_name]

        raw_queue = merged.get("resource_pool_queue")
        default_queue = worker_defaults.get("resource_pool_queue")
        if (not isinstance(raw_queue, list) or not raw_queue) and isinstance(default_queue, list) and default_queue:
            merged["resource_pool_queue"] = list(default_queue)

        raw_worktree_path = str(merged.get("worktree_path", "")).strip()
        if not raw_worktree_path:
            suggested_path = self.suggested_worktree_path(merged)
            if suggested_path:
                merged["worktree_path"] = suggested_path

        raw_task_id = str(merged.get("task_id", "")).strip()
        if not raw_task_id:
            suggested_task_id = self.suggested_task_id(merged)
            if suggested_task_id:
                merged["task_id"] = suggested_task_id

        raw_branch = str(merged.get("branch", "")).strip()
        if not raw_branch:
            suggested_branch = self.suggested_branch_name(merged)
            if suggested_branch:
                merged["branch"] = suggested_branch

        resource_plan = self.recommended_pool_plan(merged)
        raw_resource_pool = str(worker.get("resource_pool", "")).strip()
        raw_resource_pool_queue = worker.get("resource_pool_queue")
        if not raw_resource_pool and resource_plan.get("locked_pool"):
            merged["resource_pool"] = resource_plan["locked_pool"]
        if (
            (not isinstance(raw_resource_pool_queue, list) or not raw_resource_pool_queue)
            and not str(merged.get("resource_pool", "")).strip()
            and resource_plan.get("recommended_queue")
        ):
            merged["resource_pool_queue"] = list(resource_plan["recommended_queue"])

        raw_test_command = str(worker.get("test_command", "")).strip()
        if not raw_test_command:
            suggested_test_command = self.suggested_test_command(merged)
            if suggested_test_command:
                merged["test_command"] = suggested_test_command

        default_identity = worker_defaults.get("git_identity")
        raw_identity = merged.get("git_identity")
        if isinstance(default_identity, dict) or isinstance(raw_identity, dict):
            merged_identity: dict[str, str] = {}
            for key in ("name", "email"):
                worker_value = str((raw_identity or {}).get(key, "")).strip() if isinstance(raw_identity, dict) else ""
                default_value = (
                    str((default_identity or {}).get(key, "")).strip() if isinstance(default_identity, dict) else ""
                )
                if worker_value:
                    merged_identity[key] = worker_value
                elif default_value:
                    merged_identity[key] = default_value
            if merged_identity:
                merged["git_identity"] = merged_identity

        return merged

    def resolved_worker_plan(self, worker: dict[str, Any]) -> dict[str, Any]:
        pool_plan = self.recommended_pool_plan(worker)
        profile = self.task_profile_for_worker(worker)
        return {
            "agent": worker.get("agent", ""),
            "task_id": worker.get("task_id", ""),
            "task_title": profile.get("title", ""),
            "task_type": profile.get("task_type", "default"),
            "task_category": profile.get("task_type", "default"),
            "preferred_providers": profile.get("preferred_providers", []),
            "branch": worker.get("branch", ""),
            "worktree_path": worker.get("worktree_path", ""),
            "resource_pool": worker.get("resource_pool", ""),
            "resource_pool_queue": worker.get("resource_pool_queue", []),
            "recommended_pool": pool_plan.get("recommended_pool", ""),
            "locked_pool": pool_plan.get("locked_pool", ""),
            "pool_reason": pool_plan.get("reason", ""),
            "test_command": worker.get("test_command", ""),
            "suggested_test_command": self.suggested_test_command(worker),
        }
