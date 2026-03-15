from __future__ import annotations

from typing import Any

from ..constants import BACKLOG_COMPLETED_STATUSES, BACKLOG_PENDING_STATUSES
from ..contracts import BacklogItem
from ..utils import dedupe_strings, summarize_list

TASK_ACTIONS = {
    "claim",
    "release",
    "start",
    "submit_plan",
    "approve_plan",
    "reject_plan",
    "request_review",
    "complete",
    "reopen",
}

WORKFLOW_SCALAR_FIELDS = {
    "title",
    "task_type",
    "owner",
    "status",
    "gate",
    "priority",
    "claim_state",
    "claimed_by",
    "claim_note",
    "plan_state",
    "plan_summary",
    "plan_review_note",
    "review_note",
}
WORKFLOW_LIST_FIELDS = {"dependencies", "outputs", "done_when"}
WORKFLOW_BOOLEAN_FIELDS = {"plan_required"}
WORKFLOW_ALLOWED_FIELDS = WORKFLOW_SCALAR_FIELDS | WORKFLOW_LIST_FIELDS | WORKFLOW_BOOLEAN_FIELDS


def apply_task_action(
    item: dict[str, Any],
    *,
    task_id: str,
    action: str,
    actor: str,
    note: str,
    current_time: str,
) -> BacklogItem:
    action_name = str(action or "").strip()
    if action_name not in TASK_ACTIONS:
        raise ValueError(f"unsupported task action {action_name}")

    next_item: BacklogItem = dict(item)
    current_claimant = str(next_item.get("claimed_by") or "").strip()
    status = str(next_item.get("status") or "pending").strip() or "pending"

    if action_name == "claim":
        if current_claimant and current_claimant != actor and str(next_item.get("claim_state") or "") in {"claimed", "in_progress", "review"}:
            raise ValueError(f"task {task_id} is already claimed by {current_claimant}")
        next_item["claimed_by"] = actor
        next_item["claimed_at"] = current_time
        next_item["claim_state"] = "claimed"
        next_item["claim_note"] = note
    elif action_name == "release":
        if current_claimant and current_claimant != actor and actor != "A0":
            raise ValueError(f"task {task_id} is claimed by {current_claimant}")
        next_item["claimed_by"] = ""
        next_item["claimed_at"] = ""
        next_item["claim_note"] = note
        next_item["claim_state"] = "unclaimed"
        if status in {"active", "in_progress", "review"}:
            next_item["status"] = "pending"
    elif action_name == "start":
        next_item["claimed_by"] = actor
        next_item["claimed_at"] = str(next_item.get("claimed_at") or "").strip() or current_time
        next_item["claim_state"] = "in_progress"
        next_item["claim_note"] = note or str(next_item.get("claim_note") or "").strip() or "implementation started"
        if status in BACKLOG_PENDING_STATUSES or status == "blocked":
            next_item["status"] = "active"
    elif action_name == "submit_plan":
        next_item["claimed_by"] = actor
        next_item["claimed_at"] = str(next_item.get("claimed_at") or "").strip() or current_time
        next_item["claim_state"] = "claimed"
        next_item["plan_required"] = True
        next_item["plan_state"] = "pending_review"
        next_item["plan_summary"] = note
    elif action_name == "approve_plan":
        next_item["plan_state"] = "approved"
        next_item["plan_review_note"] = note
        next_item["plan_reviewed_at"] = current_time
    elif action_name == "reject_plan":
        next_item["plan_state"] = "rejected"
        next_item["plan_review_note"] = note
        next_item["plan_reviewed_at"] = current_time
        if not next_item.get("claimed_by"):
            next_item["claimed_by"] = actor
    elif action_name == "request_review":
        next_item["claimed_by"] = current_claimant or actor
        next_item["claim_state"] = "review"
        next_item["status"] = "review"
        next_item["review_note"] = note
        next_item["review_requested_at"] = current_time
    elif action_name == "complete":
        if bool(next_item.get("plan_required")) and str(next_item.get("plan_state") or "") != "approved":
            raise ValueError(f"task {task_id} requires plan approval before completion")
        next_item["claim_state"] = "completed"
        next_item["status"] = "completed"
        next_item["completed_at"] = current_time
        next_item["completed_by"] = actor
        next_item["review_note"] = note or str(next_item.get("review_note") or "").strip() or "manager accepted task"
    elif action_name == "reopen":
        next_item["status"] = "pending"
        next_item["claim_state"] = "claimed" if current_claimant else "unclaimed"
        next_item["completed_at"] = ""
        next_item["completed_by"] = ""
        next_item["review_note"] = note

    return next_item


