from __future__ import annotations

from typing import Any, Callable

from ..contracts import (
    A0ConsoleMessage,
    A0ConsoleRequest,
    A0ConsoleState,
    BacklogItem,
    MergeQueueItem,
    TeamMailboxMessage,
    TeamMailboxState,
    WorkerHandoffSummary,
)
from ..utils import now_iso, slugify, summarize_list


WorkerIdentityResolver = Callable[[dict[str, Any]], str]
RequestStateMap = dict[str, A0ConsoleRequest]


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
    handoff_by_agent: dict[str, WorkerHandoffSummary] | None,
    *,
    integration_branch: str,
    manager_identity: dict[str, Any] | None,
    worker_identity_display: WorkerIdentityResolver,
) -> list[MergeQueueItem]:
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

    queue: list[MergeQueueItem] = []
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


def _saved_request(request_state: RequestStateMap, request_id: str) -> A0ConsoleRequest:
    saved = request_state.get(request_id, {})
    return saved if isinstance(saved, dict) else {}



def backlog_plan_review_request(item: BacklogItem, request_state: RequestStateMap) -> A0ConsoleRequest | None:
    if not isinstance(item, dict) or str(item.get("plan_state") or "") != "pending_review":
        return None

    task_id = str(item.get("id") or "").strip()
    claimant = str(item.get("claimed_by") or item.get("owner") or "A?").strip() or "A?"
    request_id = slugify(f"{task_id}_plan_review")
    saved = _saved_request(request_state, request_id)
    return {
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



def backlog_task_review_request(item: BacklogItem, request_state: RequestStateMap) -> A0ConsoleRequest | None:
    if not isinstance(item, dict):
        return None
    if str(item.get("status") or "") != "review" and str(item.get("claim_state") or "") != "review":
        return None

    task_id = str(item.get("id") or "").strip()
    claimant = str(item.get("claimed_by") or item.get("owner") or "A?").strip() or "A?"
    request_id = slugify(f"{task_id}_task_review")
    saved = _saved_request(request_state, request_id)
    review_note = str(item.get("review_note") or f"{task_id} is ready for manager review").strip()
    return {
        "id": request_id,
        "agent": claimant,
        "task_id": task_id,
        "request_type": "task_review",
        "status": str(item.get("status") or "review"),
        "title": f"{task_id} requests manager acceptance",
        "body": review_note,
        "resume_instruction": "Accept to unblock dependents, or reopen with a concrete correction.",
        "next_checkin": str(item.get("review_requested_at") or item.get("updated_at") or "").strip(),
        "response_state": str(saved.get("response_state") or "pending").strip() or "pending",
        "response_note": str(saved.get("response_note") or review_note).strip(),
        "response_at": str(saved.get("response_at") or item.get("completed_at") or "").strip(),
        "created_at": str(saved.get("created_at") or item.get("review_requested_at") or now_iso()).strip(),
    }



def _merge_queue_request_body(item: MergeQueueItem) -> str:
    attention_summary = str(item.get("attention_summary", "")).strip()
    requested_unlocks = item.get("requested_unlocks") or []
    blockers = item.get("blockers") or []

    body_parts: list[str] = []
    if attention_summary:
        body_parts.append(attention_summary)
    if requested_unlocks:
        body_parts.append(f"requested unlocks: {summarize_list(requested_unlocks)}")
    if blockers:
        body_parts.append(f"blockers: {summarize_list(blockers)}")
    return "; ".join(body_parts)



def merge_queue_unlock_request(item: MergeQueueItem, request_state: RequestStateMap) -> A0ConsoleRequest | None:
    if not isinstance(item, dict):
        return None

    requested_unlocks = item.get("requested_unlocks") or []
    if not requested_unlocks:
        return None

    agent = str(item.get("agent", "")).strip()
    status = str(item.get("status", "")).strip() or "not_started"
    body = _merge_queue_request_body(item) or f"{agent} requests unlock"
    request_id = slugify(f"{agent}_unlock_{status}_{summarize_list(requested_unlocks)}")
    saved = _saved_request(request_state, request_id)
    return {
        "id": request_id,
        "agent": agent,
        "request_type": "unlock",
        "status": status,
        "title": f"{agent} requests unlock",
        "body": body,
        "requested_unlocks": requested_unlocks,
        "blockers": item.get("blockers") or [],
        "resume_instruction": str(item.get("resume_instruction", "")).strip(),
        "next_checkin": str(item.get("next_checkin", "")).strip(),
        "response_state": str(saved.get("response_state") or "pending").strip() or "pending",
        "response_note": str(saved.get("response_note") or "").strip(),
        "response_at": str(saved.get("response_at") or "").strip(),
        "created_at": str(saved.get("created_at") or now_iso()).strip(),
    }



def merge_queue_intervention_request(item: MergeQueueItem, request_state: RequestStateMap) -> A0ConsoleRequest | None:
    if not isinstance(item, dict):
        return None

    requested_unlocks = item.get("requested_unlocks") or []
    blockers = item.get("blockers") or []
    attention_summary = str(item.get("attention_summary", "")).strip()
    status = str(item.get("status", "")).strip() or "not_started"
    if requested_unlocks or (not blockers and not attention_summary):
        return None

    title = f"{agent} needs intervention" if (agent := str(item.get("agent", "")).strip()) else "Worker needs intervention"
    if not (status.startswith("launch_failed") or status == "stale"):
        title = f"{agent} needs A0 review"

    body = _merge_queue_request_body(item) or title
    request_id = slugify(f"{agent}_intervention_{status}_{attention_summary or summarize_list(blockers)}")
    saved = _saved_request(request_state, request_id)
    return {
        "id": request_id,
        "agent": agent,
        "request_type": "worker_intervention",
        "status": status,
        "title": title,
        "body": body,
        "requested_unlocks": [],
        "blockers": blockers,
        "resume_instruction": str(item.get("resume_instruction", "")).strip(),
        "next_checkin": str(item.get("next_checkin", "")).strip(),
        "response_state": str(saved.get("response_state") or "pending").strip() or "pending",
        "response_note": str(saved.get("response_note") or "").strip(),
        "response_at": str(saved.get("response_at") or "").strip(),
        "created_at": str(saved.get("created_at") or now_iso()).strip(),
    }



def build_a0_request_catalog(
    backlog_items: list[BacklogItem],
    merge_queue: list[MergeQueueItem],
    mailbox_catalog: TeamMailboxState | None,
    request_state: dict[str, A0ConsoleRequest] | None = None,
    messages: list[A0ConsoleMessage] | None = None,
) -> A0ConsoleState:
    normalized_request_state = request_state if isinstance(request_state, dict) else {}
    normalized_messages = messages if isinstance(messages, list) else []
    normalized_mailbox = mailbox_catalog if isinstance(mailbox_catalog, dict) else {}
    inbox = normalized_mailbox.get("a0_inbox", []) if isinstance(normalized_mailbox.get("a0_inbox", []), list) else []

    requests: list[A0ConsoleRequest] = []
    for item in backlog_items:
        plan_review = backlog_plan_review_request(item, normalized_request_state)
        if plan_review:
            requests.append(plan_review)
            continue
        task_review = backlog_task_review_request(item, normalized_request_state)
        if task_review:
            requests.append(task_review)

    for item in merge_queue:
        unlock_request = merge_queue_unlock_request(item, normalized_request_state)
        if unlock_request:
            requests.append(unlock_request)
            continue
        intervention_request = merge_queue_intervention_request(item, normalized_request_state)
        if intervention_request:
            requests.append(intervention_request)

    requests.sort(key=lambda item: (item["response_state"] != "pending", item["agent"], item["id"]))
    pending_count = sum(1 for item in requests if item["response_state"] == "pending") + len(inbox)
    return {
        "requests": requests,
        "messages": normalized_messages[-20:],
        "inbox": inbox[-20:],
        "pending_count": pending_count,
        "last_updated": now_iso(),
    }
