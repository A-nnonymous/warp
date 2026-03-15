from __future__ import annotations

from typing import Any

from ..constants import DEFAULT_INITIAL_PROVIDER
from ..utils import dedupe_strings, slugify


def task_policy_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config if isinstance(config, dict) else {}
    task_policies = cfg.get("task_policies", {})
    return task_policies if isinstance(task_policies, dict) else {}


def provider_preference_default(config: dict[str, Any] | None = None) -> list[str]:
    cfg = config if isinstance(config, dict) else {}
    configured_providers = cfg.get("providers", {}) if isinstance(cfg.get("providers", {}), dict) else {}
    resource_pools = cfg.get("resource_pools", {}) if isinstance(cfg.get("resource_pools", {}), dict) else {}
    ordered_pools: list[tuple[str, dict[str, Any]]] = []
    if isinstance(resource_pools, dict):
        ordered_pools = sorted(
            ((str(name), entry) for name, entry in resource_pools.items() if isinstance(entry, dict)),
            key=lambda item: (-int(item[1].get("priority", 0)), item[0]),
        )
    ordered = [str(entry.get("provider", "")).strip() for _, entry in ordered_pools if entry.get("provider")]
    fallback = [DEFAULT_INITIAL_PROVIDER, *sorted(str(key) for key in configured_providers.keys())]
    return dedupe_strings([*ordered, *fallback])


def initial_provider_name(config: dict[str, Any] | None = None) -> str:
    cfg = config if isinstance(config, dict) else {}
    project = cfg.get("project", {}) if isinstance(cfg.get("project", {}), dict) else {}
    providers = cfg.get("providers", {}) if isinstance(cfg.get("providers", {}), dict) else {}
    configured_initial = str(project.get("initial_provider") or "").strip()
    if configured_initial and configured_initial in providers:
        return configured_initial
    if DEFAULT_INITIAL_PROVIDER in providers:
        return DEFAULT_INITIAL_PROVIDER
    preferences = provider_preference_default(cfg)
    for provider_name in preferences:
        if provider_name in providers:
            return provider_name
    return configured_initial or DEFAULT_INITIAL_PROVIDER


def task_policy_defaults(config: dict[str, Any] | None = None) -> dict[str, Any]:
    policy_config = task_policy_config(config)
    defaults = policy_config.get("defaults", {})
    if not isinstance(defaults, dict):
        defaults = {}
    preferred_providers = defaults.get("preferred_providers")
    if not isinstance(preferred_providers, list) or not preferred_providers:
        preferred_providers = provider_preference_default(config)
    return {
        "task_type": str(defaults.get("task_type") or "default").strip() or "default",
        "preferred_providers": dedupe_strings(preferred_providers),
        "suggested_test_command": str(defaults.get("suggested_test_command") or "").strip(),
        "prompt_context_files": dedupe_strings(defaults.get("prompt_context_files") or []),
    }


def task_policy_types(config: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    policy_config = task_policy_config(config)
    types = policy_config.get("types", {})
    if not isinstance(types, dict):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for task_type, entry in types.items():
        if not isinstance(entry, dict):
            continue
        normalized[str(task_type).strip()] = {
            "preferred_providers": dedupe_strings(entry.get("preferred_providers") or []),
            "suggested_test_command": str(entry.get("suggested_test_command") or "").strip(),
            "prompt_context_files": dedupe_strings(entry.get("prompt_context_files") or []),
        }
    return normalized


def task_policy_rules(config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    policy_config = task_policy_config(config)
    rules = policy_config.get("rules", [])
    if not isinstance(rules, list):
        return []
    return [rule for rule in rules if isinstance(rule, dict)]


def task_policy_rule_matches(rule: dict[str, Any], worker: dict[str, Any], task: dict[str, Any]) -> bool:
    task_id = str(task.get("id") or worker.get("task_id") or "").strip()
    title = str(task.get("title") or "").strip().lower()
    agent = str(worker.get("agent") or "").strip()

    agents = rule.get("agents")
    if agents is not None:
        allowed_agents = dedupe_strings(agents if isinstance(agents, list) else [])
        if not allowed_agents or agent not in allowed_agents:
            return False

    task_ids = rule.get("task_ids")
    if task_ids is not None:
        allowed_task_ids = dedupe_strings(task_ids if isinstance(task_ids, list) else [])
        if not allowed_task_ids or task_id not in allowed_task_ids:
            return False

    title_contains = rule.get("title_contains")
    if title_contains is not None:
        if not isinstance(title_contains, list) or not any(
            str(fragment).strip().lower() in title for fragment in title_contains if str(fragment).strip()
        ):
            return False

    return True


def select_task_record_for_worker(backlog_items: list[dict[str, Any]], worker: dict[str, Any]) -> dict[str, Any]:
    task_id = str(worker.get("task_id", "")).strip()
    agent = str(worker.get("agent", "")).strip()
    if task_id:
        for item in backlog_items:
            if str(item.get("id", "")).strip() == task_id:
                return item
    if agent:
        owned = [item for item in backlog_items if str(item.get("owner", "")).strip() == agent]
        if len(owned) == 1:
            return owned[0]
        for item in owned:
            if str(item.get("status", "")).strip() in {"pending", "blocked", "active", "in_progress", "review"}:
                return item
    return {}


def suggested_task_id(worker: dict[str, Any], backlog_items: list[dict[str, Any]]) -> str:
    explicit = str(worker.get("task_id", "")).strip()
    if explicit:
        return explicit
    task = select_task_record_for_worker(backlog_items, worker)
    if task:
        return str(task.get("id", "")).strip()
    agent = str(worker.get("agent", "")).strip()
    return f"{agent}-001" if agent else ""


def build_task_profile(worker: dict[str, Any], backlog_items: list[dict[str, Any]], config: dict[str, Any] | None = None) -> dict[str, Any]:
    task = select_task_record_for_worker(backlog_items, worker)
    task_id = str(task.get("id") or worker.get("task_id") or "").strip()
    title = str(task.get("title") or task_id or worker.get("agent") or "").strip()
    defaults = task_policy_defaults(config)
    explicit_task_type = str(worker.get("task_type") or task.get("task_type") or "").strip()
    task_type = explicit_task_type or defaults["task_type"]
    matched_rule_name = ""
    if not explicit_task_type:
        for rule in task_policy_rules(config):
            candidate_type = str(rule.get("task_type") or "").strip()
            if not candidate_type:
                continue
            if task_policy_rule_matches(rule, worker, task):
                task_type = candidate_type
                matched_rule_name = str(rule.get("name") or candidate_type).strip()
                break

    policy = {**defaults, **task_policy_types(config).get(task_type, {})}
    preferred_providers = dedupe_strings(policy.get("preferred_providers") or provider_preference_default(config))
    return {
        "task_id": task_id,
        "title": title,
        "task_type": task_type,
        "category": task_type,
        "preferred_providers": preferred_providers,
        "suggested_test_command": str(policy.get("suggested_test_command") or "").strip(),
        "prompt_context_files": dedupe_strings(policy.get("prompt_context_files") or []),
        "matched_rule_name": matched_rule_name,
        "task": task,
    }


def suggested_branch_name(worker: dict[str, Any], profile: dict[str, Any]) -> str:
    explicit_branch = str(worker.get("branch", "")).strip()
    if explicit_branch:
        return explicit_branch
    agent = str(worker.get("agent", "")).strip().lower()
    suffix = slugify(profile.get("title") or profile.get("task_id") or agent)
    if agent and suffix:
        return f"{agent}_{suffix}"
    return ""
