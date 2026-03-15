from __future__ import annotations

from pathlib import Path
from typing import Any

from ..constants import MAILBOX_ACK_STATES
from ..contracts import TeamMailboxMessage, TeamMailboxState
from ..utils import dedupe_strings, dump_yaml, load_yaml, now_iso, slugify


class MailboxStore:
    def __init__(self, path: Path):
        self.path = path

    @staticmethod
    def default_state() -> TeamMailboxState:
        return {"messages": []}

    @staticmethod
    def normalize_message(message: dict[str, Any]) -> TeamMailboxMessage:
        normalized = dict(message)
        topic = str(normalized.get("topic") or "status_note").strip() or "status_note"
        scope = str(normalized.get("scope") or "direct").strip() or "direct"
        if scope not in {"direct", "broadcast", "manager"}:
            scope = "direct"
        ack_state = str(normalized.get("ack_state") or "pending").strip() or "pending"
        if ack_state not in MAILBOX_ACK_STATES:
            ack_state = "pending"
        sender = str(normalized.get("from") or "unknown").strip() or "unknown"
        recipient = str(normalized.get("to") or ("A0" if scope == "manager" else "all")).strip() or "all"
        created_at = str(normalized.get("created_at") or now_iso()).strip() or now_iso()
        message_id = str(normalized.get("id") or "").strip() or slugify(f"{sender}_{recipient}_{topic}_{created_at}")
        return {
            **normalized,
            "id": message_id,
            "from": sender,
            "to": recipient,
            "scope": scope,
            "topic": topic,
            "body": str(normalized.get("body") or "").strip(),
            "related_task_ids": dedupe_strings(normalized.get("related_task_ids") or []),
            "created_at": created_at,
            "ack_state": ack_state,
            "resolution_note": str(normalized.get("resolution_note") or "").strip(),
            "acked_at": str(normalized.get("acked_at") or "").strip(),
        }

    def load(self) -> TeamMailboxState:
        if not self.path.exists():
            return self.default_state()
        data = load_yaml(self.path)
        if not isinstance(data, dict):
            return self.default_state()
        messages = data.get("messages", [])
        return {"messages": [self.normalize_message(item) for item in messages if isinstance(item, dict)]}

    def persist(self, state: dict[str, Any]) -> TeamMailboxState:
        messages = state.get("messages", []) if isinstance(state, dict) else []
        payload: TeamMailboxState = {
            "messages": [self.normalize_message(item) for item in messages if isinstance(item, dict)]
        }
        dump_yaml(self.path, payload)
        return payload
