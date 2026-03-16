from __future__ import annotations

from typing import Any

from ..contracts import BacklogItem, CleanupState, CleanupWorkerState, HeartbeatState, RuntimeState
from ..utils import now_iso, summarize_list


ReviewMap = dict[str, list[str]]
LockedFileEntry = dict[str, str]


def cleanup_review_maps(backlog_items: list[BacklogItem]) -> tuple[ReviewMap, ReviewMap, list[str], list[str]]:
    plan_reviews_by_agent: ReviewMap = {}
    task_reviews_by_agent: ReviewMap = {}
    pending_plan_reviews: list[str] = []
    pending_task_reviews: list[str] = []

    for item in backlog_items:
        if not isinstance(item, dict):
            continue
        task_id = str(item.get("id") or "").strip()
        responsible_agent = str(item.get("claimed_by") or item.get("owner") or "").strip()
        if str(item.get("plan_state") or "") == "pending_review":
            pending_plan_reviews.append(task_id)
            if responsible_agent:
                plan_reviews_by_agent.setdefault(responsible_agent, []).append(task_id)
        if str(item.get("status") or "") == "review" or str(item.get("claim_state") or "") == "review":
            pending_task_reviews.append(task_id)
            if responsible_agent:
                task_reviews_by_agent.setdefault(responsible_agent, []).append(task_id)

    return plan_reviews_by_agent, task_reviews_by_agent, pending_plan_reviews, pending_task_reviews



def cleanup_locked_files(locks_state: dict[str, Any] | None) -> tuple[list[LockedFileEntry], dict[str, list[str]]]:
    normalized_state = locks_state if isinstance(locks_state, dict) else {}
    locked_files: list[LockedFileEntry] = []
    locked_files_by_owner: dict[str, list[str]] = {}

    for item in normalized_state.get("locks", []):
        if not isinstance(item, dict):
            continue
        state = str(item.get("state") or "free").strip() or "free"
        if state == "free":
            continue
        path = str(item.get("path") or "").strip()
        owner = str(item.get("owner") or "").strip() or "unassigned"
        locked_files.append({"path": path, "owner": owner, "state": state})
        locked_files_by_owner.setdefault(owner, []).append(path)

    return locked_files, locked_files_by_owner



def cleanup_worker_row(
    agent: str,
    runtime_workers: dict[str, dict[str, Any]],
    heartbeat_workers: dict[str, dict[str, Any]],
    active_workers: list[str],
    plan_reviews_by_agent: ReviewMap,
    task_reviews_by_agent: ReviewMap,
    locked_files_by_owner: dict[str, list[str]],
) -> CleanupWorkerState:
    runtime_entry = runtime_workers.get(agent, {})
    heartbeat_entry = heartbeat_workers.get(agent, {})
    worker_plan_reviews = plan_reviews_by_agent.get(agent, [])
    worker_task_reviews = task_reviews_by_agent.get(agent, [])
    worker_locked_files = locked_files_by_owner.get(agent, [])

    blockers: list[str] = []
    if agent in active_workers:
        blockers.append("process is still alive")
    if worker_plan_reviews:
        blockers.append(f"pending plan approvals: {summarize_list(worker_plan_reviews)}")
    if worker_task_reviews:
        blockers.append(f"pending task reviews: {summarize_list(worker_task_reviews)}")
    if worker_locked_files:
        blockers.append(f"locks still held: {summarize_list(worker_locked_files)}")

    return {
        "agent": agent,
        "ready": len(blockers) == 0,
        "active": agent in active_workers,
        "runtime_status": str(runtime_entry.get("status") or "").strip(),
        "heartbeat_state": str(heartbeat_entry.get("state") or "").strip(),
        "pending_plan_reviews": worker_plan_reviews,
        "pending_task_reviews": worker_task_reviews,
        "locked_files": worker_locked_files,
        "blockers": blockers,
    }



def cleanup_status_view(
    workers: list[dict[str, Any]],
    runtime_state: RuntimeState | None,
    heartbeat_state: HeartbeatState | None,
    backlog_items: list[BacklogItem],
    locks_state: dict[str, Any] | None,
    active_workers: list[str],
    listener_active: bool,
) -> CleanupState:
    normalized_runtime = runtime_state if isinstance(runtime_state, dict) else {}
    normalized_heartbeats = heartbeat_state if isinstance(heartbeat_state, dict) else {}
    runtime_workers = {
        str(item.get("agent") or "").strip(): item
        for item in normalized_runtime.get("workers", [])
        if isinstance(item, dict)
    }
    heartbeat_workers = {
        str(item.get("agent") or "").strip(): item
        for item in normalized_heartbeats.get("agents", [])
        if isinstance(item, dict)
    }
    plan_reviews_by_agent, task_reviews_by_agent, pending_plan_reviews, pending_task_reviews = cleanup_review_maps(backlog_items)
    locked_files, locked_files_by_owner = cleanup_locked_files(locks_state)

    worker_rows: list[CleanupWorkerState] = []
    for worker in workers:
        if not isinstance(worker, dict):
            continue
        agent = str(worker.get("agent") or "").strip()
        if not agent:
            continue
        worker_rows.append(
            cleanup_worker_row(
                agent,
                runtime_workers,
                heartbeat_workers,
                active_workers,
                plan_reviews_by_agent,
                task_reviews_by_agent,
                locked_files_by_owner,
            )
        )

    blockers: list[str] = []
    if active_workers:
        blockers.append(f"active workers must be stopped: {', '.join(active_workers)}")
    if pending_plan_reviews:
        blockers.append(f"pending plan approvals: {summarize_list(pending_plan_reviews)}")
    if pending_task_reviews:
        blockers.append(f"pending task reviews: {summarize_list(pending_task_reviews)}")
    if locked_files:
        blocker_summary = summarize_list([f"{item['path']} ({item['owner']})" for item in locked_files])
        blockers.append(f"outstanding single-writer locks: {blocker_summary}")

    return {
        "ready": len(blockers) == 0,
        "blockers": blockers,
        "listener_active": bool(listener_active),
        "active_workers": active_workers,
        "pending_plan_reviews": pending_plan_reviews,
        "pending_task_reviews": pending_task_reviews,
        "locked_files": locked_files,
        "workers": worker_rows,
        "last_updated": now_iso(),
    }