def summarize_workflow_patch(before: dict[str, Any], after: dict[str, Any]) -> str:
    fields = [
        ("owner", "owner"),
        ("claimed_by", "claimed by"),
        ("status", "status"),
        ("claim_state", "claim state"),
        ("plan_state", "plan state"),
        ("gate", "gate"),
        ("title", "title"),
    ]
    changes: list[str] = []
    for field, label in fields:
        previous = str(before.get(field) or "").strip()
        current = str(after.get(field) or "").strip()
        if previous != current:
            changes.append(f"{label}: {previous or 'empty'} -> {current or 'empty'}")
    previous_dependencies = dedupe_strings(before.get("dependencies") or [])
    current_dependencies = dedupe_strings(after.get("dependencies") or [])
    if previous_dependencies != current_dependencies:
        changes.append(
            f"dependencies: {summarize_list(previous_dependencies) or 'none'} -> {summarize_list(current_dependencies) or 'none'}"
        )
    previous_plan = str(before.get("plan_summary") or "").strip()
    current_plan = str(after.get("plan_summary") or "").strip()
    if previous_plan != current_plan:
        changes.append("plan summary updated")
    return "; ".join(changes) if changes else "workflow updated"


def validate_workflow_updates(updates: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(updates, dict) or not updates:
        raise ValueError("updates are required")
    unknown_fields = sorted(key for key in updates.keys() if key not in WORKFLOW_ALLOWED_FIELDS)
    if unknown_fields:
        raise ValueError(f"unsupported workflow update fields: {', '.join(unknown_fields)}")
    return updates


def apply_workflow_patch(item: dict[str, Any], *, updates: dict[str, Any], current_time: str) -> BacklogItem:
    validate_workflow_updates(updates)
    next_item: BacklogItem = dict(item)

    for field in WORKFLOW_SCALAR_FIELDS:
        if field in updates:
            next_item[field] = str(updates.get(field) or "").strip()
    for field in WORKFLOW_LIST_FIELDS:
        if field not in updates:
            continue
        value = updates.get(field) or []
        if isinstance(value, str):
            next_item[field] = dedupe_strings([part.strip() for part in value.split(",")])
        elif isinstance(value, list):
            next_item[field] = dedupe_strings(value)
        else:
            raise ValueError(f"workflow field {field} must be a list or comma-separated string")
    if "plan_required" in updates:
        next_item["plan_required"] = bool(updates.get("plan_required"))

    claimed_by = str(next_item.get("claimed_by") or "").strip()
    status = str(next_item.get("status") or "pending").strip() or "pending"
    plan_state = str(next_item.get("plan_state") or "none").strip() or "none"

    if claimed_by and not str(next_item.get("claimed_at") or "").strip():
        next_item["claimed_at"] = current_time
    if not claimed_by:
        next_item["claimed_at"] = ""

    if status not in BACKLOG_COMPLETED_STATUSES:
        next_item["completed_at"] = ""
        next_item["completed_by"] = ""
    if status not in {"review"} and str(next_item.get("claim_state") or "") != "review":
        next_item["review_requested_at"] = ""
    elif not str(next_item.get("review_requested_at") or "").strip():
        next_item["review_requested_at"] = current_time

    if plan_state in {"approved", "rejected"}:
        next_item["plan_reviewed_at"] = current_time
    elif plan_state in {"none", "pending_review"}:
        next_item["plan_reviewed_at"] = ""
        if plan_state == "none":
            next_item["plan_review_note"] = ""

    return next_item
