from __future__ import annotations

import signal
import subprocess
import time
from typing import Any

from .constants import STATE_DIR
from .services import apply_task_action, apply_workflow_patch, summarize_workflow_patch, validate_workflow_updates
from .stores import BacklogStore
from .utils import dedupe_strings, now_iso, summarize_list, terminate_process_tree


class BacklogMixin:
    """Methods for backlog / task lifecycle and worker stop / workflow operations."""

    def backlog_store(self) -> BacklogStore:
        return BacklogStore(STATE_DIR / "backlog.yaml")

    def backlog_items(self) -> list[dict[str, Any]]:
        return self.load_backlog_state().get("items", [])

    def default_backlog_state(self) -> dict[str, Any]:
        return self.backlog_store().default_state()

    def normalize_backlog_item(self, item: dict[str, Any]) -> dict[str, Any]:
        return self.backlog_store().normalize_item(item)

    def load_backlog_state(self) -> dict[str, Any]:
        return self.backlog_store().load()

    def persist_backlog_state(self, state: dict[str, Any]) -> None:
        self.backlog_store().persist(state)

    def update_backlog_item(self, task_id: str, updater: Any) -> dict[str, Any]:
        with self.lock:
            backlog = self.load_backlog_state()
            items = backlog.get("items", [])
            for index, item in enumerate(items):
                if str(item.get("id") or "").strip() != task_id:
                    continue
                next_item = updater(dict(item))
                if not isinstance(next_item, dict):
                    raise ValueError("task update must return a mapping")
                next_item["updated_at"] = now_iso()
                items[index] = self.normalize_backlog_item(next_item)
                backlog["items"] = items
                self.persist_backlog_state(backlog)
                return items[index]
        raise ValueError(f"unknown task id {task_id}")

    def perform_task_action(self, task_id: str, action: str, agent: str = "", note: str = "") -> dict[str, Any]:
        actor = str(agent or "A0").strip() or "A0"
        action_name = str(action or "").strip()

        def mutate(item: dict[str, Any]) -> dict[str, Any]:
            return apply_task_action(
                item,
                task_id=task_id,
                action=action_name,
                actor=actor,
                note=note,
                current_time=now_iso(),
            )

        updated = self.update_backlog_item(task_id, mutate)
        topic_map = {
            "submit_plan": ("A0", "review_request", "manager"),
            "request_review": ("A0", "handoff", "manager"),
            "approve_plan": (updated.get("claimed_by") or updated.get("owner") or "A1", "status_note", "direct"),
            "reject_plan": (updated.get("claimed_by") or updated.get("owner") or "A1", "design_question", "direct"),
            "complete": (updated.get("claimed_by") or updated.get("owner") or "A1", "status_note", "direct"),
            "reopen": (updated.get("claimed_by") or updated.get("owner") or "A1", "blocker", "direct"),
        }
        if action_name in topic_map and note:
            recipient, topic, scope = topic_map[action_name]
            sender = actor if action_name not in {"approve_plan", "reject_plan", "complete", "reopen"} else "A0"
            self.append_team_mailbox_message(sender, str(recipient), topic, note, [task_id], scope)
        self.last_event = f"task:{action_name}:{task_id}"
        return updated

    def stop_worker_locked(self, agent: str, note: str = "") -> dict[str, Any]:
        worker_config = next((item for item in self.workers if str(item.get("agent") or "").strip() == agent), None)
        if worker_config is None:
            raise ValueError(f"unknown worker {agent}")
        if agent == "A0":
            raise ValueError("A0 cannot be shut down through the worker shutdown path")

        process_entry = self.processes.get(agent)
        runtime_entry = next(
            (
                item
                for item in self.dashboard_runtime_state().get("workers", [])
                if isinstance(item, dict) and str(item.get("agent") or "").strip() == agent
            ),
            {},
        )
        stopped = False
        already_stopped = True
        pool_name = str(runtime_entry.get("resource_pool") or worker_config.get("resource_pool") or "unassigned")
        provider_name = str(runtime_entry.get("provider") or worker_config.get("provider") or "unassigned")
        model = str(runtime_entry.get("model") or worker_config.get("model") or "unassigned")
        if process_entry is not None:
            already_stopped = process_entry.process.poll() is not None
            if process_entry.process.poll() is None:
                terminate_process_tree(process_entry.process.pid, signal.SIGTERM)
                try:
                    process_entry.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    terminate_process_tree(process_entry.process.pid, signal.SIGKILL)
                    process_entry.process.wait(timeout=5)
                stopped = True
            process_entry.log_handle.close()
            pool_name = process_entry.resource_pool
            provider_name = process_entry.provider
            model = process_entry.model
            del self.processes[agent]

        self.update_heartbeat(agent, "offline", "manager_stop", note or "none")
        self.update_runtime_entry(worker_config, pool_name, provider_name, model, "stopped")
        self.append_team_mailbox_message(
            "A0",
            agent,
            "status_note",
            note or "A0 requested a clean worker shutdown.",
            [str(worker_config.get("task_id") or "").strip()] if str(worker_config.get("task_id") or "").strip() else [],
            "direct",
        )
        return {"ok": True, "agent": agent, "stopped": stopped, "already_stopped": already_stopped and not stopped}

    def stop_worker(self, agent: str, note: str = "") -> dict[str, Any]:
        with self.lock:
            result = self.stop_worker_locked(agent, note)
            self.last_event = f"stop:{agent}"
            self.write_session_state()
            result["cleanup"] = self.cleanup_status()
            return result

    def summarize_workflow_patch(self, before: dict[str, Any], after: dict[str, Any]) -> str:
        return summarize_workflow_patch(before, after)

    def patch_workflow_item(self, task_id: str, updates: dict[str, Any], actor: str = "A0", note: str = "") -> dict[str, Any]:
        manager = str(actor or "A0").strip() or "A0"
        if manager != "A0":
            raise ValueError("workflow updates are manager-owned and must be performed by A0")
        validate_workflow_updates(updates)

        before = self.task_record_for_worker({"task_id": task_id})
        if not before:
            raise ValueError(f"unknown task id {task_id}")

        def mutate(item: dict[str, Any]) -> dict[str, Any]:
            return apply_workflow_patch(item, updates=updates, current_time=now_iso())

        updated = self.update_backlog_item(task_id, mutate)
        summary = self.summarize_workflow_patch(before, updated)
        recipients = dedupe_strings(
            [
                str(before.get("owner") or "").strip(),
                str(before.get("claimed_by") or "").strip(),
                str(updated.get("owner") or "").strip(),
                str(updated.get("claimed_by") or "").strip(),
            ]
        )
        recipients = [recipient for recipient in recipients if recipient and recipient != "A0"]
        if recipients:
            topic = "design_question" if str(updated.get("plan_state") or "") == "rejected" else "status_note"
            if len(recipients) == 1:
                self.append_team_mailbox_message(
                    "A0",
                    recipients[0],
                    topic,
                    note or f"A0 updated {task_id}: {summary}",
                    [task_id],
                    "direct",
                )
            else:
                self.append_team_mailbox_message(
                    "A0",
                    "all",
                    topic,
                    note or f"A0 updated {task_id}: {summary}",
                    [task_id],
                    "broadcast",
                )
        self.last_event = f"workflow:update:{task_id}"
        return updated

    def confirm_team_cleanup(self, note: str = "", release_listener: bool = False) -> dict[str, Any]:
        with self.lock:
            cleanup = self.cleanup_status()
            if not cleanup.get("ready"):
                raise ValueError(f"cleanup blocked: {summarize_list(cleanup.get('blockers', []))}")
            self.append_team_mailbox_message(
                "A0",
                "all",
                "status_note",
                note or "Cleanup gate passed; listener shutdown is now safe.",
                [],
                "broadcast",
            )
            listener_port = self.listen_port
            listener_active = bool(self.listener_active)
            listener_release_requested = bool(release_listener and listener_active)
            self.last_event = "cleanup:ready:auto-release" if listener_release_requested else "cleanup:ready"
            self.write_session_state()
            return {
                "cleanup": cleanup,
                "listener_active": listener_active,
                "listener_port": listener_port,
                "listener_release_requested": listener_release_requested,
                "listener_released": bool(release_listener and not listener_active),
            }

    def release_listener_after_cleanup(self, delay_seconds: float = 0.15) -> None:
        time.sleep(delay_seconds)
        self.enter_silent_mode()
