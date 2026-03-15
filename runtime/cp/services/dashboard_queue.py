from __future__ import annotations

from typing import Any, Callable

from ..utils import now_iso, slugify, summarize_list


WorkerIdentityResolver = Callable[[dict[str, Any]], str]


def identity_display(identity: dict[str, Any] | None, fallback: str) -> str:
    normalized = identity if isinstance(identity, dict) else {}
    name = str(normalized.get("name", "")).strip()
    email = str(normalized.get("email", "")).strip()
    if name and email:
        return f"{name} <{email}>"
    return fallback


def build_merge_queue(
    workers: list[dict[str, Any]],
    runtime_state: dict[str, Any] | None,
    heartbeat_state: dict[str, Any] | None,
    handoff_by_agent: dict[str, dict[str, Any]] | None,
    *,
    integration_branch: str,
    manager_identity: dict[str, Any] | None,
    worker_identity_display: WorkerIdentityResolver,
) -> list[dict[str, Any]]:
    normalized_runtime = runtime_state if isinstance(runtime_state, dict) else {}
    normalized_heartbeats = heartbeat_state if isinstance(heartbeat_state, dict) else {}
    normalized_handoffs = handoff_by_agent if isinstance(handoff_by_agent, dict) else {}

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
    manager_display = identity_display(manager_identity, "A0 manager identity")

    queue: list[dict[str, Any]] = []
    for worker in workers:
        agent = str(worker.get("agent", "")).strip()
        runtime_entry = runtime_workers.get(agent, {})
        heartbeat = heartbeat_workers.get(agent, {})
        handoff = normalized_handoffs.get(agent, {}) if isinstance(normalized_handoffs.get(agent), dict) else {}
        queue.append(
            {
                "agent": agent,
                "branch": worker.get("branch", "unassigned"),
                "submit_strategy": worker.get("submit_strategy", "patch_handoff"),
                "merge_target": integration_branch,
                "worker_identity": worker_identity_display(worker),
                "manager_identity": manager_display,
                "status": runtime_entry.get("status", heartbeat.get("state", "not_started")),
                "checkpoint_status": handoff.get("checkpoint_status", "unknown"),
                "attention_summary": handoff.get("attention_summary", ""),
                "blockers": handoff.get("blockers") or [],
                "pending_work": handoff.get("pending_work") or [],
                "requested_unlocks": handoff.get("requested_unlocks") or [],
                "dependencies": handoff.get("dependencies") or [],
                "resume_instruction": str(handoff.get("resume_instruction", "")).strip(),
                "next_checkin": str(handoff.get("next_checkin", "")).strip(),
                "manager_action": f"A0 merges {worker.get('branch', 'unassigned')} into {integration_branch}",
            }
        )
    return queue


