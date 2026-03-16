from __future__ import annotations

from typing import TypedDict

from ..contracts import BacklogItem
from ..utils import dedupe_strings


class MailboxNotification(TypedDict):
    sender: str
    recipient: str
    topic: str
    body: str
    related_task_ids: list[str]
    scope: str


TASK_ACTION_NOTIFICATION_ROUTES: dict[str, tuple[str, str, str]] = {
    "submit_plan": ("A0", "review_request", "manager"),
    "request_review": ("A0", "handoff", "manager"),
    "approve_plan": ("assignee", "status_note", "direct"),
    "reject_plan": ("assignee", "design_question", "direct"),
    "complete": ("assignee", "status_note", "direct"),
    "reopen": ("assignee", "blocker", "direct"),
}


def mailbox_notification(
    sender: str,
    recipient: str,
    topic: str,
    body: str,
    related_task_ids: list[str] | None = None,
    scope: str = "direct",
) -> MailboxNotification:
    return {
        "sender": str(sender or "").strip(),
        "recipient": str(recipient or "").strip(),
        "topic": str(topic or "").strip(),
        "body": str(body or "").strip(),
        "related_task_ids": [str(task_id).strip() for task_id in (related_task_ids or []) if str(task_id).strip()],
        "scope": str(scope or "direct").strip() or "direct",
    }


def task_action_notification(
    *,
    task_id: str,
    action: str,
    actor: str,
    note: str,
    updated: BacklogItem,
) -> MailboxNotification | None:
    if not str(note or "").strip():
        return None
    route = TASK_ACTION_NOTIFICATION_ROUTES.get(str(action or "").strip())
    if route is None:
        return None
    recipient_name, topic, scope = route
    assignee = str(updated.get("claimed_by") or updated.get("owner") or "A1").strip() or "A1"
    recipient = assignee if recipient_name == "assignee" else recipient_name
    sender = "A0" if str(action or "").strip() in {"approve_plan", "reject_plan", "complete", "reopen"} else str(actor or "A0").strip() or "A0"
    return mailbox_notification(sender, recipient, topic, note, [task_id], scope)


def workflow_patch_notifications(
    *,
    task_id: str,
    before: BacklogItem,
    updated: BacklogItem,
    summary: str,
    note: str,
) -> list[MailboxNotification]:
    recipients = [
        recipient
        for recipient in dedupe_strings(
            [
                str(before.get("owner") or "").strip(),
                str(before.get("claimed_by") or "").strip(),
                str(updated.get("owner") or "").strip(),
                str(updated.get("claimed_by") or "").strip(),
            ]
        )
        if recipient and recipient != "A0"
    ]
    if not recipients:
        return []
    topic = "design_question" if str(updated.get("plan_state") or "").strip() == "rejected" else "status_note"
    body = str(note or "").strip() or f"A0 updated {task_id}: {summary}"
    if len(recipients) == 1:
        return [mailbox_notification("A0", recipients[0], topic, body, [task_id], "direct")]
    return [mailbox_notification("A0", "all", topic, body, [task_id], "broadcast")]
