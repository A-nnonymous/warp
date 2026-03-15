from __future__ import annotations

from typing import Any


def configured_pool_candidates(
    worker: dict[str, Any],
    defaults: dict[str, Any] | None,
    resource_pools: dict[str, Any] | None,
) -> list[str]:
    explicit_pool = str(worker.get("resource_pool", "")).strip()
    explicit_queue = worker.get("resource_pool_queue")
    normalized_defaults = defaults if isinstance(defaults, dict) else {}
    normalized_pools = resource_pools if isinstance(resource_pools, dict) else {}

    if explicit_pool:
        return [explicit_pool]
    if isinstance(explicit_queue, list) and explicit_queue:
        return [str(item) for item in explicit_queue if str(item)]

    default_queue = normalized_defaults.get("resource_pool_queue")
    if isinstance(default_queue, list) and default_queue:
        return [str(item) for item in default_queue if str(item)]

    default_pool = str(normalized_defaults.get("resource_pool") or "").strip()
    if default_pool:
        return [default_pool]

    return [str(name) for name in normalized_pools.keys()]


def queue_pool_candidates(worker: dict[str, Any], provider_queue: list[dict[str, Any]]) -> list[str]:
    explicit_pool = str(worker.get("resource_pool", "")).strip()
    if explicit_pool:
        return [explicit_pool]

    configured_queue = worker.get("resource_pool_queue")
    if isinstance(configured_queue, list) and configured_queue:
        return [str(item) for item in configured_queue if str(item)]

    return [str(item.get("resource_pool", "")).strip() for item in provider_queue if str(item.get("resource_pool", "")).strip()]


def pool_rank_tuple(
    pool_name: str,
    evaluations: dict[str, dict[str, Any]],
    preferred_providers: list[str],
    explicit_pool: str = "",
) -> tuple[float, int, str]:
    evaluation = evaluations.get(pool_name)
    if not evaluation:
        return (-1.0, len(preferred_providers), pool_name)

    provider_name = str(evaluation.get("provider", ""))
    provider_rank = preferred_providers.index(provider_name) if provider_name in preferred_providers else len(preferred_providers)
    affinity_bonus = max(0, len(preferred_providers) - provider_rank) * 40
    lock_bonus = 500 if explicit_pool and pool_name == explicit_pool else 0
    return (float(evaluation.get("score", 0.0)) + affinity_bonus + lock_bonus, -provider_rank, pool_name)


def rank_pool_candidates(
    candidate_pools: list[str],
    evaluations: dict[str, dict[str, Any]],
    preferred_providers: list[str],
    explicit_pool: str = "",
) -> list[str]:
    return sorted(
        [str(pool_name) for pool_name in candidate_pools if str(pool_name)],
        key=lambda pool_name: pool_rank_tuple(pool_name, evaluations, preferred_providers, explicit_pool),
        reverse=True,
    )


def recommended_pool_plan(
    worker: dict[str, Any],
    resource_pools: dict[str, Any] | None,
    defaults: dict[str, Any] | None,
    provider_queue: list[dict[str, Any]],
    profile: dict[str, Any],
) -> dict[str, Any]:
    normalized_pools = resource_pools if isinstance(resource_pools, dict) else {}
    if not normalized_pools:
        return {
            "recommended_pool": "",
            "locked_pool": "",
            "recommended_queue": [],
            "reason": "no resource pools configured",
            "category": str(profile.get("task_type") or "default"),
            "preferred_providers": list(profile.get("preferred_providers") or []),
        }

    explicit_pool = str(worker.get("resource_pool", "")).strip()
    candidate_pools = configured_pool_candidates(worker, defaults, normalized_pools)
    evaluations = {
        str(item.get("resource_pool", "")): item
        for item in provider_queue
        if str(item.get("resource_pool", "")) in candidate_pools
    }
    preferred_providers = [str(item) for item in profile.get("preferred_providers") or [] if str(item)]
    ordered_candidates = rank_pool_candidates(candidate_pools, evaluations, preferred_providers, explicit_pool)
    recommended_pool = ordered_candidates[0] if ordered_candidates else ""
    recommended_queue = ordered_candidates if ordered_candidates else candidate_pools
    locked_pool = explicit_pool
    reason = "explicit worker pool override"

    if not locked_pool and recommended_pool:
        preferred_usable_candidates: list[str] = []
        for preferred_provider in preferred_providers:
            provider_candidates = [
                pool_name
                for pool_name in ordered_candidates
                if str(evaluations.get(pool_name, {}).get("provider", "")) == preferred_provider
                and bool(evaluations.get(pool_name, {}).get("launch_ready"))
            ]
            if provider_candidates:
                preferred_usable_candidates = provider_candidates
                break

        if preferred_usable_candidates:
            locked_pool = preferred_usable_candidates[0]
            recommended_pool = locked_pool
            recommended_queue = [locked_pool] + [pool for pool in ordered_candidates if pool != locked_pool]
            reason = (
                f"A0 locked {locked_pool} for {profile['task_type']} work using task policy plus provider quality"
            )
        else:
            reason = f"A0 recommends {recommended_pool} for {profile['task_type']} work"

    return {
        "recommended_pool": recommended_pool,
        "locked_pool": locked_pool,
        "recommended_queue": recommended_queue,
        "reason": reason,
        "category": profile["task_type"],
        "preferred_providers": preferred_providers,
    }


def best_pool_for_provider(provider_name: str, provider_queue: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    ordered_candidates = [item for item in provider_queue if str(item.get("provider", "")) == provider_name]
    if not ordered_candidates:
        raise RuntimeError(f"no eligible resource pool candidates exist for provider {provider_name}")
    for item in ordered_candidates:
        if item.get("launch_ready"):
            return str(item["resource_pool"]), item
    return str(ordered_candidates[0]["resource_pool"]), ordered_candidates[0]


def best_pool_for_worker(worker: dict[str, Any], provider_queue: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    evaluations = {
        str(item.get("resource_pool", "")): item
        for item in provider_queue
        if str(item.get("resource_pool", "")).strip()
    }
    ordered_candidates = []
    for pool_name in queue_pool_candidates(worker, provider_queue):
        if pool_name in evaluations:
            ordered_candidates.append(evaluations[pool_name])
    ordered_candidates.sort(
        key=lambda item: (-int(item.get("score", 0)), -int(item.get("priority", 0)), str(item.get("resource_pool", "")))
    )
    for item in ordered_candidates:
        if item.get("launch_ready"):
            return str(item["resource_pool"]), item
    if ordered_candidates:
        return str(ordered_candidates[0]["resource_pool"]), ordered_candidates[0]
    raise RuntimeError(f"worker {worker['agent']} has no eligible resource pool candidates")
