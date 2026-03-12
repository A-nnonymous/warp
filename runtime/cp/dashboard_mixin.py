from __future__ import annotations

import subprocess
from typing import Any

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
from .utils import (
    dedupe_strings,
    load_yaml,
    now_iso,
    slugify,
    summarize_list,
)


class DashboardMixin:
    """Methods for building dashboard views, CLI commands, merge-queue state, and manager reporting."""

    def build_dashboard_state(self) -> dict[str, Any]:
        config_text = self.config_path.read_text(encoding="utf-8") if self.config_path.exists() else ""
        runtime_state = self.dashboard_runtime_state()
        heartbeat_state = self.dashboard_heartbeats_state()
        manager_report = self.persist_manager_report(runtime_state, heartbeat_state)
        merge_queue = self.merge_queue()
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
            "cleanup": self.cleanup_status(),
            "config": self.config,
            "config_text": config_text,
            "validation_errors": self.validation_errors(),
            "launch_blockers": self.launch_blockers(),
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
            "resource_pool": "manager_local",
            "provider": "manager-local",
            "model": "environment default",
            "recursion_guard": str(existing.get("recursion_guard", "")).strip(),
            "launch_wrapper": str(existing.get("launch_wrapper", "")).strip(),
            "launch_owner": "manager",
            "local_workspace_root": self.project.get("local_repo_root", str(REPO_ROOT)),
            "repository_root": str(REPO_ROOT),
            "worktree_path": str(REPO_ROOT),
            "branch": self.current_repo_branch(),
            "merge_target": self.integration_branch(),
            "environment_type": "none",
            "environment_path": "environment default",
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
        runtime_state = runtime_state or self.dashboard_runtime_state()
        heartbeat_state = heartbeat_state or self.dashboard_heartbeats_state()
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
        backlog_items = self.backlog_items()
        completed_task_ids = {
            str(item.get("id", "")).strip()
            for item in backlog_items
            if str(item.get("status", "")).strip() in {"done", "completed", "merged"}
        }

        active_agents: list[str] = []
        attention_agents: list[str] = []
        runnable_agents: list[str] = []
        blocked_agents: list[str] = []

        for worker in self.workers:
            agent = str(worker.get("agent", "")).strip()
            runtime_entry = runtime_workers.get(agent, {})
            heartbeat = heartbeat_workers.get(agent, {})
            runtime_status = str(runtime_entry.get("status", "")).strip()
            heartbeat_value = str(heartbeat.get("state", "")).strip()
            backlog_item = self.task_record_for_worker(worker)
            backlog_status = str(backlog_item.get("status", "")).strip()
            dependencies = [str(item).strip() for item in backlog_item.get("dependencies", []) if str(item).strip()]
            dependencies_ready = all(item in completed_task_ids for item in dependencies)

            if runtime_status in {"launching", "healthy", "active"}:
                active_agents.append(agent)
                continue
            if runtime_status.startswith("launch_failed") or heartbeat_value in {"stale", "error"}:
                attention_agents.append(agent)
                continue
            if backlog_status == "blocked" or (dependencies and not dependencies_ready):
                blocked_agents.append(agent)
                continue
            if backlog_status in {"pending", "queued", "not-started", "not_started", ""}:
                runnable_agents.append(agent)

        return {
            "worker_count": len(self.workers),
            "active_agents": active_agents,
            "attention_agents": attention_agents,
            "runnable_agents": runnable_agents,
            "blocked_agents": blocked_agents,
        }

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

    def manager_heartbeat_entry(self, heartbeats: dict[str, Any] | None = None) -> dict[str, Any]:
        agents = heartbeats.get("agents", []) if isinstance(heartbeats, dict) else []
        existing = next(
            (item for item in agents if isinstance(item, dict) and str(item.get("agent", "")).strip() == "A0"),
            {},
        )
        listener_active = bool(self.listener_active)
        control = self.compute_manager_control_state(
            self.dashboard_runtime_state(),
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

    def dashboard_heartbeats_state(self) -> dict[str, Any]:
        heartbeats = load_yaml(STATE_DIR / "heartbeats.yaml")
        agents = heartbeats.get("agents", [])
        if not isinstance(agents, list):
            agents = []
        filtered_agents = [
            item for item in agents if isinstance(item, dict) and str(item.get("agent", "")).strip() != "A0"
        ]
        filtered_agents.insert(0, self.manager_heartbeat_entry(heartbeats))
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

        blockers = parse_markdown_list(status_sections.get("blockers", ""))
        requested_unlocks = parse_markdown_list(status_sections.get("requested unlocks", ""))
        pending_work = parse_markdown_list(checkpoint_sections.get("pending work", ""))
        dependencies = parse_markdown_list(checkpoint_sections.get("dependencies", ""))
        resume_instruction = parse_markdown_paragraph(checkpoint_sections.get("resume instruction", ""))
        next_checkin = parse_markdown_paragraph(status_sections.get("next check-in condition", ""))

        runtime_status = str(runtime_entry.get("status", "")).strip()
        heartbeat_state = str(heartbeat.get("state", "")).strip()
        heartbeat_evidence = str(heartbeat.get("evidence", "")).strip()
        heartbeat_escalation = str(heartbeat.get("escalation", "")).strip()
        attention_summary = ""
        if runtime_status.startswith("launch_failed"):
            attention_summary = runtime_status
        elif heartbeat_evidence == "process_exit" and heartbeat_escalation and heartbeat_escalation != "none":
            attention_summary = heartbeat_escalation
        elif heartbeat_state in {"stale", "error"} and heartbeat_evidence:
            attention_summary = heartbeat_escalation or heartbeat_evidence
        elif blockers:
            attention_summary = blockers[0]
        elif pending_work:
            attention_summary = pending_work[0]
        elif heartbeat_evidence and heartbeat_evidence.lower() != "no runtime heartbeat yet":
            attention_summary = heartbeat_escalation or heartbeat_evidence

        return {
            "checkpoint_status": checkpoint_meta.get("status")
            or status_meta.get("status")
            or heartbeat_state
            or "unknown",
            "attention_summary": attention_summary,
            "blockers": blockers,
            "pending_work": pending_work,
            "requested_unlocks": requested_unlocks,
            "dependencies": dependencies,
            "resume_instruction": resume_instruction,
            "next_checkin": next_checkin or str(heartbeat.get("expected_next_checkin", "")).strip(),
        }

    def merge_queue(self) -> list[dict[str, Any]]:
        runtime_state = self.dashboard_runtime_state()
        runtime_workers = {str(item.get("agent")): item for item in runtime_state.get("workers", [])}
        heartbeat_state = self.dashboard_heartbeats_state()
        heartbeats = {str(item.get("agent")): item for item in heartbeat_state.get("agents", [])}
        queue: list[dict[str, Any]] = []
        manager_identity = self.manager_git_identity()
        manager_display = (
            f"{manager_identity['name']} <{manager_identity['email']}>"
            if manager_identity["name"] and manager_identity["email"]
            else "A0 manager identity"
        )
        for worker in self.workers:
            agent = str(worker.get("agent", ""))
            runtime_entry = runtime_workers.get(agent, {})
            heartbeat = heartbeats.get(agent, {})
            handoff = self.worker_handoff_summary(agent, runtime_entry, heartbeat)
            git_identity = self.worker_git_identity(worker)
            worker_display = (
                f"{git_identity['name']} <{git_identity['email']}>"
                if git_identity["name"] and git_identity["email"]
                else "environment default"
            )
            queue.append(
                {
                    "agent": agent,
                    "branch": worker.get("branch", "unassigned"),
                    "submit_strategy": worker.get("submit_strategy", "patch_handoff"),
                    "merge_target": self.integration_branch(),
                    "worker_identity": worker_display,
                    "manager_identity": manager_display,
                    "status": runtime_entry.get("status", heartbeat.get("state", "not_started")),
                    "checkpoint_status": handoff["checkpoint_status"],
                    "attention_summary": handoff["attention_summary"],
                    "blockers": handoff["blockers"],
                    "pending_work": handoff["pending_work"],
                    "requested_unlocks": handoff["requested_unlocks"],
                    "dependencies": handoff["dependencies"],
                    "resume_instruction": handoff["resume_instruction"],
                    "next_checkin": handoff["next_checkin"],
                    "manager_action": f"A0 merges {worker.get('branch', 'unassigned')} into {self.integration_branch()}",
                }
            )
        return queue

    def a0_request_catalog(
        self,
        merge_queue: list[dict[str, Any]],
        heartbeat_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        stored = self.load_manager_console_state()
        request_state = stored.get("requests", {}) if isinstance(stored.get("requests"), dict) else {}
        messages = stored.get("messages", []) if isinstance(stored.get("messages"), list) else []
        requests: list[dict[str, Any]] = []
        mailbox_state = self.team_mailbox_catalog()
        inbox = [
            item
            for item in mailbox_state.get("messages", [])
            if str(item.get("ack_state") or "") != "resolved"
            and (
                str(item.get("to") or "") in {"A0", "a0", "manager", "all"}
                or str(item.get("scope") or "") in {"broadcast", "manager"}
            )
        ]

        for item in self.backlog_items():
            task_id = str(item.get("id") or "").strip()
            claimant = str(item.get("claimed_by") or item.get("owner") or "A?").strip() or "A?"
            if str(item.get("plan_state") or "") == "pending_review":
                request_id = slugify(f"{task_id}_plan_review")
                saved = request_state.get(request_id, {}) if isinstance(request_state.get(request_id), dict) else {}
                requests.append(
                    {
                        "id": request_id,
                        "agent": claimant,
                        "task_id": task_id,
                        "request_type": "plan_review",
                        "status": str(item.get("status") or "pending"),
                        "title": f"{task_id} requests plan approval",
                        "body": str(item.get("plan_summary") or f"{task_id} is waiting for manager review").strip(),
                        "resume_instruction": "Approve to allow implementation, or reject with constraints.",
                        "next_checkin": str(item.get("updated_at") or item.get("claimed_at") or "").strip(),
                        "response_state": str(saved.get("response_state") or "pending").strip() or "pending",
                        "response_note": str(saved.get("response_note") or item.get("plan_review_note") or "").strip(),
                        "response_at": str(saved.get("response_at") or item.get("plan_reviewed_at") or "").strip(),
                        "created_at": str(saved.get("created_at") or item.get("claimed_at") or now_iso()).strip(),
                    }
                )
            elif str(item.get("status") or "") == "review" or str(item.get("claim_state") or "") == "review":
                request_id = slugify(f"{task_id}_task_review")
                saved = request_state.get(request_id, {}) if isinstance(request_state.get(request_id), dict) else {}
                requests.append(
                    {
                        "id": request_id,
                        "agent": claimant,
                        "task_id": task_id,
                        "request_type": "task_review",
                        "status": str(item.get("status") or "review"),
                        "title": f"{task_id} requests manager acceptance",
                        "body": str(item.get("review_note") or f"{task_id} is ready for manager review").strip(),
                        "resume_instruction": "Accept to unblock dependents, or reopen with a concrete correction.",
                        "next_checkin": str(item.get("review_requested_at") or item.get("updated_at") or "").strip(),
                        "response_state": str(saved.get("response_state") or "pending").strip() or "pending",
                        "response_note": str(saved.get("response_note") or item.get("review_note") or "").strip(),
                        "response_at": str(saved.get("response_at") or item.get("completed_at") or "").strip(),
                        "created_at": str(saved.get("created_at") or item.get("review_requested_at") or now_iso()).strip(),
                    }
                )

        for item in merge_queue:
            agent = str(item.get("agent", "")).strip()
            requested_unlocks = item.get("requested_unlocks") or []
            blockers = item.get("blockers") or []
            attention_summary = str(item.get("attention_summary", "")).strip()
            status = str(item.get("status", "")).strip() or "not_started"
            if not requested_unlocks and not blockers and not attention_summary:
                continue

            title = f"{agent} needs A0 review"
            if requested_unlocks:
                title = f"{agent} requests unlock"
            elif status.startswith("launch_failed") or status == "stale":
                title = f"{agent} needs intervention"

            body_parts = []
            if attention_summary:
                body_parts.append(attention_summary)
            if requested_unlocks:
                body_parts.append(f"requested unlocks: {summarize_list(requested_unlocks)}")
            if blockers:
                body_parts.append(f"blockers: {summarize_list(blockers)}")
            request_id = slugify(f"{agent}_{status}_{title}_{attention_summary or summarize_list(requested_unlocks) or summarize_list(blockers)}")
            saved = request_state.get(request_id, {}) if isinstance(request_state.get(request_id), dict) else {}
            response_state = str(saved.get("response_state", "pending")).strip() or "pending"
            response_note = str(saved.get("response_note", "")).strip()
            response_at = str(saved.get("response_at", "")).strip()
            created_at = str(saved.get("created_at", "")).strip() or now_iso()

            requests.append(
                {
                    "id": request_id,
                    "agent": agent,
                    "request_type": "worker_intervention",
                    "status": status,
                    "title": title,
                    "body": "; ".join(body_parts) or title,
                    "requested_unlocks": requested_unlocks,
                    "blockers": blockers,
                    "resume_instruction": str(item.get("resume_instruction", "")).strip(),
                    "next_checkin": str(item.get("next_checkin", "")).strip(),
                    "response_state": response_state,
                    "response_note": response_note,
                    "response_at": response_at,
                    "created_at": created_at,
                }
            )

        requests.sort(key=lambda item: (item["response_state"] != "pending", item["agent"], item["id"]))
        pending_count = sum(1 for item in requests if item["response_state"] == "pending") + len(inbox)
        return {
            "requests": requests,
            "messages": messages[-20:],
            "inbox": inbox[-20:],
            "pending_count": pending_count,
            "last_updated": now_iso(),
        }
