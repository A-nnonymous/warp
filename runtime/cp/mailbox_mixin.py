from __future__ import annotations

from typing import Any

from .contracts import A0ConsoleState, CleanupState, HeartbeatState, RuntimeState, TeamMailboxMessage, TeamMailboxState
from .constants import (
    MAILBOX_ACK_STATES,
    STATE_DIR,
    TEAM_MAILBOX_PATH,
)
from .services import build_team_mailbox_catalog, cleanup_status_view
from .stores import LockStore, MailboxStore
from .utils import now_iso, slugify


class MailboxMixin:
    """Methods for team mailbox, edit locks, and cleanup status."""

    def mailbox_store(self) -> MailboxStore:
        return MailboxStore(TEAM_MAILBOX_PATH)

    def lock_store(self) -> LockStore:
        return LockStore(STATE_DIR / "edit_locks.yaml")

    def default_team_mailbox_state(self) -> TeamMailboxState:
        return self.mailbox_store().default_state()

    def normalize_team_mailbox_message(self, message: dict[str, Any]) -> TeamMailboxMessage:
        return self.mailbox_store().normalize_message(message)

    def load_team_mailbox_state(self) -> TeamMailboxState:
        return self.mailbox_store().load()

    def persist_team_mailbox_state(self, state: TeamMailboxState) -> None:
        self.mailbox_store().persist(state)

    def append_team_mailbox_message(
        self,
        sender: str,
        recipient: str,
        topic: str,
        body: str,
        related_task_ids: list[str] | None = None,
        scope: str = "direct",
    ) -> TeamMailboxMessage:
        with self.lock:
            state = self.load_team_mailbox_state()
            message = self.normalize_team_mailbox_message(
                {
                    "from": sender,
                    "to": recipient,
                    "scope": scope,
                    "topic": topic,
                    "body": body,
                    "related_task_ids": related_task_ids or [],
                    "created_at": now_iso(),
                }
            )
            messages = state.setdefault("messages", [])
            messages.append(message)
            state["messages"] = messages[-200:]
            self.persist_team_mailbox_state(state)
            return message

    def acknowledge_team_mailbox_message(self, message_id: str, ack_state: str, resolution_note: str = "") -> TeamMailboxMessage:
        if ack_state not in MAILBOX_ACK_STATES:
            raise ValueError(f"invalid ack state {ack_state}")
        with self.lock:
            state = self.load_team_mailbox_state()
            messages = state.get("messages", [])
            for index, item in enumerate(messages):
                if str(item.get("id") or "").strip() != message_id:
                    continue
                updated = dict(item)
                updated["ack_state"] = ack_state
                updated["acked_at"] = now_iso()
                if resolution_note:
                    updated["resolution_note"] = resolution_note
                messages[index] = self.normalize_team_mailbox_message(updated)
                state["messages"] = messages
                self.persist_team_mailbox_state(state)
                return messages[index]
        raise ValueError(f"unknown message id {message_id}")

    def team_mailbox_catalog(self) -> TeamMailboxState:
        state = self.load_team_mailbox_state()
        return build_team_mailbox_catalog(state.get("messages", []))

    def edit_lock_state(self) -> dict[str, Any]:
        return self.lock_store().load()

    def cleanup_status(
        self,
        runtime_state: RuntimeState | None = None,
        heartbeat_state: HeartbeatState | None = None,
    ) -> CleanupState:
        runtime_state = runtime_state or self.dashboard_runtime_state()
        heartbeat_state = heartbeat_state or self.dashboard_heartbeats_state(runtime_state=runtime_state)
        active_workers = sorted(agent for agent, worker in self.processes.items() if worker.process.poll() is None)
        return cleanup_status_view(
            self.workers,
            runtime_state,
            heartbeat_state,
            self.backlog_items(),
            self.edit_lock_state(),
            active_workers,
            self.listener_active,
        )

    def record_a0_user_message(self, message: str, request_id: str = "", action: str = "note") -> A0ConsoleState:
        with self.lock:
            stored = self.load_manager_console_state()
            requests = stored.setdefault("requests", {})
            messages = stored.setdefault("messages", [])
            timestamp = now_iso()
            if request_id:
                entry = requests.setdefault(request_id, {})
                entry["response_state"] = action
                entry["response_note"] = message
                entry["response_at"] = timestamp
                entry.setdefault("created_at", timestamp)
            messages.append(
                {
                    "id": slugify(f"{request_id or 'note'}_{timestamp}_{len(messages)}"),
                    "direction": "user_to_a0",
                    "request_id": request_id,
                    "action": action,
                    "body": message,
                    "created_at": timestamp,
                }
            )
            stored["messages"] = messages[-50:]
            self.persist_manager_console_state(stored)
            self.last_event = f"a0_message:{action}:{request_id or 'general'}"
            heartbeat_state = self.dashboard_heartbeats_state()
            merge_queue = self.merge_queue()
            return self.a0_request_catalog(merge_queue, heartbeat_state)
