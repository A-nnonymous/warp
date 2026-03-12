from __future__ import annotations

import signal
import subprocess
import time
from typing import Any

from .constants import (
    BACKLOG_ACTIVE_STATUSES,
    BACKLOG_CLAIM_STATES,
    BACKLOG_COMPLETED_STATUSES,
    BACKLOG_PENDING_STATUSES,
    BACKLOG_PLAN_STATES,
    STATE_DIR,
)
from .utils import (
    dedupe_strings,
    dump_yaml,
    load_yaml,
    now_iso,
    summarize_list,
    terminate_process_tree,
)


class BacklogMixin:
    """Methods for backlog / task lifecycle and worker stop / workflow operations."""

    def backlog_items(self) -> list[dict[str, Any]]:
        return self.load_backlog_state().get("items", [])

    def default_backlog_state(self) -> dict[str, Any]:
        return {
            "project": "",
            "last_updated": "",
            "manager": "A0",
            "phase": "",
            "items": [],
        }

    def normalize_backlog_item(self, item: dict[str, Any]) -> dict[str, Any]:
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

        normalized["id"] = str(normalized.get("id") or "").strip()
        normalized["title"] = str(normalized.get("title") or normalized["id"] or "unassigned task").strip()
        normalized["task_type"] = str(normalized.get("task_type") or "default").strip() or "default"
        normalized["owner"] = str(normalized.get("owner") or "").strip()
        normalized["status"] = status
        normalized["gate"] = str(normalized.get("gate") or "").strip()
        normalized["priority"] = str(normalized.get("priority") or "").strip()
        normalized["dependencies"] = dedupe_strings(normalized.get("dependencies") or [])
        normalized["outputs"] = [str(value).strip() for value in normalized.get("outputs") or [] if str(value).strip()]
        normalized["done_when"] = [str(value).strip() for value in normalized.get("done_when") or [] if str(value).strip()]
        normalized["claim_state"] = claim_state
        normalized["claimed_by"] = claimed_by
        normalized["claimed_at"] = str(normalized.get("claimed_at") or "").strip()
        normalized["claim_note"] = str(normalized.get("claim_note") or "").strip()
        normalized["plan_required"] = plan_required
        normalized["plan_state"] = plan_state
        normalized["plan_summary"] = str(normalized.get("plan_summary") or "").strip()
        normalized["plan_review_note"] = str(normalized.get("plan_review_note") or "").strip()
        normalized["plan_reviewed_at"] = str(normalized.get("plan_reviewed_at") or "").strip()
        normalized["review_requested_at"] = str(normalized.get("review_requested_at") or "").strip()
        normalized["review_note"] = str(normalized.get("review_note") or "").strip()
        normalized["completed_at"] = str(normalized.get("completed_at") or "").strip()
        normalized["completed_by"] = str(normalized.get("completed_by") or "").strip()
        normalized["updated_at"] = str(normalized.get("updated_at") or "").strip()
        return normalized

    def load_backlog_state(self) -> dict[str, Any]:
        state = self.default_backlog_state()
        if not (STATE_DIR / "backlog.yaml").exists():
            return state
        data = load_yaml(STATE_DIR / "backlog.yaml")
        if not isinstance(data, dict):
            return state
        for key, value in data.items():
            if key != "items":
                state[key] = value
        items = data.get("items", [])
        state["items"] = [self.normalize_backlog_item(item) for item in items if isinstance(item, dict)]
        return state

    def persist_backlog_state(self, state: dict[str, Any]) -> None:
        payload = self.default_backlog_state()
        if isinstance(state, dict):
            for key, value in state.items():
                if key != "items":
                    payload[key] = value
        payload["last_updated"] = now_iso()
        items = state.get("items", []) if isinstance(state, dict) else []
        payload["items"] = [self.normalize_backlog_item(item) for item in items if isinstance(item, dict)]
        dump_yaml(STATE_DIR / "backlog.yaml", payload)

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
        if action_name not in {"claim", "release", "start", "submit_plan", "approve_plan", "reject_plan", "request_review", "complete", "reopen"}:
            raise ValueError(f"unsupported task action {action_name}")

        def mutate(item: dict[str, Any]) -> dict[str, Any]:
            next_item = dict(item)
            current_claimant = str(next_item.get("claimed_by") or "").strip()
            status = str(next_item.get("status") or "pending").strip() or "pending"
            if action_name == "claim":
                if current_claimant and current_claimant != actor and str(next_item.get("claim_state") or "") in {"claimed", "in_progress", "review"}:
                    raise ValueError(f"task {task_id} is already claimed by {current_claimant}")
                next_item["claimed_by"] = actor
                next_item["claimed_at"] = now_iso()
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
                next_item["claimed_at"] = next_item.get("claimed_at") or now_iso()
                next_item["claim_state"] = "in_progress"
                next_item["claim_note"] = note or next_item.get("claim_note") or "implementation started"
                if status in BACKLOG_PENDING_STATUSES or status == "blocked":
                    next_item["status"] = "active"
            elif action_name == "submit_plan":
                next_item["claimed_by"] = actor
                next_item["claimed_at"] = next_item.get("claimed_at") or now_iso()
                next_item["claim_state"] = "claimed"
                next_item["plan_required"] = True
                next_item["plan_state"] = "pending_review"
                next_item["plan_summary"] = note
            elif action_name == "approve_plan":
                next_item["plan_state"] = "approved"
                next_item["plan_review_note"] = note
                next_item["plan_reviewed_at"] = now_iso()
            elif action_name == "reject_plan":
                next_item["plan_state"] = "rejected"
                next_item["plan_review_note"] = note
                next_item["plan_reviewed_at"] = now_iso()
                if not next_item.get("claimed_by"):
                    next_item["claimed_by"] = actor
            elif action_name == "request_review":
                next_item["claimed_by"] = current_claimant or actor
                next_item["claim_state"] = "review"
                next_item["status"] = "review"
                next_item["review_note"] = note
                next_item["review_requested_at"] = now_iso()
            elif action_name == "complete":
                if bool(next_item.get("plan_required")) and str(next_item.get("plan_state") or "") != "approved":
                    raise ValueError(f"task {task_id} requires plan approval before completion")
                next_item["claim_state"] = "completed"
                next_item["status"] = "completed"
                next_item["completed_at"] = now_iso()
                next_item["completed_by"] = actor
                next_item["review_note"] = note or next_item.get("review_note") or "manager accepted task"
            elif action_name == "reopen":
                next_item["status"] = "pending"
                next_item["claim_state"] = "claimed" if current_claimant else "unclaimed"
                next_item["completed_at"] = ""
                next_item["completed_by"] = ""
                next_item["review_note"] = note
            return next_item

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

    def patch_workflow_item(self, task_id: str, updates: dict[str, Any], actor: str = "A0", note: str = "") -> dict[str, Any]:
        manager = str(actor or "A0").strip() or "A0"
        if manager != "A0":
            raise ValueError("workflow updates are manager-owned and must be performed by A0")
        if not isinstance(updates, dict) or not updates:
            raise ValueError("updates are required")

        allowed_scalar_fields = {
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
        allowed_list_fields = {"dependencies", "outputs", "done_when"}
        allowed_boolean_fields = {"plan_required"}
        unknown_fields = sorted(
            key for key in updates.keys() if key not in allowed_scalar_fields | allowed_list_fields | allowed_boolean_fields
        )
        if unknown_fields:
            raise ValueError(f"unsupported workflow update fields: {', '.join(unknown_fields)}")

        before = self.task_record_for_worker({"task_id": task_id})
        if not before:
            raise ValueError(f"unknown task id {task_id}")

        def mutate(item: dict[str, Any]) -> dict[str, Any]:
            next_item = dict(item)
            for field in allowed_scalar_fields:
                if field in updates:
                    next_item[field] = str(updates.get(field) or "").strip()
            for field in allowed_list_fields:
                if field in updates:
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
                next_item["claimed_at"] = now_iso()
            if not claimed_by:
                next_item["claimed_at"] = ""

            if status not in BACKLOG_COMPLETED_STATUSES:
                next_item["completed_at"] = ""
                next_item["completed_by"] = ""
            if status not in {"review"} and str(next_item.get("claim_state") or "") != "review":
                next_item["review_requested_at"] = ""
            elif not str(next_item.get("review_requested_at") or "").strip():
                next_item["review_requested_at"] = now_iso()

            if plan_state in {"approved", "rejected"}:
                next_item["plan_reviewed_at"] = now_iso()
            elif plan_state in {"none", "pending_review"}:
                next_item["plan_reviewed_at"] = ""
                if plan_state == "none":
                    next_item["plan_review_note"] = ""

            return next_item

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
