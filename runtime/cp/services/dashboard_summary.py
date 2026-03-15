from __future__ import annotations

from typing import Any, Callable

from ..utils import dedupe_strings


TaskResolver = Callable[[dict[str, Any]], dict[str, Any]]


def compute_manager_control_state(
    workers: list[dict[str, Any]],
    runtime_state: dict[str, Any] | None,
    heartbeat_state: dict[str, Any] | None,
    backlog_items: list[dict[str, Any]],
    task_record_for_worker: TaskResolver,
) -> dict[str, Any]:
    normalized_runtime = runtime_state if isinstance(runtime_state, dict) else {}
    normalized_heartbeats = heartbeat_state if isinstance(heartbeat_state, dict) else {}
    runtime_workers = {
        str(item.get("agent", "")).strip(): item
        for item in normalized_runtime.get("workers", [])
        if isinstance(item, dict)
    }
    heartbeat_workers = {
        str(item.get("agent", "")).strip(): item
        for item in normalized_heartbeats.get("agents", [])
        if isinstance(item, dict)
    }
    completed_task_ids = {
        str(item.get("id", "")).strip()
        for item in backlog_items
        if str(item.get("status", "")).strip() in {"done", "completed", "merged"}
    }

    active_agents: list[str] = []
    attention_agents: list[str] = []
    runnable_agents: list[str] = []
    blocked_agents: list[str] = []

    for worker in workers:
        agent = str(worker.get("agent", "")).strip()
        runtime_entry = runtime_workers.get(agent, {})
        heartbeat = heartbeat_workers.get(agent, {})
        runtime_status = str(runtime_entry.get("status", "")).strip()
        heartbeat_value = str(heartbeat.get("state", "")).strip()
        backlog_item = task_record_for_worker(worker)
        backlog_status = str(backlog_item.get("status", "")).strip()
        dependencies = [str(item).strip() for item in backlog_item.get("dependencies", []) if str(item).strip()]
        dependencies_ready = all(item in completed_task_ids for item in dependencies)

        if runtime_status in {"launching", "healthy", "active"}:
            active_agents.append(agent)
            continue
        if runtime_status.startswith("launch_failed") or heartbeat_value in {"stale", "error"}:
            attention_agents.append(agent)
            continue
        if backlog_status == "blocked" or (dependencies and not dependencies_ready):
            blocked_agents.append(agent)
            continue
        if backlog_status in {"pending", "queued", "not-started", "not_started", ""}:
            runnable_agents.append(agent)

    return {
        "worker_count": len(workers),
        "active_agents": active_agents,
        "attention_agents": attention_agents,
        "runnable_agents": runnable_agents,
        "blocked_agents": blocked_agents,
    }


def summarize_worker_handoff(
    runtime_entry: dict[str, Any],
    heartbeat: dict[str, Any],
    status_meta: dict[str, str] | None = None,
    status_sections: dict[str, str] | None = None,
    checkpoint_meta: dict[str, str] | None = None,
    checkpoint_sections: dict[str, str] | None = None,
    *,
    parse_list: Callable[[str], list[str]],
    parse_paragraph: Callable[[str], str],
) -> dict[str, Any]:
    normalized_status_meta = status_meta if isinstance(status_meta, dict) else {}
    normalized_status_sections = status_sections if isinstance(status_sections, dict) else {}
    normalized_checkpoint_meta = checkpoint_meta if isinstance(checkpoint_meta, dict) else {}
    normalized_checkpoint_sections = checkpoint_sections if isinstance(checkpoint_sections, dict) else {}

    blockers = dedupe_strings(parse_list(normalized_status_sections.get("blockers", "")))
    requested_unlocks = dedupe_strings(parse_list(normalized_status_sections.get("requested unlocks", "")))
    pending_work = dedupe_strings(parse_list(normalized_checkpoint_sections.get("pending work", "")))
    dependencies = dedupe_strings(parse_list(normalized_checkpoint_sections.get("dependencies", "")))
    resume_instruction = parse_paragraph(normalized_checkpoint_sections.get("resume instruction", ""))
    next_checkin = parse_paragraph(normalized_status_sections.get("next check-in condition", ""))

    runtime_status = str(runtime_entry.get("status", "")).strip()
    heartbeat_state = str(heartbeat.get("state", "")).strip()
    heartbeat_evidence = str(heartbeat.get("evidence", "")).strip()
    heartbeat_escalation = str(heartbeat.get("escalation", "")).strip()
    attention_summary = ""
    if runtime_status.startswith("launch_failed"):
        attention_summary = runtime_status
    elif heartbeat_evidence == "process_exit" and heartbeat_escalation and heartbeat_escalation != "none":
        attention_summary = heartbeat_escalation
    elif heartbeat_state in {"stale", "error"} and heartbeat_evidence:
        attention_summary = heartbeat_escalation or heartbeat_evidence
    elif blockers:
        attention_summary = blockers[0]
    elif pending_work:
        attention_summary = pending_work[0]
    elif heartbeat_evidence and heartbeat_evidence.lower() != "no runtime heartbeat yet":
        attention_summary = heartbeat_escalation or heartbeat_evidence

    return {
        "checkpoint_status": normalized_checkpoint_meta.get("status")
        or normalized_status_meta.get("status")
        or heartbeat_state
        or "unknown",
        "attention_summary": attention_summary,
        "blockers": blockers,
        "pending_work": pending_work,
        "requested_unlocks": requested_unlocks,
        "dependencies": dependencies,
        "resume_instruction": resume_instruction,
        "next_checkin": next_checkin or str(heartbeat.get("expected_next_checkin", "")).strip(),
    }
