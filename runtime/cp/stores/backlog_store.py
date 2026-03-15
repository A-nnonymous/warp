from __future__ import annotations

from pathlib import Path
from typing import Any

from ..constants import (
    BACKLOG_ACTIVE_STATUSES,
    BACKLOG_CLAIM_STATES,
    BACKLOG_COMPLETED_STATUSES,
    BACKLOG_PENDING_STATUSES,
    BACKLOG_PLAN_STATES,
)
from ..contracts import BacklogItem, BacklogState
from ..utils import dedupe_strings, dump_yaml, load_yaml, now_iso


class BacklogStore:
    def __init__(self, path: Path):
        self.path = path

    @staticmethod
    def default_state() -> BacklogState:
        return {
            "project": "",
            "last_updated": "",
            "manager": "A0",
            "phase": "",
            "items": [],
        }

    @staticmethod
    def normalize_item(item: dict[str, Any]) -> BacklogItem:
        normalized = dict(item)
        status = str(normalized.get("status") or "pending").strip() or "pending"
        claim_state = str(normalized.get("claim_state") or "").strip()
        claimed_by = str(normalized.get("claimed_by") or "").strip()
        if claim_state not in BACKLOG_CLAIM_STATES:
            if status in BACKLOG_COMPLETED_STATUSES:
                claim_state = "completed"
            elif status == "review":
                claim_state = "review"
            elif status in BACKLOG_ACTIVE_STATUSES:
                claim_state = "in_progress"
            elif claimed_by:
                claim_state = "claimed"
            else:
                claim_state = "unclaimed"
        if claim_state == "completed" and status not in BACKLOG_COMPLETED_STATUSES:
            status = "completed"
        elif claim_state == "review":
            status = "review"
        elif claim_state == "in_progress" and status in BACKLOG_PENDING_STATUSES:
            status = "active"

        plan_required = bool(normalized.get("plan_required", False))
        plan_state = str(normalized.get("plan_state") or "none").strip() or "none"
        if plan_state not in BACKLOG_PLAN_STATES:
            plan_state = "none"

        return {
            **normalized,
            "id": str(normalized.get("id") or "").strip(),
            "title": str(normalized.get("title") or normalized.get("id") or "unassigned task").strip(),
            "task_type": str(normalized.get("task_type") or "default").strip() or "default",
            "owner": str(normalized.get("owner") or "").strip(),
            "status": status,
            "gate": str(normalized.get("gate") or "").strip(),
            "priority": str(normalized.get("priority") or "").strip(),
            "dependencies": dedupe_strings(normalized.get("dependencies") or []),
            "outputs": [str(value).strip() for value in normalized.get("outputs") or [] if str(value).strip()],
            "done_when": [str(value).strip() for value in normalized.get("done_when") or [] if str(value).strip()],
            "claim_state": claim_state,
            "claimed_by": claimed_by,
            "claimed_at": str(normalized.get("claimed_at") or "").strip(),
            "claim_note": str(normalized.get("claim_note") or "").strip(),
            "plan_required": plan_required,
            "plan_state": plan_state,
            "plan_summary": str(normalized.get("plan_summary") or "").strip(),
            "plan_review_note": str(normalized.get("plan_review_note") or "").strip(),
            "plan_reviewed_at": str(normalized.get("plan_reviewed_at") or "").strip(),
            "review_requested_at": str(normalized.get("review_requested_at") or "").strip(),
            "review_note": str(normalized.get("review_note") or "").strip(),
            "completed_at": str(normalized.get("completed_at") or "").strip(),
            "completed_by": str(normalized.get("completed_by") or "").strip(),
            "updated_at": str(normalized.get("updated_at") or "").strip(),
        }

    def load(self) -> BacklogState:
        state = self.default_state()
        if not self.path.exists():
            return state
        data = load_yaml(self.path)
        if not isinstance(data, dict):
            return state
        for key, value in data.items():
            if key != "items":
                state[key] = value
        items = data.get("items", [])
        state["items"] = [self.normalize_item(item) for item in items if isinstance(item, dict)]
        return state

    def persist(self, state: dict[str, Any]) -> BacklogState:
        payload = self.default_state()
        if isinstance(state, dict):
            for key, value in state.items():
                if key != "items":
                    payload[key] = value
        items = state.get("items", []) if isinstance(state, dict) else []
        payload["items"] = [self.normalize_item(item) for item in items if isinstance(item, dict)]
        payload["last_updated"] = now_iso()
        dump_yaml(self.path, payload)
        return payload
