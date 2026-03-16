from __future__ import annotations

from ..contracts import PoolUsageSummary, ProviderQueueItem


def provider_connection_quality(launch_ready: bool, latency_ms: float) -> float:
    if not launch_ready:
        return 0.0
    if latency_ms < 25:
        return 1.0
    if latency_ms < 100:
        return 0.9
    return 0.8


def provider_failure_detail(
    *,
    pool_name: str,
    binary: str,
    binary_found: bool,
    auth_ready: bool,
    auth_detail: str,
    last_failure: str,
) -> str:
    if not binary_found:
        return f"provider binary missing for pool {pool_name}: {binary or 'unassigned'}"
    if not auth_ready:
        return auth_detail
    return last_failure


def provider_queue_item(
    *,
    pool_name: str,
    provider_name: str,
    model: str,
    priority: int,
    binary: str,
    binary_found: bool,
    recursion_guard: str,
    launch_wrapper: str,
    auth_mode: str,
    auth_ready: bool,
    auth_detail: str,
    api_key_present: bool,
    latency_ms: float,
    work_quality: float,
    pool_usage: PoolUsageSummary,
    last_failure: str,
) -> ProviderQueueItem:
    launch_ready = binary_found and auth_ready
    active_workers = len(pool_usage["running_agents"])
    connection_quality = provider_connection_quality(launch_ready, latency_ms)
    score = round(priority * 100 + connection_quality * 30 + work_quality * 70, 3)
    return {
        "resource_pool": pool_name,
        "provider": provider_name,
        "model": model,
        "priority": priority,
        "binary": binary,
        "binary_found": binary_found,
        "recursion_guard": recursion_guard,
        "launch_wrapper": launch_wrapper,
        "auth_mode": auth_mode,
        "auth_ready": auth_ready,
        "auth_detail": auth_detail,
        "api_key_present": api_key_present,
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
        "last_failure": provider_failure_detail(
            pool_name=pool_name,
            binary=binary,
            binary_found=binary_found,
            auth_ready=auth_ready,
            auth_detail=auth_detail,
            last_failure=last_failure,
        ),
    }
