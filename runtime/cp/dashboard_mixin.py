from __future__ import annotations

import subprocess
from typing import Any

from .contracts import A0ConsoleState, MergeQueueItem
from .constants import (
    CHECKPOINT_DIR,
    CONTROL_PLANE_RUNTIME,
    DEFAULT_DASHBOARD_HOST,
    DEFAULT_DASHBOARD_PORT,
    MANAGER_REPORT,
    REPO_ROOT,
    STATE_DIR,
    STATUS_DIR,
)
from .markdown import parse_markdown_list, parse_markdown_paragraph, parse_markdown_sections
from .services import (
    build_a0_request_catalog,
    build_merge_queue,
    compute_manager_control_state,
    summarize_worker_handoff,
)
from .utils import (
    dedupe_strings,
    load_yaml,
    now_iso,
)


class DashboardMixin:
    """Methods for building dashboard views, CLI commands, merge-queue state, and manager reporting."""

    def build_dashboard_state(self) -> dict[str, Any]:
        config_text = self.config_path.read_text(encoding="utf-8") if self.config_path.exists() else ""
        runtime_state = self.dashboard_runtime_state()
        heartbeat_state = self.dashboard_heartbeats_state(runtime_state=runtime_state)
        manager_report = self.persist_manager_report(runtime_state, heartbeat_state)
        merge_queue = self.merge_queue(runtime_state=runtime_state, heartbeat_state=heartbeat_state)
        a0_console = self.a0_request_catalog(merge_queue, heartbeat_state)
        return {
            "updated_at": now_iso(),
            "last_event": self.last_event,
            "mode": {
                "state": "cold-start" if self.bootstrap_mode else "configured",
                "cold_start": self.bootstrap_mode,
                "listener_active": self.listener_active,
                "reason": self.bootstrap_reason,
                "config_path": str(self.config_path),
                "persist_config_path": str(self.persist_config_path),
            },
            "project": self.project,
            "commands": self.build_cli_commands(),
            "launch_policy": self.launch_policy_state(),
            "manager_report": manager_report,
            "runtime": runtime_state,
            "heartbeats": heartbeat_state,
            "backlog": self.load_backlog_state(),
            "gates": load_yaml(STATE_DIR / "gates.yaml"),
            "processes": self.process_snapshot(),
            "provider_queue": self.provider_queue(),
            "resolved_workers": [self.resolved_worker_plan(worker) for worker in self.workers],
            "merge_queue": merge_queue,
            "a0_console": a0_console,
            "team_mailbox": self.team_mailbox_catalog(),
            "cleanup": self.cleanup_status(runtime_state=runtime_state, heartbeat_state=heartbeat_state),
            "config": self.config,
            "config_text": config_text,
            "validation_errors": self.validation_errors(),
            "launch_blockers": self.launch_blockers(),
            "peek": self.peek_read_all(),
        }

    def build_cli_commands(self) -> dict[str, str]:
        host = self.host_override or self.project.get("dashboard", {}).get("host", DEFAULT_DASHBOARD_HOST)
        port = self.port_override or int(self.project.get("dashboard", {}).get("port", DEFAULT_DASHBOARD_PORT))
        config = str(self.persist_config_path)
        serve_parts = [
            CONTROL_PLANE_RUNTIME,
            "runtime/control_plane.py",
            "serve",
            "--config",
            config,
        ]
        up_parts = [
            CONTROL_PLANE_RUNTIME,
            "runtime/control_plane.py",
            "up",
            "--config",
            config,
        ]
        if host != DEFAULT_DASHBOARD_HOST:
            serve_parts.extend(["--host", str(host)])
            up_parts.extend(["--host", str(host)])
        if port != DEFAULT_DASHBOARD_PORT:
            serve_parts.extend(["--port", str(port)])
            up_parts.extend(["--port", str(port)])
        up_parts.append("--open-browser")
        serve = " ".join(serve_parts)
        up = " ".join(up_parts)
        return {"serve": serve, "up": up}

    def task_title(self, task_id: str) -> str:
        backlog = load_yaml(STATE_DIR / "backlog.yaml")
        for item in backlog.get("items", []):
            if item.get("id") == task_id:
                return str(item.get("title", task_id))
        return task_id

    def integration_branch(self) -> str:
        return str(self.project.get("integration_branch") or self.project.get("base_branch") or "main")

    def worker_git_identity(self, worker: dict[str, Any]) -> dict[str, str]:
        identity = worker.get("git_identity") or {}
        return {
            "name": str(identity.get("name", "")).strip(),
            "email": str(identity.get("email", "")).strip(),
        }

    def manager_git_identity(self) -> dict[str, str]:
        identity = self.project.get("manager_git_identity") or {}
        return {
            "name": str(identity.get("name", "")).strip(),
            "email": str(identity.get("email", "")).strip(),
        }

    def _worker_identity_display(self, worker: dict[str, Any]) -> str:
        git_identity = self.worker_git_identity(worker)
        if git_identity["name"] and git_identity["email"]:
            return f"{git_identity['name']} <{git_identity['email']}>"
        return "environment default"

    def current_repo_branch(self) -> str:
        repo_root = self.target_repo_root()
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            branch = str(result.stdout).strip()
            if branch and branch != "HEAD":
                return branch
        return str(self.project.get("base_branch") or self.integration_branch() or "main")

    def manager_runtime_entry(self, runtime: dict[str, Any] | None = None) -> dict[str, Any]:
        workers = runtime.get("workers", []) if isinstance(runtime, dict) else []
        existing = next(
            (item for item in workers if isinstance(item, dict) and str(item.get("agent", "")).strip() == "A0"),
            {},
        )
        status = str(existing.get("status", "")).strip() or "healthy"
        manager_identity = self.manager_git_identity()
        return {
            "agent": "A0",
            "repository_name": self.project.get("repository_name", "target-repo"),
            "resource_pool": "none",
            "provider": "none",
            "model": "none",
            "recursion_guard": str(existing.get("recursion_guard", "")).strip(),
            "launch_wrapper": str(existing.get("launch_wrapper", "")).strip(),
            "launch_owner": "manager",
            "local_workspace_root": self.project.get("local_repo_root", str(REPO_ROOT)),
            "repository_root": str(REPO_ROOT),
            "worktree_path": str(REPO_ROOT),
            "branch": self.current_repo_branch(),
            "merge_target": self.integration_branch(),
            "environment_type": "none",
            "environment_path": "none",
            "sync_command": "none",
            "test_command": "none",
            "submit_strategy": "direct_manager_edit",
            "git_author_name": manager_identity.get("name", ""),
            "git_author_email": manager_identity.get("email", ""),
            "status": status,
        }

    def dashboard_runtime_state(self) -> dict[str, Any]:
        runtime = load_yaml(STATE_DIR / "agent_runtime.yaml")
        workers = runtime.get("workers", [])
        if not isinstance(workers, list):
            workers = []
        filtered_workers = [
            item for item in workers if isinstance(item, dict) and str(item.get("agent", "")).strip() != "A0"
        ]
        filtered_workers.insert(0, self.manager_runtime_entry(runtime))
        runtime["workers"] = filtered_workers
        runtime["last_updated"] = runtime.get("last_updated") or now_iso()
        return runtime

    def compute_manager_control_state(
        self,
        runtime_state: dict[str, Any] | None = None,
        heartbeat_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return compute_manager_control_state(
            workers=self.workers,
            runtime_state=runtime_state or self.dashboard_runtime_state(),
            heartbeat_state=heartbeat_state or self.dashboard_heartbeats_state(),
            backlog_items=self.backlog_items(),
            task_record_for_worker=self.task_record_for_worker,
        )

    def render_manager_report(
        self,
        runtime_state: dict[str, Any] | None = None,
        heartbeat_state: dict[str, Any] | None = None,
    ) -> str:
        runtime_state = runtime_state or self.dashboard_runtime_state()
        heartbeat_state = heartbeat_state or self.dashboard_heartbeats_state()
        control = self.compute_manager_control_state(runtime_state, heartbeat_state)
        gates = load_yaml(STATE_DIR / "gates.yaml").get("gates", [])
        gate_list = gates if isinstance(gates, list) else []
        open_gate = next((item for item in gate_list if str(item.get("status", "")).strip() == "open"), None)
        current_gate = (
            f"{open_gate.get('id', 'unknown')} {open_gate.get('name', '')}".strip()
            if isinstance(open_gate, dict)
            else "none"
        )
        heartbeat_map = {
            str(item.get("agent", "")).strip(): item
            for item in heartbeat_state.get("agents", [])
            if isinstance(item, dict)
        }
        runtime_map = {
            str(item.get("agent", "")).strip(): item
            for item in runtime_state.get("workers", [])
            if isinstance(item, dict)
        }
        liveness_lines: list[str] = []
        for agent in ["A0", *[str(worker.get("agent", "")).strip() for worker in self.workers]]:
            if not agent:
                continue
            heartbeat = heartbeat_map.get(agent, {})
            runtime_entry = runtime_map.get(agent, {})
            state = (
                str(heartbeat.get("state", "")).strip() or str(runtime_entry.get("status", "")).strip() or "unknown"
            )
            liveness_lines.append(f"- {agent}: {state}")

        blocker_lines: list[str] = []
        if control["attention_agents"]:
            blocker_lines.append(f"attention required: {', '.join(control['attention_agents'])}")
        if control["blocked_agents"]:
            blocker_lines.append(f"blocked by dependency or gate: {', '.join(control['blocked_agents'])}")
        if not blocker_lines:
            blocker_lines.append("no manager-side incidents detected")

        return f"""# Manager Report

Last updated: {now_iso()}

## Production View

- Stage: live manager polling
- Delivery mode: {'listener active' if self.listener_active else 'listener offline'}
- Current gate: {current_gate}
- Current manager: A0
- Poll loop: every 5 seconds

## Real Liveness

{chr(10).join(liveness_lines)}

## Control Snapshot

- Active agents: {', '.join(control['active_agents']) or 'none'}
- Attention agents: {', '.join(control['attention_agents']) or 'none'}
- Runnable agents: {', '.join(control['runnable_agents']) or 'none'}
- Blocked agents: {', '.join(control['blocked_agents']) or 'none'}

## Active Blockers

{chr(10).join(f'- {item}' for item in blocker_lines)}

## Immediate Action

1. Review attention agents first and clear launch or runtime faults.
2. Launch the next runnable set when provider readiness is green.
3. Keep gate ordering aligned with backlog dependencies before widening scope.
"""

    def persist_manager_report(
        self,
        runtime_state: dict[str, Any] | None = None,
        heartbeat_state: dict[str, Any] | None = None,
    ) -> str:
        report = self.render_manager_report(runtime_state, heartbeat_state)
        MANAGER_REPORT.write_text(report, encoding="utf-8")
        return report

    def manager_heartbeat_entry(
        self,
        heartbeats: dict[str, Any] | None = None,
        runtime_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        agents = heartbeats.get("agents", []) if isinstance(heartbeats, dict) else []
        existing = next(
            (item for item in agents if isinstance(item, dict) and str(item.get("agent", "")).strip() == "A0"),
            {},
        )
        listener_active = bool(self.listener_active)
        control = self.compute_manager_control_state(
            runtime_state or self.dashboard_runtime_state(),
            {
                "agents": [
                    item for item in agents if isinstance(item, dict) and str(item.get("agent", "")).strip() != "A0"
                ]
            },
        )
        if listener_active:
            evidence = f"polling {control['worker_count']} workers"
            if control["attention_agents"]:
                evidence += f"; attention: {', '.join(control['attention_agents'])}"
            elif control["active_agents"]:
                evidence += f"; active: {', '.join(control['active_agents'])}"
            elif control["runnable_agents"]:
                evidence += f"; runnable: {', '.join(control['runnable_agents'])}"
            else:
                evidence += "; no immediate action set"
            expected_next_checkin = "within monitor loop interval"
            escalation = (
                "review attention queue and launch runnable workers" if control["attention_agents"] else "none"
            )
        else:
            evidence = "control-plane listener offline"
            expected_next_checkin = "when listener restarts"
            escalation = "restart control-plane listener to resume manager orchestration"
        return {
            "agent": "A0",
            "role": str(existing.get("role", "")).strip() or "manager",
            "state": "healthy" if listener_active else "offline",
            "last_seen": now_iso(),
            "evidence": evidence,
            "expected_next_checkin": expected_next_checkin,
            "escalation": escalation,
        }

    def dashboard_heartbeats_state(self, runtime_state: dict[str, Any] | None = None) -> dict[str, Any]:
        heartbeats = load_yaml(STATE_DIR / "heartbeats.yaml")
        agents = heartbeats.get("agents", [])
        if not isinstance(agents, list):
            agents = []
        filtered_agents = [
            item for item in agents if isinstance(item, dict) and str(item.get("agent", "")).strip() != "A0"
        ]
        filtered_agents.insert(0, self.manager_heartbeat_entry(heartbeats, runtime_state=runtime_state))
        heartbeats["agents"] = filtered_agents
        heartbeats["last_updated"] = now_iso()
        return heartbeats

    def worker_handoff_summary(
        self, agent: str, runtime_entry: dict[str, Any], heartbeat: dict[str, Any]
    ) -> dict[str, Any]:
        status_path = STATUS_DIR / f"{agent}.md"
        checkpoint_path = CHECKPOINT_DIR / f"{agent}.md"
        status_meta: dict[str, str] = {}
        status_sections: dict[str, str] = {}
        checkpoint_meta: dict[str, str] = {}
        checkpoint_sections: dict[str, str] = {}
        if status_path.exists():
            status_meta, status_sections = parse_markdown_sections(status_path.read_text(encoding="utf-8"))
        if checkpoint_path.exists():
            checkpoint_meta, checkpoint_sections = parse_markdown_sections(checkpoint_path.read_text(encoding="utf-8"))

        return summarize_worker_handoff(
            runtime_entry=runtime_entry,
            heartbeat=heartbeat,
            status_meta=status_meta,
            status_sections=status_sections,
            checkpoint_meta=checkpoint_meta,
            checkpoint_sections=checkpoint_sections,
            parse_list=parse_markdown_list,
            parse_paragraph=parse_markdown_paragraph,
        )

    def merge_queue(
        self,
        runtime_state: dict[str, Any] | None = None,
        heartbeat_state: dict[str, Any] | None = None,
    ) -> list[MergeQueueItem]:
        runtime_state = runtime_state or self.dashboard_runtime_state()
        heartbeat_state = heartbeat_state or self.dashboard_heartbeats_state(runtime_state=runtime_state)
        runtime_workers = {
            str(item.get("agent", "")).strip(): item
            for item in runtime_state.get("workers", [])
            if isinstance(item, dict)
        }
        heartbeat_workers = {
            str(item.get("agent", "")).strip(): item
            for item in heartbeat_state.get("agents", [])
            if isinstance(item, dict)
        }
        handoff_by_agent = {
            str(worker.get("agent", "")).strip(): self.worker_handoff_summary(
                str(worker.get("agent", "")).strip(),
                runtime_workers.get(str(worker.get("agent", "")).strip(), {}),
                heartbeat_workers.get(str(worker.get("agent", "")).strip(), {}),
            )
            for worker in self.workers
        }
        return build_merge_queue(
            self.workers,
            runtime_state,
            heartbeat_state,
            handoff_by_agent,
            integration_branch=self.integration_branch(),
            manager_identity=self.manager_git_identity(),
            worker_identity_display=lambda worker: self._worker_identity_display(worker),
        )

    def a0_request_catalog(
        self,
        merge_queue: list[MergeQueueItem],
        heartbeat_state: dict[str, Any] | None = None,
    ) -> A0ConsoleState:
        stored = self.load_manager_console_state()
        mailbox_state = self.team_mailbox_catalog()
        return build_a0_request_catalog(
            self.backlog_items(),
            merge_queue,
            mailbox_state.get("messages", []),
            stored.get("requests", {}),
            stored.get("messages", []),
        )