def manager_inbox(messages: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized_messages = messages if isinstance(messages, list) else []
    return [
        item
        for item in normalized_messages
        if isinstance(item, dict)
        and str(item.get("ack_state") or "") != "resolved"
        and (
            str(item.get("to") or "") in {"A0", "a0", "manager", "all"}
            or str(item.get("scope") or "") in {"broadcast", "manager"}
        )
    ]


def build_a0_request_catalog(
    backlog_items: list[dict[str, Any]],
    merge_queue: list[dict[str, Any]],
    mailbox_messages: list[dict[str, Any]] | None,
    request_state: dict[str, dict[str, Any]] | None = None,
    messages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_request_state = request_state if isinstance(request_state, dict) else {}
    normalized_messages = messages if isinstance(messages, list) else []
    requests: list[dict[str, Any]] = []
    inbox = manager_inbox(mailbox_messages)

    for item in backlog_items:
        if not isinstance(item, dict):
            continue
        task_id = str(item.get("id") or "").strip()
        claimant = str(item.get("claimed_by") or item.get("owner") or "A?").strip() or "A?"
        if str(item.get("plan_state") or "") == "pending_review":
            request_id = slugify(f"{task_id}_plan_review")
            saved = normalized_request_state.get(request_id, {}) if isinstance(normalized_request_state.get(request_id), dict) else {}
            requests.append(
                {
                    "id": request_id,
                    "agent": claimant,
                    "task_id": task_id,
                    "request_type": "plan_review",
                    "status": str(item.get("status") or "pending"),
                    "title": f"{task_id} requests plan approval",
                    "body": str(item.get("plan_summary") or f"{task_id} is waiting for manager review").strip(),
                    "resume_instruction": "Approve to allow implementation, or reject with constraints.",
                    "next_checkin": str(item.get("updated_at") or item.get("claimed_at") or "").strip(),
                    "response_state": str(saved.get("response_state") or "pending").strip() or "pending",
                    "response_note": str(saved.get("response_note") or item.get("plan_review_note") or "").strip(),
                    "response_at": str(saved.get("response_at") or item.get("plan_reviewed_at") or "").strip(),
                    "created_at": str(saved.get("created_at") or item.get("claimed_at") or now_iso()).strip(),
                }
            )
        elif str(item.get("status") or "") == "review" or str(item.get("claim_state") or "") == "review":
            request_id = slugify(f"{task_id}_task_review")
            saved = normalized_request_state.get(request_id, {}) if isinstance(normalized_request_state.get(request_id), dict) else {}
            requests.append(
                {
                    "id": request_id,
                    "agent": claimant,
                    "task_id": task_id,
                    "request_type": "task_review",
                    "status": str(item.get("status") or "review"),
                    "title": f"{task_id} requests manager acceptance",
                    "body": str(item.get("review_note") or f"{task_id} is ready for manager review").strip(),
                    "resume_instruction": "Accept to unblock dependents, or reopen with a concrete correction.",
                    "next_checkin": str(item.get("review_requested_at") or item.get("updated_at") or "").strip(),
                    "response_state": str(saved.get("response_state") or "pending").strip() or "pending",
                    "response_note": str(saved.get("response_note") or item.get("review_note") or "").strip(),
                    "response_at": str(saved.get("response_at") or item.get("completed_at") or "").strip(),
                    "created_at": str(saved.get("created_at") or item.get("review_requested_at") or now_iso()).strip(),
                }
            )

    for item in merge_queue:
        if not isinstance(item, dict):
            continue
        agent = str(item.get("agent", "")).strip()
        requested_unlocks = item.get("requested_unlocks") or []
        blockers = item.get("blockers") or []
        attention_summary = str(item.get("attention_summary", "")).strip()
        status = str(item.get("status", "")).strip() or "not_started"
        if not requested_unlocks and not blockers and not attention_summary:
            continue

        title = f"{agent} needs A0 review"
        if requested_unlocks:
            title = f"{agent} requests unlock"
        elif status.startswith("launch_failed") or status == "stale":
            title = f"{agent} needs intervention"

        body_parts = []
        if attention_summary:
            body_parts.append(attention_summary)
        if requested_unlocks:
            body_parts.append(f"requested unlocks: {summarize_list(requested_unlocks)}")
        if blockers:
            body_parts.append(f"blockers: {summarize_list(blockers)}")
        request_id = slugify(
            f"{agent}_{status}_{title}_{attention_summary or summarize_list(requested_unlocks) or summarize_list(blockers)}"
        )
        saved = normalized_request_state.get(request_id, {}) if isinstance(normalized_request_state.get(request_id), dict) else {}
        response_state = str(saved.get("response_state", "pending")).strip() or "pending"
        response_note = str(saved.get("response_note", "")).strip()
        response_at = str(saved.get("response_at", "")).strip()
        created_at = str(saved.get("created_at", "")).strip() or now_iso()

        requests.append(
            {
                "id": request_id,
                "agent": agent,
                "request_type": "worker_intervention",
                "status": status,
                "title": title,
                "body": "; ".join(body_parts) or title,
                "requested_unlocks": requested_unlocks,
                "blockers": blockers,
                "resume_instruction": str(item.get("resume_instruction", "")).strip(),
                "next_checkin": str(item.get("next_checkin", "")).strip(),
                "response_state": response_state,
                "response_note": response_note,
                "response_at": response_at,
                "created_at": created_at,
            }
        )

    requests.sort(key=lambda item: (item["response_state"] != "pending", item["agent"], item["id"]))
    pending_count = sum(1 for item in requests if item["response_state"] == "pending") + len(inbox)
    return {
        "requests": requests,
        "messages": normalized_messages[-20:],
        "inbox": inbox[-20:],
        "pending_count": pending_count,
        "last_updated": now_iso(),
    }
