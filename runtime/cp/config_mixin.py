from __future__ import annotations

import copy
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit("PyYAML is required. Run `uv sync` or install PyYAML>=6.0.2.") from exc

from .constants import (
    CONFIG_SECTIONS,
    CONFIG_TEMPLATE_PATH,
    PROVIDER_AUTH_MODES,
    REPO_ROOT,
)
from .utils import (
    dedupe_strings,
    dump_yaml,
    is_placeholder_path,
    host_reachable_via_ping,
    load_yaml,
    now_iso,
    path_exists_via_ls,
    yaml_text,
)


class ConfigMixin:
    """Methods for configuration validation, loading, saving, and repair."""

    def worker_defaults(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        cfg = config or self.config
        if not isinstance(cfg, dict):
            return {}
        defaults = cfg.get("worker_defaults", {})
        return defaults if isinstance(defaults, dict) else {}

    def repair_config_resource_pool_references(self, config: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        if not isinstance(config, dict):
            return config, []

        repaired = copy.deepcopy(config)
        repairs: list[str] = []
        providers = repaired.get("providers", {})
        available_providers = set(providers.keys()) if isinstance(providers, dict) else set()
        resource_pools = repaired.get("resource_pools", {})
        available_pools = set(resource_pools.keys()) if isinstance(resource_pools, dict) else set()

        project = repaired.get("project")
        if isinstance(project, dict):
            initial_provider = str(project.get("initial_provider", "")).strip()
            if initial_provider and initial_provider not in available_providers:
                project.pop("initial_provider", None)
                repairs.append(f"project.initial_provider cleared unknown provider {initial_provider}")

        task_policies = repaired.get("task_policies")
        if isinstance(task_policies, dict):
            defaults = task_policies.get("defaults")
            if isinstance(defaults, dict):
                preferred = defaults.get("preferred_providers")
                if isinstance(preferred, list):
                    filtered = [str(item) for item in preferred if str(item) in available_providers]
                    if filtered != [str(item) for item in preferred]:
                        repairs.append("task_policies.defaults.preferred_providers removed unknown providers")
                    if filtered:
                        defaults["preferred_providers"] = filtered
                    else:
                        defaults.pop("preferred_providers", None)
            types = task_policies.get("types")
            if isinstance(types, dict):
                for task_type, entry in types.items():
                    if not isinstance(entry, dict):
                        continue
                    preferred = entry.get("preferred_providers")
                    if isinstance(preferred, list):
                        filtered = [str(item) for item in preferred if str(item) in available_providers]
                        if filtered != [str(item) for item in preferred]:
                            repairs.append(
                                f"task_policies.types.{task_type}.preferred_providers removed unknown providers"
                            )
                        if filtered:
                            entry["preferred_providers"] = filtered
                        else:
                            entry.pop("preferred_providers", None)

        worker_defaults = repaired.get("worker_defaults")
        if isinstance(worker_defaults, dict):
            default_pool = str(worker_defaults.get("resource_pool", "")).strip()
            if default_pool and default_pool not in available_pools:
                worker_defaults.pop("resource_pool", None)
                repairs.append(f"worker_defaults.resource_pool cleared unknown pool {default_pool}")
            default_queue = worker_defaults.get("resource_pool_queue")
            if isinstance(default_queue, list):
                filtered_queue = [str(item) for item in default_queue if str(item) in available_pools]
                if filtered_queue != [str(item) for item in default_queue]:
                    repairs.append("worker_defaults.resource_pool_queue removed unknown pools")
                if filtered_queue:
                    worker_defaults["resource_pool_queue"] = filtered_queue
                else:
                    worker_defaults.pop("resource_pool_queue", None)

        workers = repaired.get("workers")
        if isinstance(workers, list):
            for index, worker in enumerate(workers):
                if not isinstance(worker, dict):
                    continue
                pool_name = str(worker.get("resource_pool", "")).strip()
                if pool_name and pool_name not in available_pools:
                    worker.pop("resource_pool", None)
                    repairs.append(f"workers[{index}].resource_pool cleared unknown pool {pool_name}")
                pool_queue = worker.get("resource_pool_queue")
                if isinstance(pool_queue, list):
                    filtered_queue = [str(item) for item in pool_queue if str(item) in available_pools]
                    if filtered_queue != [str(item) for item in pool_queue]:
                        repairs.append(f"workers[{index}].resource_pool_queue removed unknown pools")
                    if filtered_queue:
                        worker["resource_pool_queue"] = filtered_queue
                    else:
                        worker.pop("resource_pool_queue", None)

        return repaired, repairs

    def field_matches_section(self, field: str, section: str) -> bool:
        if section == "project":
            return (
                field.startswith("project.")
                and not field.startswith("project.integration_branch")
                and not field.startswith("project.manager_git_identity")
            )
        if section == "merge_policy":
            return field.startswith("project.integration_branch") or field.startswith("project.manager_git_identity")
        if section == "resource_pools":
            return field.startswith("resource_pools.")
        if section == "worker_defaults":
            return field.startswith("worker_defaults.")
        if section == "workers":
            return field.startswith("workers[")
        return False

    def filter_section_issue_text(self, values: list[str], section: str) -> list[str]:
        if section == "project":
            keywords = (
                "project.repository_name",
                "project.local_repo_root",
                "project.reference_workspace_root",
                "project.dashboard",
            )
        elif section == "merge_policy":
            keywords = ("project.integration_branch", "project.manager_git_identity", "merge")
        elif section == "resource_pools":
            keywords = ("resource_pools.", "provider", "pool")
        elif section == "worker_defaults":
            keywords = ("worker_defaults",)
        elif section == "workers":
            keywords = (
                "worker ",
                "workers[",
                "worktree_path",
                "resource_pool_queue",
                "branch",
                "submit_strategy",
                "test_command",
            )
        else:
            return values
        return [value for value in values if any(keyword in value for keyword in keywords)]

    def config_for_section(
        self, section: str, value: Any, base_config: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if section not in CONFIG_SECTIONS:
            raise ValueError(f"unknown config section: {section}")
        current = copy.deepcopy(base_config or self.config or {})
        if not isinstance(current, dict):
            current = {}

        if section == "project":
            project = current.get("project", {})
            if not isinstance(project, dict):
                project = {}
            payload = value if isinstance(value, dict) else {}
            reference_workspace_root = payload.get(
                "reference_workspace_root",
                payload.get(
                    "paddle_repo_path",
                    project.get("reference_workspace_root") or project.get("paddle_repo_path"),
                ),
            )
            project.update(
                {
                    "repository_name": payload.get("repository_name", project.get("repository_name")),
                    "local_repo_root": payload.get("local_repo_root", project.get("local_repo_root")),
                    "reference_workspace_root": reference_workspace_root,
                    "dashboard": payload.get("dashboard", project.get("dashboard", {})),
                }
            )
            project.pop("paddle_repo_path", None)
            current["project"] = project
            return current

        if section == "merge_policy":
            project = current.get("project", {})
            if not isinstance(project, dict):
                project = {}
            payload = value if isinstance(value, dict) else {}
            project.update(
                {
                    "integration_branch": payload.get("integration_branch", project.get("integration_branch")),
                    "manager_git_identity": payload.get(
                        "manager_git_identity", project.get("manager_git_identity", {})
                    ),
                }
            )
            current["project"] = project
            return current

        current[section] = copy.deepcopy(value)
        return current

    def config_validation_issues(self, config: dict[str, Any] | None = None) -> list[dict[str, str]]:
        cfg = config or self.config
        issues: list[dict[str, str]] = []

        def add_issue(field: str, message: str) -> None:
            issues.append({"field": field, "message": message})

        if not isinstance(cfg, dict):
            add_issue("config", "top-level config must be a YAML mapping")
            return issues

        project = cfg.get("project", {})
        providers = cfg.get("providers", {})
        resource_pools = cfg.get("resource_pools", {})
        worker_defaults = cfg.get("worker_defaults", {})
        workers = cfg.get("workers", [])

        if not isinstance(project, dict):
            add_issue("project", "project must be a mapping")
            project = {}
        if not isinstance(providers, dict):
            add_issue("providers", "providers must be a mapping")
            providers = {}
        if not isinstance(resource_pools, dict):
            add_issue("resource_pools", "resource_pools must be a mapping")
            resource_pools = {}
        if not isinstance(worker_defaults, dict):
            add_issue("worker_defaults", "worker_defaults must be a mapping")
            worker_defaults = {}
        if not isinstance(workers, list):
            add_issue("workers", "workers must be a list")
            workers = []

        repository_name = str(project.get("repository_name", "")).strip()
        if not repository_name:
            add_issue("project.repository_name", "repository name is required")

        for field_name in ("local_repo_root",):
            raw_value = str(project.get(field_name, "")).strip()
            field_path = f"project.{field_name}"
            if not raw_value:
                add_issue(field_path, f"{field_name} is required")
            elif is_placeholder_path(raw_value):
                add_issue(field_path, f"{field_name} must be replaced with a real path")
            elif not path_exists_via_ls(raw_value):
                add_issue(field_path, f"{field_name} does not exist: {raw_value}")

        reference_workspace_root = self.reference_workspace_root(cfg)
        if reference_workspace_root:
            if is_placeholder_path(reference_workspace_root):
                add_issue(
                    "project.reference_workspace_root",
                    "reference_workspace_root must be replaced with a real path",
                )
            elif not path_exists_via_ls(reference_workspace_root):
                add_issue(
                    "project.reference_workspace_root",
                    f"reference_workspace_root does not exist: {reference_workspace_root}",
                )

        dashboard = project.get("dashboard", {})
        if not isinstance(dashboard, dict):
            add_issue("project.dashboard", "dashboard must be a mapping")
            dashboard = {}
        host = str(dashboard.get("host", "")).strip()

        if not host:
            add_issue("project.dashboard.host", "dashboard host is required")
        elif not host_reachable_via_ping(host):
            add_issue("project.dashboard.host", f"dashboard host is not reachable via ping: {host}")
        port = dashboard.get("port")
        if not isinstance(port, int) or not (1 <= int(port) <= 65535):
            add_issue("project.dashboard.port", "dashboard port must be an integer between 1 and 65535")

        task_policies = self.task_policy_config(cfg)
        if task_policies and not isinstance(task_policies, dict):
            add_issue("task_policies", "task_policies must be a mapping")
        known_task_types = {self.task_policy_defaults(cfg)["task_type"], *self.task_policy_types(cfg).keys()}
        for task_type, entry in self.task_policy_types(cfg).items():
            for provider_name in entry.get("preferred_providers", []):
                if provider_name not in providers:
                    add_issue(
                        f"task_policies.types.{task_type}.preferred_providers",
                        f"unknown provider in preferred_providers: {provider_name}",
                    )
        for rule_index, rule in enumerate(self.task_policy_rules(cfg)):
            task_type = str(rule.get("task_type") or "").strip()
            if not task_type:
                add_issue(f"task_policies.rules[{rule_index}].task_type", "task_type is required")
            elif task_type not in known_task_types:
                add_issue(
                    f"task_policies.rules[{rule_index}].task_type",
                    f"task_type references unknown policy type: {task_type}",
                )

        seen_agents: set[str] = set()
        seen_branches: set[str] = set()
        seen_worktrees: set[str] = set()

        for pool_name, pool in resource_pools.items():
            if not isinstance(pool, dict):
                add_issue(f"resource_pools.{pool_name}", "resource pool must be a mapping")
                continue
            provider_name = str(pool.get("provider", "")).strip()
            if not provider_name:
                add_issue(f"resource_pools.{pool_name}.provider", "provider is required")
            elif provider_name not in providers:
                add_issue(f"resource_pools.{pool_name}.provider", f"unknown provider: {provider_name}")
            if not str(pool.get("model", "")).strip():
                add_issue(f"resource_pools.{pool_name}.model", "model is required")
            priority = pool.get("priority", 100)
            if not isinstance(priority, int):
                add_issue(f"resource_pools.{pool_name}.priority", "priority must be an integer")

        default_pool_name = str(worker_defaults.get("resource_pool", "")).strip()
        if default_pool_name and default_pool_name not in resource_pools:
            add_issue("worker_defaults.resource_pool", f"unknown resource pool: {default_pool_name}")
        default_pool_queue = worker_defaults.get("resource_pool_queue", [])
        if default_pool_queue and not isinstance(default_pool_queue, list):
            add_issue("worker_defaults.resource_pool_queue", "resource_pool_queue must be a list")
        if isinstance(default_pool_queue, list):
            for queue_index, candidate_pool in enumerate(default_pool_queue):
                if str(candidate_pool) not in resource_pools:
                    add_issue(
                        f"worker_defaults.resource_pool_queue[{queue_index}]",
                        f"unknown resource pool: {candidate_pool}",
                    )

        default_environment_type = str(worker_defaults.get("environment_type", "uv")).strip() or "uv"
        default_environment_path = str(worker_defaults.get("environment_path", "")).strip()
        if default_environment_type == "venv":
            if not default_environment_path:
                add_issue("worker_defaults.environment_path", "environment path is required when environment_type is venv")
            elif is_placeholder_path(default_environment_path):
                add_issue("worker_defaults.environment_path", "environment path must be replaced with a real path")
            elif not path_exists_via_ls(default_environment_path):
                add_issue(
                    "worker_defaults.environment_path",
                    f"environment path does not exist: {default_environment_path}",
                )
        elif default_environment_type not in {"none", "uv"} and default_environment_path and is_placeholder_path(default_environment_path):
            add_issue("worker_defaults.environment_path", "environment path must be replaced with a real path")

        default_git_identity = worker_defaults.get("git_identity")
        if default_git_identity is not None:
            if not isinstance(default_git_identity, dict):
                add_issue("worker_defaults.git_identity", "git_identity must be a mapping")
            else:
                if default_git_identity.get("name") and not str(default_git_identity.get("email", "")).strip():
                    add_issue("worker_defaults.git_identity.email", "email is required when git_identity.name is set")
                if default_git_identity.get("email") and not str(default_git_identity.get("name", "")).strip():
                    add_issue("worker_defaults.git_identity.name", "name is required when git_identity.email is set")

        for worker_index, worker in enumerate(workers):
            field_root = f"workers[{worker_index}]"
            if not isinstance(worker, dict):
                add_issue(field_root, "worker must be a mapping")
                continue
            effective_worker = self.merge_worker_config(worker, worker_defaults)
            agent = str(worker.get("agent", "")).strip()
            if not agent:
                add_issue(f"{field_root}.agent", "agent is required")
            elif agent in seen_agents:
                add_issue(f"{field_root}.agent", f"duplicate agent: {agent}")
            else:
                seen_agents.add(agent)

            branch = str(effective_worker.get("branch", "")).strip()
            if not branch:
                add_issue(f"{field_root}.branch", "branch is required")
            elif branch in seen_branches:
                add_issue(f"{field_root}.branch", f"duplicate branch: {branch}")
            else:
                seen_branches.add(branch)

            worktree_path = str(effective_worker.get("worktree_path", "")).strip()
            if not worktree_path:
                add_issue(f"{field_root}.worktree_path", "worktree path is required")
            elif is_placeholder_path(worktree_path):
                add_issue(f"{field_root}.worktree_path", "worktree path must be replaced with a real path")
            elif worktree_path in seen_worktrees:
                add_issue(f"{field_root}.worktree_path", f"duplicate worktree path: {worktree_path}")
            else:
                seen_worktrees.add(worktree_path)

            pool_name = str(effective_worker.get("resource_pool", "")).strip()
            pool_queue = effective_worker.get("resource_pool_queue", [])
            if not pool_name and not pool_queue:
                add_issue(f"{field_root}.resource_pool", "resource_pool or resource_pool_queue is required")
            if pool_name and pool_name not in resource_pools:
                add_issue(f"{field_root}.resource_pool", f"unknown resource pool: {pool_name}")
            if pool_queue and not isinstance(pool_queue, list):
                add_issue(f"{field_root}.resource_pool_queue", "resource_pool_queue must be a list")
            if isinstance(pool_queue, list):
                for queue_index, candidate_pool in enumerate(pool_queue):
                    if str(candidate_pool) not in resource_pools:
                        add_issue(
                            f"{field_root}.resource_pool_queue[{queue_index}]",
                            f"unknown resource pool: {candidate_pool}",
                        )

            environment_type = str(effective_worker.get("environment_type", "uv")).strip() or "uv"
            environment_path = str(effective_worker.get("environment_path", "")).strip()
            if environment_type == "venv":
                if not environment_path:
                    add_issue(
                        f"{field_root}.environment_path",
                        "environment path is required when environment_type is venv",
                    )
                elif is_placeholder_path(environment_path):
                    add_issue(f"{field_root}.environment_path", "environment path must be replaced with a real path")
                elif not path_exists_via_ls(environment_path):
                    add_issue(f"{field_root}.environment_path", f"environment path does not exist: {environment_path}")
            elif environment_type not in {"none", "uv"} and environment_path and is_placeholder_path(environment_path):
                add_issue(f"{field_root}.environment_path", "environment path must be replaced with a real path")

            if not str(effective_worker.get("test_command", "")).strip():
                add_issue(f"{field_root}.test_command", "test_command is required")
            if not str(effective_worker.get("submit_strategy", "")).strip():
                add_issue(f"{field_root}.submit_strategy", "submit_strategy is required")

        return issues

    def validate_config_payload(self, config: dict[str, Any]) -> dict[str, Any]:
        repaired_config, _ = self.repair_config_resource_pool_references(config)
        issues = self.config_validation_issues(repaired_config)
        return {
            "ok": len(issues) == 0,
            "validation_issues": issues,
            "validation_errors": self.validation_errors(repaired_config),
            "launch_blockers": self.launch_blockers(repaired_config),
        }

    def validate_config_section(self, section: str, value: Any) -> dict[str, Any]:
        next_config = self.config_for_section(section, value)
        validation = self.validate_config_payload(next_config)
        validation["validation_issues"] = [
            issue for issue in validation["validation_issues"] if self.field_matches_section(issue["field"], section)
        ]
        validation["validation_errors"] = self.filter_section_issue_text(validation["validation_errors"], section)
        validation["launch_blockers"] = self.filter_section_issue_text(validation["launch_blockers"], section)
        validation["ok"] = len(validation["validation_issues"]) == 0
        return validation

    def refresh_runtime_mode(self) -> None:
        using_template = self.config_path.resolve() == CONFIG_TEMPLATE_PATH.resolve()
        self.bootstrap_mode = using_template
        reasons: list[str] = []
        if using_template:
            reasons.append(f"cold-start bootstrap loaded from template {self.config_path}")
        if self.persist_config_path != self.config_path:
            reasons.append(f"save target is {self.persist_config_path}")
        if self.bootstrap_requested and using_template:
            reasons.append("bootstrap mode was requested explicitly")
        self.bootstrap_reason = "; ".join(reasons)

    def reload_config(self) -> None:
        with self.lock:
            loaded_config = load_yaml(self.config_path)
            self.config, repairs = self.repair_config_resource_pool_references(loaded_config)
            self.project = self.config.get("project", {})
            self.providers = self.config.get("providers", {})
            self.resource_pools = self.config.get("resource_pools", {})
            self.worker_defaults_config = self.worker_defaults(self.config)
            self.provider_stats = self.load_provider_stats()
            self.workers = [
                self.merge_worker_config(worker, self.worker_defaults_config)
                for worker in self.config.get("workers", [])
                if isinstance(worker, dict)
            ]
            self.refresh_runtime_mode()
            self.provider_stats = self.provider_stats or {
                pool_name: self.default_provider_stat_entry() for pool_name in self.resource_pools
            }
            for pool_name in self.resource_pools:
                self.provider_stats.setdefault(
                    pool_name,
                    self.default_provider_stat_entry(),
                )
            self.persist_provider_stats()
            if repairs:
                self.last_event = f"config_repaired:{len(repairs)} stale reference update(s)"

    def validation_errors(self, config: dict[str, Any] | None = None) -> list[str]:
        cfg = config or self.config
        if not isinstance(cfg, dict):
            return ["top-level config must be a YAML mapping"]
        errors: list[str] = []
        project = cfg.get("project", {})
        providers = cfg.get("providers", {})
        resource_pools = cfg.get("resource_pools", {})
        worker_defaults = self.worker_defaults(cfg)
        workers = cfg.get("workers", [])

        if not project.get("repository_name"):
            errors.append("project.repository_name is recommended")
        if not project.get("local_repo_root"):
            errors.append(f"project.local_repo_root is recommended; default runtime root is {REPO_ROOT}")
        elif is_placeholder_path(project.get("local_repo_root")):
            errors.append("project.local_repo_root still points at a placeholder path")
        reference_workspace_root = self.reference_workspace_root(cfg)
        if reference_workspace_root and is_placeholder_path(reference_workspace_root):
            errors.append("project.reference_workspace_root still points at a placeholder path")
        dashboard = project.get("dashboard", {})
        if not dashboard.get("host"):
            errors.append("project.dashboard.host is recommended")
        if not dashboard.get("port"):
            errors.append("project.dashboard.port is recommended")
        if project.get("manager_git_identity"):
            manager_identity = project.get("manager_git_identity", {})
            if not str(manager_identity.get("name", "")).strip():
                errors.append("project.manager_git_identity.name should be set when manager_git_identity is present")
            if not str(manager_identity.get("email", "")).strip():
                errors.append("project.manager_git_identity.email should be set when manager_git_identity is present")
        configured_initial_provider = str(project.get("initial_provider") or "").strip()
        if configured_initial_provider and configured_initial_provider not in providers:
            errors.append(f"project.initial_provider references unknown provider {configured_initial_provider}")

        seen_agents: set[str] = set()
        seen_branches: set[str] = set()
        seen_worktrees: set[str] = set()

        for provider_name, provider in providers.items():
            if not isinstance(provider, dict):
                errors.append(f"providers.{provider_name} must be a mapping")
                continue
            auth_mode = self.provider_auth_mode(provider)
            if auth_mode not in PROVIDER_AUTH_MODES:
                errors.append(f"providers.{provider_name}.auth_mode must be one of {sorted(PROVIDER_AUTH_MODES)}")
            session_probe_command = provider.get("session_probe_command")
            if session_probe_command is not None and not isinstance(session_probe_command, (str, list)):
                errors.append(f"providers.{provider_name}.session_probe_command must be a string or list")

        for pool_name, pool in resource_pools.items():
            provider_name = pool.get("provider")
            if provider_name not in providers:
                errors.append(f"resource_pools.{pool_name}.provider references unknown provider {provider_name}")
            if not pool.get("model"):
                errors.append(f"resource_pools.{pool_name}.model is recommended")
            priority = pool.get("priority", 100)
            if not isinstance(priority, int):
                errors.append(f"resource_pools.{pool_name}.priority must be an integer")
            session_probe_command = pool.get("session_probe_command")
            if session_probe_command is not None and not isinstance(session_probe_command, (str, list)):
                errors.append(f"resource_pools.{pool_name}.session_probe_command must be a string or list")

        for task_type, entry in self.task_policy_types(cfg).items():
            for provider_name in entry.get("preferred_providers", []):
                if provider_name not in providers:
                    errors.append(
                        f"task_policies.types.{task_type}.preferred_providers references unknown provider {provider_name}"
                    )

        for worker in workers:
            if not isinstance(worker, dict):
                errors.append("worker entries must be mappings")
                continue
            effective_worker = self.merge_worker_config(worker, worker_defaults)
            agent = str(worker.get("agent", "")).strip()
            if not agent:
                errors.append("worker.agent is required")
                continue
            if agent in seen_agents:
                errors.append(f"duplicate worker agent {agent}")
            seen_agents.add(agent)

            pool_name = effective_worker.get("resource_pool")
            pool_queue = effective_worker.get("resource_pool_queue", [])
            if pool_name and pool_name not in resource_pools:
                errors.append(f"worker {agent} references unknown resource_pool {pool_name}")
            if not pool_name and not pool_queue:
                errors.append(f"worker {agent} should define resource_pool or resource_pool_queue")
            if pool_queue and not isinstance(pool_queue, list):
                errors.append(f"worker {agent} resource_pool_queue must be a list")
            for candidate_pool in pool_queue if isinstance(pool_queue, list) else []:
                if candidate_pool not in resource_pools:
                    errors.append(f"worker {agent} resource_pool_queue references unknown pool {candidate_pool}")
            branch = str(effective_worker.get("branch", "")).strip()
            if not branch:
                errors.append(f"worker {agent} branch is required for launch")
            elif branch in seen_branches:
                errors.append(f"duplicate worker branch {branch}")
            else:
                seen_branches.add(branch)

            worktree = str(effective_worker.get("worktree_path", "")).strip()
            if not worktree:
                errors.append(f"worker {agent} worktree_path is required for launch")
            elif is_placeholder_path(worktree):
                errors.append(f"worker {agent} worktree_path still points at a placeholder path")
            elif worktree in seen_worktrees:
                errors.append(f"duplicate worker worktree_path {worktree}")
            else:
                seen_worktrees.add(worktree)

            environment_path = effective_worker.get("environment_path")
            if effective_worker.get("environment_type") not in {"none", None} and is_placeholder_path(
                environment_path
            ):
                errors.append(f"worker {agent} environment_path still points at a placeholder path")

            if not effective_worker.get("test_command"):
                errors.append(f"worker {agent} test_command is recommended")
            if not effective_worker.get("submit_strategy"):
                errors.append(f"worker {agent} submit_strategy is recommended")
            git_identity = effective_worker.get("git_identity")
            if git_identity is not None:
                if not isinstance(git_identity, dict):
                    errors.append(f"worker {agent} git_identity must be a mapping")
                else:
                    if not str(git_identity.get("name", "")).strip():
                        errors.append(f"worker {agent} git_identity.name is required when git_identity is set")
                    if not str(git_identity.get("email", "")).strip():
                        errors.append(f"worker {agent} git_identity.email is required when git_identity is set")

        return errors

    def launch_blockers(self, config: dict[str, Any] | None = None) -> list[str]:
        cfg = config or self.config
        if not isinstance(cfg, dict):
            return ["top-level config must be a YAML mapping before launch"]

        blockers: list[str] = []
        providers = cfg.get("providers", {})
        resource_pools = cfg.get("resource_pools", {})
        worker_defaults = self.worker_defaults(cfg)
        workers = cfg.get("workers", [])

        if not isinstance(providers, dict):
            blockers.append("providers must be a mapping")
            providers = {}
        if not isinstance(resource_pools, dict):
            blockers.append("resource_pools must be a mapping")
            resource_pools = {}
        if not isinstance(workers, list):
            blockers.append("workers must be a list")
            workers = []

        if not workers:
            blockers.append("define at least one worker before launch")

        seen_agents: set[str] = set()
        seen_branches: set[str] = set()
        seen_worktrees: set[str] = set()

        for pool_name, pool in resource_pools.items():
            provider_name = pool.get("provider")
            if not provider_name:
                blockers.append(f"resource_pools.{pool_name}.provider is required")
            elif provider_name not in providers:
                blockers.append(f"resource_pools.{pool_name}.provider references unknown provider {provider_name}")
            if not pool.get("model"):
                blockers.append(f"resource_pools.{pool_name}.model is required")
            if not isinstance(pool.get("priority", 100), int):
                blockers.append(f"resource_pools.{pool_name}.priority must be an integer")

        for provider_name, provider in providers.items():
            template = provider.get("command_template")
            if not template:
                blockers.append(f"providers.{provider_name}.command_template is required")

        for worker in workers:
            if not isinstance(worker, dict):
                blockers.append("worker entries must be mappings")
                continue
            effective_worker = self.merge_worker_config(worker, worker_defaults)
            agent = str(worker.get("agent", "")).strip()
            if not agent:
                blockers.append("worker.agent is required")
                continue
            if agent in seen_agents:
                blockers.append(f"duplicate worker agent {agent}")
            seen_agents.add(agent)

            branch = str(effective_worker.get("branch", "")).strip()
            if not branch:
                blockers.append(f"worker {agent} branch is required")
            elif branch in seen_branches:
                blockers.append(f"duplicate worker branch {branch}")
            else:
                seen_branches.add(branch)

            worktree = str(effective_worker.get("worktree_path", "")).strip()
            if not worktree:
                blockers.append(f"worker {agent} worktree_path is required")
            elif is_placeholder_path(worktree):
                blockers.append(f"worker {agent} worktree_path must be replaced with a real path")
            elif worktree in seen_worktrees:
                blockers.append(f"duplicate worker worktree_path {worktree}")
            else:
                seen_worktrees.add(worktree)

            pool_name = effective_worker.get("resource_pool")
            pool_queue = effective_worker.get("resource_pool_queue", [])
            if pool_name and pool_name not in resource_pools:
                blockers.append(f"worker {agent} references unknown resource_pool {pool_name}")
            if not pool_name and not pool_queue:
                blockers.append(f"worker {agent} must define resource_pool or resource_pool_queue")
            if pool_queue and not isinstance(pool_queue, list):
                blockers.append(f"worker {agent} resource_pool_queue must be a list")
            for candidate_pool in pool_queue if isinstance(pool_queue, list) else []:
                if candidate_pool not in resource_pools:
                    blockers.append(f"worker {agent} resource_pool_queue references unknown pool {candidate_pool}")

            environment_path = effective_worker.get("environment_path")
            if effective_worker.get("environment_type") not in {"none", None} and is_placeholder_path(
                environment_path
            ):
                blockers.append(f"worker {agent} environment_path must be replaced with a real path")
            if not effective_worker.get("test_command"):
                blockers.append(f"worker {agent} test_command is required")
            if not effective_worker.get("submit_strategy"):
                blockers.append(f"worker {agent} submit_strategy is required")

        return blockers

    def save_config_data(self, parsed: dict[str, Any]) -> list[str]:
        parsed, _ = self.repair_config_resource_pool_references(parsed)
        target_path = self.persist_config_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(yaml_text(parsed), encoding="utf-8")
        self.config_path = target_path
        self.reload_config()
        self.last_event = f"config_saved:{now_iso()}"
        return self.validation_errors(parsed)

    def save_config_section(self, section: str, value: Any) -> list[str]:
        next_config = self.config_for_section(section, value)
        validation = self.validate_config_section(section, value)
        if validation["validation_issues"]:
            raise ValueError(f"section {section} has validation issues")
        return self.save_config_data(next_config)

    def save_config_text(self, raw_text: str) -> list[str]:
        parsed = yaml.safe_load(raw_text) or {}
        if not isinstance(parsed, dict):
            raise ValueError("top-level config must be a YAML mapping")
        return self.save_config_data(parsed)
