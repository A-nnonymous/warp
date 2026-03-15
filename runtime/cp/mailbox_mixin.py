from __future__ import annotations

from typing import Any

from .contracts import A0ConsoleState, TeamMailboxMessage, TeamMailboxState
from .constants import (
    MAILBOX_ACK_STATES,
    STATE_DIR,
    TEAM_MAILBOX_PATH,
)
from .stores import LockStore, MailboxStore
from .utils import (
    now_iso,
    slugify,
    summarize_list,
)


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
        messages = state.get("messages", [])
        pending_messages = [item for item in messages if str(item.get("ack_state") or "") != "resolved"]
        a0_messages = [
            item
            for item in pending_messages
            if str(item.get("to") or "") in {"A0", "a0", "manager", "all"} or str(item.get("scope") or "") in {"broadcast", "manager"}
        ]
        return {
            "messages": messages[-50:],
            "pending_count": len(pending_messages),
            "a0_pending_count": len(a0_messages),
            "last_updated": now_iso(),
        }

    def edit_lock_state(self) -> dict[str, Any]:
        return self.lock_store().load()

    def cleanup_status(
        self,
        runtime_state: dict[str, Any] | None = None,
        heartbeat_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        runtime_state = runtime_state or self.dashboard_runtime_state()
        heartbeat_state = heartbeat_state or self.dashboard_heartbeats_state(runtime_state=runtime_state)
        runtime_workers = {
            str(item.get("agent") or "").strip(): item
            for item in runtime_state.get("workers", [])
            if isinstance(item, dict)
        }
        heartbeat_workers = {
            str(item.get("agent") or "").strip(): item
            for item in heartbeat_state.get("agents", [])
            if isinstance(item, dict)
        }
        locks_state = self.edit_lock_state()
        plan_reviews_by_agent: dict[str, list[str]] = {}
        task_reviews_by_agent: dict[str, list[str]] = {}
        pending_plan_reviews: list[str] = []
        pending_task_reviews: list[str] = []
        for item in self.backlog_items():
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

        active_workers = sorted(
            agent for agent, worker in self.processes.items() if worker.process.poll() is None
        )

        locked_files: list[dict[str, str]] = []
        locked_files_by_owner: dict[str, list[str]] = {}
        for item in locks_state.get("locks", []):
            state = str(item.get("state") or "free").strip() or "free"
            if state == "free":
                continue
            path = str(item.get("path") or "").strip()
            owner = str(item.get("owner") or "").strip() or "unassigned"
            locked_files.append({"path": path, "owner": owner, "state": state})
            locked_files_by_owner.setdefault(owner, []).append(path)

        worker_rows = []
        for worker in self.workers:
            agent = str(worker.get("agent") or "").strip()
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
            worker_rows.append(
                {
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
            )

        blockers: list[str] = []
        if active_workers:
            blockers.append(f"active workers must be stopped: {', '.join(active_workers)}")
        if pending_plan_reviews:
            blockers.append(f"pending plan approvals: {summarize_list(pending_plan_reviews)}")
        if pending_task_reviews:
            blockers.append(f"pending task reviews: {summarize_list(pending_task_reviews)}")
        if locked_files:
            blocker_summary = summarize_list(
                [f"{item['path']} ({item['owner']})" for item in locked_files]
            )
            blockers.append(f"outstanding single-writer locks: {blocker_summary}")

        return {
            "ready": len(blockers) == 0,
            "blockers": blockers,
            "listener_active": bool(self.listener_active),
            "active_workers": active_workers,
            "pending_plan_reviews": pending_plan_reviews,
            "pending_task_reviews": pending_task_reviews,
            "locked_files": locked_files,
            "workers": worker_rows,
            "last_updated": now_iso(),
        }

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
