from __future__ import annotations

import json
import os
import time
from typing import Any

from .constants import (
    PROVIDER_STATS_PATH,
    MANAGER_CONSOLE_PATH,
    REPO_ROOT,
    SESSION_STATE,
    STATE_DIR,
)
from .network import session_state_path_for_port
from .telemetry import read_log_telemetry
from .utils import (
    dump_yaml,
    load_yaml,
    now_iso,
    summarize_list,
)


class StateMixin:
    """Methods for runtime state persistence, heartbeats, telemetry, monitoring, and cleanup coordination."""

    def runtime_worker_entries(self) -> list[dict[str, Any]]:
        runtime = load_yaml(STATE_DIR / "agent_runtime.yaml")
        items = runtime.get("workers", [])
        return items if isinstance(items, list) else []

    def update_runtime_entry(
        self,
        worker: dict[str, Any],
        pool_name: str,
        provider_name: str,
        model: str,
        status: str,
        recursion_guard: str | None = None,
        launch_wrapper: str | None = None,
    ) -> None:
        runtime_path = STATE_DIR / "agent_runtime.yaml"
        runtime = load_yaml(runtime_path)
        workers = runtime.get("workers", [])
        target = None
        for entry in workers:
            if entry.get("agent") == worker["agent"]:
                target = entry
                break
        if target is None:
            target = {"agent": worker["agent"]}
            workers.append(target)
        target.update(
            {
                "repository_name": self.project.get("repository_name", "target-repo"),
                "resource_pool": pool_name,
                "provider": provider_name,
                "model": model,
                "recursion_guard": (
                    recursion_guard if recursion_guard is not None else target.get("recursion_guard", "")
                ),
                "launch_wrapper": launch_wrapper if launch_wrapper is not None else target.get("launch_wrapper", ""),
                "launch_owner": worker.get("launch_owner", "manager"),
                "local_workspace_root": self.project.get("local_repo_root", str(REPO_ROOT)),
                "repository_root": str(REPO_ROOT),
                "worktree_path": worker["worktree_path"],
                "branch": worker["branch"],
                "merge_target": self.integration_branch(),
                "environment_type": worker.get("environment_type", "uv"),
                "environment_path": worker.get("environment_path", "unassigned"),
                "sync_command": worker.get("sync_command", "uv sync"),
                "test_command": worker.get("test_command", "unassigned"),
                "submit_strategy": worker.get("submit_strategy", "patch_handoff"),
                "git_author_name": self.worker_git_identity(worker).get("name", ""),
                "git_author_email": self.worker_git_identity(worker).get("email", ""),
                "status": status,
            }
        )
        runtime["last_updated"] = now_iso()
        dump_yaml(runtime_path, runtime)

    def update_heartbeat(self, agent: str, state: str, evidence: str, escalation: str) -> None:
        heartbeats_path = STATE_DIR / "heartbeats.yaml"
        heartbeats = load_yaml(heartbeats_path)
        entries = heartbeats.get("agents", [])
        for entry in entries:
            if entry.get("agent") == agent:
                entry["state"] = state
                entry["last_seen"] = now_iso()
                entry["evidence"] = evidence
                entry["expected_next_checkin"] = "while worker process is alive"
                entry["escalation"] = escalation
                break
        heartbeats["last_updated"] = now_iso()
        dump_yaml(heartbeats_path, heartbeats)

    def load_provider_stats(self) -> dict[str, dict[str, Any]]:
        data = load_yaml(PROVIDER_STATS_PATH) if PROVIDER_STATS_PATH.exists() else {}
        if not isinstance(data, dict):
            return {}
        stats: dict[str, dict[str, Any]] = {}
        for pool_name, entry in data.items():
            if isinstance(entry, dict):
                stats[str(pool_name)] = {**self.default_provider_stat_entry(), **entry}
        return stats

    def persist_provider_stats(self) -> None:
        PROVIDER_STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
        dump_yaml(PROVIDER_STATS_PATH, self.provider_stats)

    def load_manager_console_state(self) -> dict[str, Any]:
        if not MANAGER_CONSOLE_PATH.exists():
            return {"requests": {}, "messages": []}
        data = load_yaml(MANAGER_CONSOLE_PATH)
        if not isinstance(data, dict):
            return {"requests": {}, "messages": []}
        requests = data.get("requests", {})
        messages = data.get("messages", [])
        return {
            "requests": requests if isinstance(requests, dict) else {},
            "messages": messages if isinstance(messages, list) else [],
        }

    def persist_manager_console_state(self, state: dict[str, Any]) -> None:
        MANAGER_CONSOLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        dump_yaml(MANAGER_CONSOLE_PATH, state)

    def worker_process_telemetry(self, worker) -> dict[str, Any]:
        return read_log_telemetry(worker.log_path)

    def pool_usage_summary(self, pool_name: str) -> dict[str, Any]:
        running_agents: list[dict[str, Any]] = []
        usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        progress_values: list[int] = []
        last_activity_at = ""
        for agent, worker in self.processes.items():
            if worker.resource_pool != pool_name or worker.process.poll() is not None:
                continue
            telemetry = self.worker_process_telemetry(worker)
            running_agents.append(
                {
                    "agent": agent,
                    "progress_pct": telemetry.get("progress_pct"),
                    "phase": telemetry.get("phase", ""),
                    "total_tokens": telemetry.get("usage", {}).get("total_tokens", 0),
                }
            )
            for key in usage:
                usage[key] += int(telemetry.get("usage", {}).get(key, 0) or 0)
            progress_value = telemetry.get("progress_pct")
            if isinstance(progress_value, int):
                progress_values.append(progress_value)
            activity = str(telemetry.get("last_activity_at", "")).strip()
            if activity and activity > last_activity_at:
                last_activity_at = activity
        return {
            "running_agents": running_agents,
            "usage": usage,
            "progress_pct": round(sum(progress_values) / len(progress_values)) if progress_values else None,
            "last_activity_at": last_activity_at,
        }

    def process_snapshot(self) -> dict[str, Any]:
        snapshot: dict[str, Any] = {}
        for agent, worker in self.processes.items():
            telemetry = self.worker_process_telemetry(worker)
            snapshot[agent] = {
                "resource_pool": worker.resource_pool,
                "provider": worker.provider,
                "model": worker.model,
                "pid": worker.process.pid,
                "alive": worker.process.poll() is None,
                "returncode": worker.process.poll(),
                "wrapper_path": worker.wrapper_path,
                "recursion_guard": worker.recursion_guard,
                "worktree_path": str(worker.worktree_path),
                "log_path": str(worker.log_path),
                "command": worker.command,
                "phase": telemetry.get("phase", ""),
                "progress_pct": telemetry.get("progress_pct"),
                "last_activity_at": telemetry.get("last_activity_at", ""),
                "last_log_line": telemetry.get("last_line", ""),
                "usage": telemetry.get("usage", {}),
            }
        return snapshot

    def monitor_loop(self) -> None:
        while not self.stop_event.is_set():
            with self.lock:
                for agent, worker in list(self.processes.items()):
                    returncode = worker.process.poll()
                    if returncode is None:
                        self.update_heartbeat(agent, "healthy", "process_running", "none")
                        runtime_entry = next((w for w in self.workers if w.get("agent") == agent), None)
                        if runtime_entry:
                            self.update_runtime_entry(
                                runtime_entry,
                                worker.resource_pool,
                                worker.provider,
                                worker.model,
                                "healthy",
                            )
                    else:
                        if returncode == 0:
                            self.provider_stats[worker.resource_pool]["clean_exits"] += 1
                        else:
                            self.provider_stats[worker.resource_pool]["failed_exits"] += 1
                            self.provider_stats[worker.resource_pool][
                                "last_failure"
                            ] = f"worker exited with {returncode}"
                        self.persist_provider_stats()
                        state = "offline" if returncode == 0 else "stale"
                        escalation = "worker exited cleanly" if returncode == 0 else f"worker exited with {returncode}"
                        self.update_heartbeat(agent, state, "process_exit", escalation)
                        runtime_entry = next((w for w in self.workers if w.get("agent") == agent), None)
                        if runtime_entry:
                            self.update_runtime_entry(
                                runtime_entry,
                                worker.resource_pool,
                                worker.provider,
                                worker.model,
                                state,
                            )
                self.persist_manager_report()
                self.write_session_state()
            time.sleep(5)

    def write_session_state(self) -> None:
        worker_payload = {
            agent: {
                "pid": worker.process.pid,
                "resource_pool": worker.resource_pool,
                "provider": worker.provider,
                "model": worker.model,
                "command": worker.command,
                "wrapper_path": worker.wrapper_path,
                "recursion_guard": worker.recursion_guard,
                "worktree_path": str(worker.worktree_path),
                "log_path": str(worker.log_path),
                "alive": worker.process.poll() is None,
                "returncode": worker.process.poll(),
                "simulated": False,
            }
            for agent, worker in self.processes.items()
        }
        payload = {
            "updated_at": now_iso(),
            "last_event": self.last_event,
            "server": {
                "pid": os.getpid(),
                "host": self.listen_host,
                "port": self.listen_port,
                "endpoints": self.listen_endpoints,
                "config_path": str(self.config_path),
                "persist_config_path": str(self.persist_config_path),
                "cold_start": self.bootstrap_mode,
                "bootstrap_reason": self.bootstrap_reason,
                "listener_active": self.listener_active,
                "alive": not self.stop_event.is_set(),
            },
            "workers": worker_payload,
        }
        encoded = json.dumps(payload, indent=2)
        SESSION_STATE.write_text(encoded, encoding="utf-8")
        if self.listen_port:
            session_state_path_for_port(self.listen_port).write_text(encoded, encoding="utf-8")

    def edit_lock_state(self) -> dict[str, Any]:
        path = STATE_DIR / "edit_locks.yaml"
        if not path.exists():
            return {"policy": {}, "locks": [], "last_updated": ""}
        data = load_yaml(path)
        if not isinstance(data, dict):
            return {"policy": {}, "locks": [], "last_updated": ""}
        locks = data.get("locks", [])
        normalized_locks = []
        for item in locks if isinstance(locks, list) else []:
            if not isinstance(item, dict):
                continue
            normalized_locks.append(
                {
                    "path": str(item.get("path") or "").strip(),
                    "owner": str(item.get("owner") or "").strip(),
                    "state": str(item.get("state") or "free").strip() or "free",
                    "intent": str(item.get("intent") or "").strip(),
                    "updated_at": str(item.get("updated_at") or "").strip(),
                }
            )
        return {
            "policy": data.get("policy") if isinstance(data.get("policy"), dict) else {},
            "locks": normalized_locks,
            "last_updated": str(data.get("last_updated") or "").strip(),
        }

    def cleanup_status(self) -> dict[str, Any]:
        runtime_state = self.dashboard_runtime_state()
        heartbeat_state = self.dashboard_heartbeats_state()
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
