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
)


class StateMixin:
    """Methods for runtime state persistence, heartbeats, telemetry, monitoring, and session state."""

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
        if "workers" not in runtime:
            runtime["workers"] = workers
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
        target = None
        for entry in entries:
            if entry.get("agent") == agent:
                target = entry
                break
        if target is None:
            target = {"agent": agent}
            entries.append(target)
            heartbeats["agents"] = entries
        target["state"] = state
        target["last_seen"] = now_iso()
        target["evidence"] = evidence
        target["expected_next_checkin"] = "while worker process is alive"
        target["escalation"] = escalation
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
                runtime_path = STATE_DIR / "agent_runtime.yaml"
                heartbeats_path = STATE_DIR / "heartbeats.yaml"
                runtime = load_yaml(runtime_path)
                if "workers" not in runtime:
                    runtime["workers"] = []
                heartbeats = load_yaml(heartbeats_path)
                if "agents" not in heartbeats:
                    heartbeats["agents"] = []
                runtime_dirty = False
                heartbeats_dirty = False
                stats_dirty = False

                for agent, worker in list(self.processes.items()):
                    returncode = worker.process.poll()
                    # Feed worker log tail into peek buffer
                    try:
                        self._feed_peek_from_log(agent, worker.log_path)
                    except Exception:
                        pass
                    if returncode is None:
                        hb_state, hb_evidence, hb_escalation = "healthy", "process_running", "none"
                        rt_status = "healthy"
                    else:
                        if returncode == 0:
                            self.provider_stats[worker.resource_pool]["clean_exits"] += 1
                        else:
                            self.provider_stats[worker.resource_pool]["failed_exits"] += 1
                            self.provider_stats[worker.resource_pool]["last_failure"] = f"worker exited with {returncode}"
                        stats_dirty = True
                        rt_status = "offline" if returncode == 0 else "stale"
                        hb_state = rt_status
                        hb_evidence = "process_exit"
                        hb_escalation = "worker exited cleanly" if returncode == 0 else f"worker exited with {returncode}"

                    # Batch heartbeat update
                    ts = now_iso()
                    hb_entry = next((e for e in heartbeats["agents"] if e.get("agent") == agent), None)
                    if hb_entry is None:
                        hb_entry = {"agent": agent}
                        heartbeats["agents"].append(hb_entry)
                    hb_entry.update({"state": hb_state, "last_seen": ts, "evidence": hb_evidence,
                                     "expected_next_checkin": "while worker process is alive", "escalation": hb_escalation})
                    heartbeats_dirty = True

                    # Batch runtime update
                    runtime_entry = next((w for w in self.workers if w.get("agent") == agent), None)
                    if runtime_entry:
                        rt_target = next((e for e in runtime["workers"] if e.get("agent") == agent), None)
                        if rt_target is None:
                            rt_target = {"agent": agent}
                            runtime["workers"].append(rt_target)
                        rt_target.update({
                            "repository_name": self.project.get("repository_name", "target-repo"),
                            "resource_pool": worker.resource_pool,
                            "provider": worker.provider,
                            "model": worker.model,
                            "recursion_guard": rt_target.get("recursion_guard", ""),
                            "launch_wrapper": rt_target.get("launch_wrapper", ""),
                            "launch_owner": runtime_entry.get("launch_owner", "manager"),
                            "local_workspace_root": self.project.get("local_repo_root", str(REPO_ROOT)),
                            "repository_root": str(REPO_ROOT),
                            "worktree_path": runtime_entry["worktree_path"],
                            "branch": runtime_entry["branch"],
                            "merge_target": self.integration_branch(),
                            "environment_type": runtime_entry.get("environment_type", "uv"),
                            "environment_path": runtime_entry.get("environment_path", "unassigned"),
                            "sync_command": runtime_entry.get("sync_command", "uv sync"),
                            "test_command": runtime_entry.get("test_command", "unassigned"),
                            "submit_strategy": runtime_entry.get("submit_strategy", "patch_handoff"),
                            "git_author_name": self.worker_git_identity(runtime_entry).get("name", ""),
                            "git_author_email": self.worker_git_identity(runtime_entry).get("email", ""),
                            "status": rt_status,
                        })
                        runtime_dirty = True

                # Single dump per file
                if heartbeats_dirty:
                    heartbeats["last_updated"] = now_iso()
                    dump_yaml(heartbeats_path, heartbeats)
                if runtime_dirty:
                    runtime["last_updated"] = now_iso()
                    dump_yaml(runtime_path, runtime)
                if stats_dirty:
                    self.persist_provider_stats()
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

    def _feed_peek_from_log(self, agent: str, log_path) -> None:
        """Read new lines from a worker log file and push them into the peek buffer."""
        from pathlib import Path
        log_path = Path(log_path)
        if not log_path.exists():
            return
        if not hasattr(self, "_peek_log_offsets"):
            self._peek_log_offsets: dict[str, int] = {}
        offset = self._peek_log_offsets.get(agent, 0)
        file_size = log_path.stat().st_size
        if file_size <= offset:
            return
        with log_path.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(offset)
            new_text = fh.read(64 * 1024)  # cap at 64KB per tick
            new_offset = fh.tell()
        self._peek_log_offsets[agent] = new_offset
        lines = new_text.splitlines()
        if lines:
            self.peek_append(agent, lines)

