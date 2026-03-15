from __future__ import annotations

import json
import os
import time
from typing import Any

from .contracts import ManagerConsoleState
from .constants import (
    PROVIDER_STATS_PATH,
    MANAGER_CONSOLE_PATH,
    REPO_ROOT,
    SESSION_STATE,
    STATE_DIR,
)
from .network import session_state_path_for_port
from .stores import HeartbeatStore, ManagerConsoleStore, ProviderStatsStore, RuntimeStore
from .telemetry import read_log_telemetry
from .utils import now_iso


def _short_path(path: str) -> str:
    """Collapse long absolute paths to just the last 2 segments."""
    parts = path.rstrip("/").rsplit("/", 2)
    return "/".join(parts[-2:]) if len(parts) > 2 else path


def _extract_stream_json_lines(raw_lines: list[str]) -> list[str]:
    """Parse ducc stream-json lines into concise peek output.

    Only keeps: assistant text (first line), tool calls (short), errors, init/done.
    Drops: user messages, tool results, thinking, system hooks, raw noise.
    """
    readable: list[str] = []
    for line in raw_lines:
        stripped = line.strip()
        if not stripped or not stripped.startswith("{"):
            continue
        try:
            obj = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            continue
        msg_type = obj.get("type", "")
        if msg_type == "assistant":
            message = obj.get("message", {})
            for block in message.get("content", []):
                bt = block.get("type", "")
                if bt == "text":
                    text = block.get("text", "").strip()
                    if text:
                        first_line = text.split("\n", 1)[0].strip()
                        if len(first_line) > 160:
                            first_line = first_line[:157] + "..."
                        readable.append(first_line)
                elif bt == "tool_use":
                    name = block.get("name", "?")
                    inp = block.get("input", {})
                    if not isinstance(inp, dict):
                        readable.append(f">> {name}")
                        continue
                    if "command" in inp:
                        cmd = inp["command"].strip().split("\n", 1)[0]
                        if len(cmd) > 100:
                            cmd = cmd[:97] + "..."
                        readable.append(f">> {name} $ {cmd}")
                    elif "file_path" in inp:
                        readable.append(f">> {name} {_short_path(inp['file_path'])}")
                    elif "pattern" in inp:
                        readable.append(f">> {name} {inp['pattern']}")
                    else:
                        readable.append(f">> {name}")
        elif msg_type == "tool_result":
            if obj.get("is_error"):
                readable.append(f"!! {obj.get('tool_name', '?')} ERROR")
        elif msg_type == "system":
            sub = obj.get("subtype", "")
            if sub == "init":
                readable.append(f"[init model={obj.get('model', '?')}]")
            elif sub == "result":
                cost = obj.get("cost_usd", "")
                readable.append(f"[done cost=${cost}]")
    return readable


class StateMixin:
    """Methods for runtime state persistence, heartbeats, telemetry, monitoring, and session state."""

    def runtime_store(self) -> RuntimeStore:
        return RuntimeStore(STATE_DIR / "agent_runtime.yaml")

    def heartbeat_store(self) -> HeartbeatStore:
        return HeartbeatStore(STATE_DIR / "heartbeats.yaml")

    def provider_stats_store(self) -> ProviderStatsStore:
        return ProviderStatsStore(PROVIDER_STATS_PATH, self.default_provider_stat_entry)

    def manager_console_store(self) -> ManagerConsoleStore:
        return ManagerConsoleStore(MANAGER_CONSOLE_PATH)

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
        runtime = self.runtime_store().load()
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
        runtime["workers"] = workers
        self.runtime_store().persist(runtime)

    def update_heartbeat(self, agent: str, state: str, evidence: str, escalation: str) -> None:
        heartbeats = self.heartbeat_store().load()
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
        heartbeats["agents"] = entries
        self.heartbeat_store().persist(heartbeats)

    def load_provider_stats(self) -> dict[str, dict[str, Any]]:
        return self.provider_stats_store().load()

    def persist_provider_stats(self) -> None:
        self.provider_stats_store().persist(self.provider_stats)

    def load_manager_console_state(self) -> ManagerConsoleState:
        return self.manager_console_store().load()

    def persist_manager_console_state(self, state: ManagerConsoleState) -> None:
        self.manager_console_store().persist(state)

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
                runtime = self.runtime_store().load()
                if "workers" not in runtime:
                    runtime["workers"] = []
                heartbeats = self.heartbeat_store().load()
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
                    heartbeats["agents"] = heartbeats.get("agents", [])
                    self.heartbeat_store().persist(heartbeats)
                if runtime_dirty:
                    runtime["workers"] = runtime.get("workers", [])
                    self.runtime_store().persist(runtime)
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
        """Read new lines from a worker log file and push them into the peek buffer.

        If lines are stream-json (from ducc --output-format stream-json),
        parse them and extract human-readable content.  Otherwise treat as
        plain text.
        """
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
        raw_lines = new_text.splitlines()
        if not raw_lines:
            return
        readable = _extract_stream_json_lines(raw_lines)
        if readable:
            self.peek_append(agent, readable)

