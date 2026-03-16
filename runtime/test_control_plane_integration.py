from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from copy import deepcopy
from pathlib import Path


WARP_ROOT = Path(__file__).resolve().parents[1]


def _yaml_available_in_system_python() -> bool:
    """Return True if the current Python interpreter can import yaml."""
    try:
        import yaml  # noqa: F401
        return True
    except ImportError:
        return False


def _server_launch_cmd(script: str | Path, extra_args: list[str]) -> list[str]:
    """Build the command list to launch the control-plane server.

    Prefers the current ``python3`` interpreter when PyYAML is already
    installed, falling back to ``uv run --with PyYAML`` otherwise.
    """
    if _yaml_available_in_system_python():
        return [sys.executable, str(script)] + extra_args
    return ["uv", "run", "--with", "PyYAML>=6.0.2", "python", str(script)] + extra_args


def read_json(url: str, payload: dict[str, object] | None = None, timeout: float = 5.0) -> dict[str, object]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"request failed with status {exc.code}: {body}") from exc


def wait_for(predicate, timeout: float = 20.0, interval: float = 0.5) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise TimeoutError("condition was not satisfied before timeout")


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def port_is_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def request_json_allow_error(
    url: str, payload: dict[str, object] | None = None, timeout: float = 5.0
) -> tuple[int, dict[str, object]]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = json.loads(exc.read().decode("utf-8", errors="replace"))
        exc.close()
        return int(exc.code), body


def request_bytes_allow_error(
    url: str, payload: bytes, *, content_type: str = "application/json", timeout: float = 5.0
) -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(url, data=payload)
    request.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = json.loads(exc.read().decode("utf-8", errors="replace"))
        exc.close()
        return int(exc.code), body


_COPYTREE_SKIP = {"worktrees", "node_modules", "__pycache__", ".git", "logs"}


def _copytree_ignore(directory: str, entries: list[str]) -> set[str]:
    return {e for e in entries if e in _COPYTREE_SKIP or e.endswith(".pyc")}


class ControlPlaneIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="fp8-control-plane-it-")
        self.root = Path(self.temp_dir.name)
        self.warp_root = self.root / "warp"
        shutil.copytree(WARP_ROOT, self.warp_root, ignore=_copytree_ignore)
        # Reset state files so tests start with a clean first-launch environment.
        state_dir = self.warp_root / "state"
        for state_file in ("agent_runtime.yaml", "heartbeats.yaml", "provider_stats.yaml",
                           "edit_locks.yaml", "team_mailbox.yaml"):
            path = state_dir / state_file
            if path.exists():
                path.write_text("", encoding="utf-8")
        self.runtime_script = self.warp_root / "runtime" / "control_plane.py"
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir(parents=True, exist_ok=True)
        self.project_root = self.root / "workspace"
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.paddle_root = self.root / "paddle"
        self.paddle_root.mkdir(parents=True, exist_ok=True)

        self.worker_roots = {
            "A1": self.root / "workers" / "A1",
            "A2": self.root / "workers" / "A2",
        }
        for path in self.worker_roots.values():
            path.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "init"], cwd=path, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        self.write_fake_provider_binary("copilot")
        self.write_fake_provider_binary("opencode")
        self.write_fake_provider_binary("claude-code")
        self.write_fake_provider_binary("ducc")

        self.port = find_free_port()
        self.config_path = self.root / "integration_config.yaml"
        self.config_path.write_text(self.render_config(), encoding="utf-8")
        self.base_url = f"http://127.0.0.1:{self.port}"

        env = os.environ.copy()
        env["PATH"] = f"{self.bin_dir}{os.pathsep}{env.get('PATH', '')}"
        env["GITHUB_TOKEN"] = "integration-token"
        env["OPENCODE_API_KEY"] = "integration-token"
        env["ANTHROPIC_API_KEY"] = "integration-token"
        self.env = env

        self.server = subprocess.Popen(
            _server_launch_cmd(self.runtime_script, [
                "serve",
                "--config",
                str(self.config_path),
                "--foreground",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
            ]),
            cwd=self.root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        wait_for(self.server_ready)

    def tearDown(self) -> None:
        if hasattr(self, "server") and self.server.poll() is None:
            try:
                read_json(f"{self.base_url}/api/stop-all", {})
            except Exception:
                pass
            try:
                self.server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.server.kill()
                self.server.wait(timeout=5)
        if hasattr(self, "server") and self.server.stdout is not None:
            self.server.stdout.close()
        self.temp_dir.cleanup()

    def write_fake_provider_binary(self, binary_name: str) -> None:
        binary_path = self.bin_dir / binary_name
        if binary_name == "ducc":
            binary_path.write_text(
                "#!/bin/sh\n"
                'if [ "$1" = "session-ok" ]; then\n'
                "  exit 0\n"
                "fi\n"
                'if [ "$1" = "session-fail" ]; then\n'
                '  echo "ducc session unavailable" >&2\n'
                "  exit 17\n"
                "fi\n"
                "printf '{\"phase\":\"ducc boot\",\"progress_pct\":27,\"usage\":{\"input_tokens\":300,\"output_tokens\":120,\"total_tokens\":420}}\\n'\n"
                "while [ $# -gt 0 ]; do\n"
                "  shift\n"
                "done\n"
                "sleep 30\n",
                encoding="utf-8",
            )
        else:
            binary_path.write_text(
                "#!/bin/sh\n"
                "printf '{\"phase\":\"worker boot\",\"progress_pct\":12,\"usage\":{\"input_tokens\":120,\"output_tokens\":35,\"total_tokens\":155}}\\n'\n"
                "while [ $# -gt 0 ]; do\n"
                "  shift\n"
                "done\n"
                "sleep 30\n",
                encoding="utf-8",
            )
        binary_path.chmod(0o755)

    def render_config(self) -> str:
        config = {
            "project": {
                "repository_name": "target-repo-it",
                "local_repo_root": str(self.project_root),
                "reference_workspace_root": str(self.paddle_root),
                "base_branch": "main",
                "integration_branch": "main",
                "manager_git_identity": {
                    "name": "Integration Manager",
                    "email": "integration-manager@example.com",
                },
                "dashboard": {
                    "host": "127.0.0.1",
                    "port": self.port,
                },
            },
            "providers": {
                "copilot": {
                    "api_key_env_name": "GITHUB_TOKEN",
                    "command_template": [
                        "copilot",
                        "--model",
                        "{model}",
                        "--prompt-file",
                        "{prompt_file}",
                        "--worktree",
                        "{worktree_path}",
                    ],
                },
                "opencode": {
                    "api_key_env_name": "OPENCODE_API_KEY",
                    "command_template": [
                        "opencode",
                        "--model",
                        "{model}",
                        "--prompt-file",
                        "{prompt_file}",
                        "--cwd",
                        "{worktree_path}",
                    ],
                },
                "claude_code": {
                    "api_key_env_name": "ANTHROPIC_API_KEY",
                    "command_template": [
                        "claude-code",
                        "--model",
                        "{model}",
                        "--prompt-file",
                        "{prompt_file}",
                        "--cwd",
                        "{worktree_path}",
                    ],
                },
                "ducc": {
                    "auth_mode": "session",
                    "prompt_transport": "stdin",
                    "session_probe_command": ["ducc", "session-ok"],
                    "command_template": [
                        "ducc",
                        "--model",
                        "{model}",
                    ],
                },
            },
            "task_policies": {
                "defaults": {
                    "task_type": "default",
                    "preferred_providers": ["ducc", "claude_code", "opencode", "copilot"],
                    "suggested_test_command": "uv run pytest tests/moe_test.py -k test_moe",
                },
                "types": {
                    "protocol": {
                        "preferred_providers": ["ducc", "claude_code", "opencode", "copilot"],
                        "suggested_test_command": "uv run pytest tests/reference_layers/standalone_moe_layer/tests/test_imports_and_interfaces.py",
                    },
                    "audit_hopper": {
                        "preferred_providers": ["ducc", "claude_code", "opencode", "copilot"],
                        "suggested_test_command": "uv run pytest tests/moe_test.py -k test_moe",
                    },
                },
                "rules": [
                    {"name": "protocol-a1", "task_type": "protocol", "task_ids": ["A1-001"]},
                    {"name": "audit-a2", "task_type": "audit_hopper", "task_ids": ["A2-001"]},
                ],
            },
            "resource_pools": {
                "copilot_pool": {
                    "priority": 100,
                    "provider": "copilot",
                    "model": "gpt-5.4",
                    "api_key": "replace_me_or_use_api_key_env",
                    "extra_env": {},
                },
                "opencode_pool": {
                    "priority": 400,
                    "provider": "opencode",
                    "model": "o4-mini",
                    "api_key": "replace_me_or_use_api_key_env",
                    "extra_env": {},
                },
                "claude_pool": {
                    "priority": 200,
                    "provider": "claude_code",
                    "model": "claude-sonnet-4-5",
                    "api_key": "replace_me_or_use_api_key_env",
                    "extra_env": {},
                },
                "ducc_pool": {
                    "priority": 350,
                    "provider": "ducc",
                    "model": "claude-sonnet-4-5",
                    "extra_env": {},
                },
            },
            "worker_defaults": {
                "resource_pool": "ducc_pool",
                "resource_pool_queue": ["ducc_pool"],
                "environment_type": "none",
                "sync_command": "none",
                "submit_strategy": "patch_handoff",
            },
            "workers": [
                {
                    "agent": "A1",
                    "task_id": "A1-001",
                    "branch": "integration-a1",
                    "worktree_path": str(self.worker_roots["A1"]),
                    "git_identity": {
                        "name": "Integration A1",
                        "email": "a1@example.com",
                    },
                },
                {
                    "agent": "A2",
                    "task_id": "A2-001",
                    "branch": "integration-a2",
                    "worktree_path": str(self.worker_roots["A2"]),
                    "git_identity": {
                        "name": "Integration A2",
                        "email": "a2@example.com",
                    },
                },
            ],
        }
        return json.dumps(config, indent=2) + "\n"

    def server_ready(self) -> bool:
        if self.server.poll() is not None:
            output = self.server.stdout.read() if self.server.stdout else ""
            raise RuntimeError(f"control plane exited early:\n{output}")
        try:
            state = read_json(f"{self.base_url}/api/state")
        except Exception:
            return False
        return bool(state.get("mode"))

    def fetch_state(self) -> dict[str, object]:
        return read_json(f"{self.base_url}/api/state")

    def wait_for_state_available(self) -> dict[str, object]:
        final_state: dict[str, object] = {}

        def predicate() -> bool:
            nonlocal final_state
            try:
                final_state = self.fetch_state()
            except Exception:
                return False
            return bool(final_state.get("mode"))

        wait_for(predicate, timeout=20, interval=0.5)
        return final_state

    def run_cli_command(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            _server_launch_cmd(self.runtime_script, [
                *args,
                "--port",
                str(self.port),
            ]),
            cwd=self.root,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )

    def session_state(self) -> dict[str, object]:
        session_state_path = self.warp_root / "runtime" / f"session_state_{self.port}.json"
        return json.loads(session_state_path.read_text(encoding="utf-8"))

    def write_state_payload(self, relative_path: str, payload: dict[str, object]) -> None:
        path = self.warp_root / relative_path
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def write_worker_handoff(self, agent: str, *, status: str, blockers: list[str], requested_unlocks: list[str], next_checkin: str, checkpoint_status: str, pending_work: list[str], dependencies: list[str], resume_instruction: str) -> None:
        status_lines = [
            f"# {agent} Status",
            "",
            f"Status: {status}",
            "",
            "## Blockers",
            *(f"- {item}" for item in (blockers or ["none"])),
            "",
            "## Requested Unlocks",
            *(f"- {item}" for item in (requested_unlocks or ["none"])),
            "",
            "## Next Check-in Condition",
            next_checkin,
            "",
        ]
        checkpoint_lines = [
            f"# {agent} Checkpoint",
            "",
            f"Status: {checkpoint_status}",
            "",
            "## Pending Work",
            *(f"- {item}" for item in (pending_work or ["none"])),
            "",
            "## Dependencies",
            *(f"- {item}" for item in (dependencies or ["none"])),
            "",
            "## Resume Instruction",
            resume_instruction,
            "",
        ]
        (self.warp_root / "status" / "agents" / f"{agent}.md").write_text("\n".join(status_lines), encoding="utf-8")
        (self.warp_root / "checkpoints" / "agents" / f"{agent}.md").write_text("\n".join(checkpoint_lines), encoding="utf-8")

    def install_dummy_dag(self) -> None:
        self.write_state_payload(
            "state/backlog.yaml",
            {
                "project": "dummy-a0-it",
                "manager": "A0",
                "phase": "dummy-a0",
                "items": [
                    {
                        "id": "A1-001",
                        "title": "Dummy root lane",
                        "task_type": "dummy_root",
                        "owner": "A1",
                        "status": "pending",
                        "claim_state": "unclaimed",
                        "claimed_by": "",
                        "plan_required": True,
                        "plan_state": "none",
                        "gate": "G0",
                        "priority": "P0",
                        "dependencies": [],
                        "outputs": ["root.txt"],
                        "done_when": ["root accepted or closed"],
                    },
                    {
                        "id": "A2-001",
                        "title": "Dummy dependent lane",
                        "task_type": "dummy_child",
                        "owner": "A2",
                        "status": "pending",
                        "claim_state": "unclaimed",
                        "claimed_by": "",
                        "plan_required": False,
                        "plan_state": "none",
                        "gate": "G1",
                        "priority": "P0",
                        "dependencies": ["A1-001"],
                        "outputs": ["child.txt"],
                        "done_when": ["child only runs after root"],
                    },
                ],
            },
        )

    def seed_worker_runtime(self, agent: str, *, runtime_status: str, heartbeat_state: str, evidence: str, escalation: str = "none") -> None:
        worker = self.worker_roots[agent]
        self.write_state_payload(
            "state/agent_runtime.yaml",
            {
                "workers": [
                    {
                        "agent": agent,
                        "task_id": f"{agent}-001",
                        "repository_name": "target-repo-it",
                        "resource_pool": "ducc_pool",
                        "provider": "ducc",
                        "model": "claude-sonnet-4-5",
                        "worktree_path": str(worker),
                        "branch": f"integration-{agent.lower()}",
                        "merge_target": "main",
                        "environment_type": "none",
                        "sync_command": "none",
                        "test_command": "pytest -q",
                        "submit_strategy": "patch_handoff",
                        "status": runtime_status,
                    }
                ]
            },
        )
        self.write_state_payload(
            "state/heartbeats.yaml",
            {
                "agents": [
                    {
                        "agent": agent,
                        "role": "worker",
                        "state": heartbeat_state,
                        "last_seen": "2026-03-16T03:00:00Z",
                        "evidence": evidence,
                        "expected_next_checkin": "manual",
                        "escalation": escalation,
                    }
                ]
            },
        )

    def wait_for_agent_state(self, expected_provider: str, expected_model: str | None = None) -> dict[str, object]:
        final_state: dict[str, object] = {}

        def predicate() -> bool:
            nonlocal final_state
            state = self.fetch_state()
            heartbeats = {item["agent"]: item for item in state["heartbeats"]["agents"]}
            runtime_workers = {item["agent"]: item for item in state["runtime"]["workers"]}
            for agent in ("A1", "A2"):
                heartbeat = heartbeats.get(agent, {})
                runtime = runtime_workers.get(agent, {})
                if heartbeat.get("state") != "healthy":
                    return False
                if runtime.get("provider") != expected_provider:
                    return False
                if expected_model is not None and runtime.get("model") != expected_model:
                    return False
            final_state = state
            return True

        wait_for(predicate, timeout=20, interval=1)
        return final_state

    def stop_workers(self) -> None:
        read_json(f"{self.base_url}/api/stop", {})
        wait_for(
            lambda: all(
                item.get("state") in {"offline", "not-started", "not_started"}
                for item in self.fetch_state()["heartbeats"]["agents"]
                if item.get("agent") in {"A1", "A2"}
            ),
            timeout=15,
            interval=1,
        )

    def test_project_section_validate_and_save(self) -> None:
        updated_local_repo_root = self.project_root / "repo-updated"
        updated_reference_workspace_root = self.paddle_root / "ref-updated"
        updated_local_repo_root.mkdir(parents=True, exist_ok=True)
        updated_reference_workspace_root.mkdir(parents=True, exist_ok=True)
        updated_project = {
            "repository_name": "target-repo-it-updated",
            "local_repo_root": str(updated_local_repo_root),
            "reference_workspace_root": str(updated_reference_workspace_root),
            "dashboard": {
                "host": "127.0.0.1",
                "port": self.port,
            },
        }

        validation_result = read_json(
            f"{self.base_url}/api/config/validate-section",
            {"section": "project", "value": updated_project},
        )
        self.assertTrue(validation_result["ok"])
        self.assertEqual(validation_result["validation_issues"], [])

        save_result = read_json(
            f"{self.base_url}/api/config/section",
            {"section": "project", "value": updated_project},
        )
        self.assertTrue(save_result["ok"])
        self.assertEqual(save_result["validation_issues"], [])

        state = self.fetch_state()
        project = state["config"]["project"]
        self.assertEqual(project["repository_name"], updated_project["repository_name"])
        self.assertEqual(project["local_repo_root"], updated_project["local_repo_root"])
        self.assertEqual(project["reference_workspace_root"], updated_project["reference_workspace_root"])

        saved_config_text = self.config_path.read_text(encoding="utf-8")
        self.assertIn(updated_project["local_repo_root"], saved_config_text)
        self.assertIn(updated_project["reference_workspace_root"], saved_config_text)

    def test_task_actions_drive_plan_and_review_flow(self) -> None:
        initial_state = self.fetch_state()
        backlog_items = {item["id"]: item for item in initial_state["backlog"]["items"]}
        self.assertEqual(backlog_items["A1-001"]["claim_state"], "unclaimed")

        claimed = read_json(
            f"{self.base_url}/api/tasks/action",
            {"task_id": "A1-001", "action": "claim", "agent": "A1", "note": "own protocol freeze"},
        )
        self.assertTrue(claimed["ok"])
        self.assertEqual(claimed["task"]["claimed_by"], "A1")
        self.assertEqual(claimed["task"]["claim_state"], "claimed")

        plan_request = read_json(
            f"{self.base_url}/api/tasks/action",
            {"task_id": "A1-001", "action": "submit_plan", "agent": "A1", "note": "freeze dtype names and public scale contract"},
        )
        self.assertTrue(plan_request["ok"])
        self.assertEqual(plan_request["task"]["plan_state"], "pending_review")

        state_with_plan = self.fetch_state()
        requests = {item["task_id"]: item for item in state_with_plan["a0_console"]["requests"] if item.get("task_id")}
        self.assertEqual(requests["A1-001"]["request_type"], "plan_review")

        approved = read_json(
            f"{self.base_url}/api/tasks/action",
            {"task_id": "A1-001", "action": "approve_plan", "agent": "A0", "note": "approved; continue with the narrowest public contract"},
        )
        self.assertTrue(approved["ok"])
        self.assertEqual(approved["task"]["plan_state"], "approved")

        review_request = read_json(
            f"{self.base_url}/api/tasks/action",
            {"task_id": "A1-001", "action": "request_review", "agent": "A1", "note": "protocol draft is ready for acceptance"},
        )
        self.assertTrue(review_request["ok"])
        self.assertEqual(review_request["task"]["status"], "review")

        state_with_review = self.fetch_state()
        requests = {item["task_id"]: item for item in state_with_review["a0_console"]["requests"] if item.get("task_id")}
        self.assertEqual(requests["A1-001"]["request_type"], "task_review")

        completed = read_json(
            f"{self.base_url}/api/tasks/action",
            {"task_id": "A1-001", "action": "complete", "agent": "A0", "note": "accepted for downstream work"},
        )
        self.assertTrue(completed["ok"])
        self.assertEqual(completed["task"]["status"], "completed")
        self.assertEqual(completed["task"]["claim_state"], "completed")

    def test_workflow_update_allows_a0_replan(self) -> None:
        updated = read_json(
            f"{self.base_url}/api/workflow/update",
            {
                "task_id": "A1-001",
                "agent": "A0",
                "note": "Shift this lane to A2 and hold for a revised plan.",
                "updates": {
                    "title": "Replanned protocol freeze",
                    "owner": "A2",
                    "claimed_by": "A2",
                    "status": "pending",
                    "claim_state": "claimed",
                    "gate": "gate-2",
                    "priority": "P0",
                    "dependencies": ["A2-001"],
                    "plan_required": True,
                    "plan_state": "pending_review",
                    "plan_summary": "Replan around reviewer feedback before code changes.",
                    "claim_note": "A0 reassigned this after feedback.",
                    "review_note": "waiting for refreshed plan",
                },
            },
        )
        self.assertTrue(updated["ok"])
        task = updated["task"]
        self.assertEqual(task["title"], "Replanned protocol freeze")
        self.assertEqual(task["owner"], "A2")
        self.assertEqual(task["claimed_by"], "A2")
        self.assertEqual(task["plan_state"], "pending_review")
        self.assertEqual(task["dependencies"], ["A2-001"])

        state = self.fetch_state()
        backlog_items = {item["id"]: item for item in state["backlog"]["items"]}
        self.assertEqual(backlog_items["A1-001"]["owner"], "A2")
        self.assertTrue(any(item.get("task_id") == "A1-001" for item in state["a0_console"]["requests"]))
        self.assertTrue(
            any(
                item.get("related_task_ids") == ["A1-001"] and item.get("to") in {"A2", "all"}
                for item in state["team_mailbox"]["messages"]
            )
        )

    def test_task_action_handler_recovers_from_malformed_requests(self) -> None:
        status_code, invalid_json = request_bytes_allow_error(f"{self.base_url}/api/tasks/action", b"{broken")
        self.assertEqual(status_code, 400)
        self.assertFalse(invalid_json["ok"])
        self.assertIn("invalid json", invalid_json["error"])

        status_code, unsupported_action = request_json_allow_error(
            f"{self.base_url}/api/tasks/action",
            {"task_id": "A1-001", "action": "warp-drive", "agent": "A1"},
        )
        self.assertEqual(status_code, 400)
        self.assertFalse(unsupported_action["ok"])
        self.assertIn("unsupported task action warp-drive", unsupported_action["error"])

        claimed = read_json(
            f"{self.base_url}/api/tasks/action",
            {"task_id": "A1-001", "action": "claim", "agent": "A1", "note": "recover after malformed action"},
        )
        self.assertTrue(claimed["ok"])
        self.assertEqual(claimed["task"]["claimed_by"], "A1")
        self.assertEqual(claimed["task"]["claim_state"], "claimed")

    def test_workflow_update_handler_recovers_from_malformed_requests(self) -> None:
        status_code, invalid_json = request_bytes_allow_error(f"{self.base_url}/api/workflow/update", b"{broken")
        self.assertEqual(status_code, 400)
        self.assertFalse(invalid_json["ok"])
        self.assertIn("invalid json", invalid_json["error"])

        status_code, bad_patch = request_json_allow_error(
            f"{self.base_url}/api/workflow/update",
            {
                "task_id": "A1-001",
                "agent": "A0",
                "updates": {"dependencies": 7},
            },
        )
        self.assertEqual(status_code, 400)
        self.assertFalse(bad_patch["ok"])
        self.assertEqual(bad_patch["error"], "workflow field dependencies must be a list or comma-separated string")

        updated = read_json(
            f"{self.base_url}/api/workflow/update",
            {
                "task_id": "A1-001",
                "agent": "A0",
                "note": "recover after malformed patch",
                "updates": {
                    "owner": "A2",
                    "claimed_by": "A2",
                    "status": "pending",
                    "claim_state": "claimed",
                    "dependencies": ["A2-001"],
                    "plan_required": True,
                    "plan_state": "pending_review",
                    "plan_summary": "fresh plan after malformed patch recovery",
                },
            },
        )
        self.assertTrue(updated["ok"])
        self.assertEqual(updated["task"]["owner"], "A2")
        self.assertEqual(updated["task"]["dependencies"], ["A2-001"])
        self.assertEqual(updated["task"]["plan_state"], "pending_review")

    def test_dummy_dag_cancel_closes_root_request_and_keeps_dependent_blocked(self) -> None:
        self.install_dummy_dag()

        plan_request = read_json(
            f"{self.base_url}/api/tasks/action",
            {"task_id": "A1-001", "action": "submit_plan", "agent": "A1", "note": "dummy root plan for cancellation"},
        )
        self.assertTrue(plan_request["ok"])

        state_with_request = self.fetch_state()
        requests = {item["task_id"]: item for item in state_with_request["a0_console"]["requests"] if item.get("task_id")}
        self.assertEqual(requests["A1-001"]["request_type"], "plan_review")
        self.assertIn("A1-001", state_with_request["cleanup"]["pending_plan_reviews"])
        backlog_before_cancel = {item["id"]: item for item in state_with_request["backlog"]["items"]}
        self.assertEqual(backlog_before_cancel["A2-001"]["status"], "pending")
        self.assertEqual(backlog_before_cancel["A2-001"]["dependencies"], ["A1-001"])

        cancelled = read_json(
            f"{self.base_url}/api/workflow/update",
            {
                "task_id": "A1-001",
                "agent": "A0",
                "note": "Cancel this root lane; do not advance dependent work.",
                "updates": {
                    "status": "closed",
                    "claim_state": "completed",
                    "plan_state": "none",
                    "review_note": "cancelled by A0",
                },
            },
        )
        self.assertTrue(cancelled["ok"])
        self.assertEqual(cancelled["task"]["status"], "closed")
        self.assertEqual(cancelled["task"]["plan_state"], "none")

        refreshed = self.fetch_state()
        self.assertFalse(any(item.get("task_id") == "A1-001" for item in refreshed["a0_console"]["requests"]))
        self.assertNotIn("A1-001", refreshed["cleanup"]["pending_plan_reviews"])
        backlog_after_cancel = {item["id"]: item for item in refreshed["backlog"]["items"]}
        self.assertEqual(backlog_after_cancel["A1-001"]["status"], "closed")
        self.assertEqual(backlog_after_cancel["A2-001"]["status"], "pending")
        self.assertEqual(backlog_after_cancel["A2-001"]["dependencies"], ["A1-001"])
        self.assertTrue(
            any(
                item.get("to") == "A1"
                and item.get("related_task_ids") == ["A1-001"]
                and "Cancel this root lane" in item.get("body", "")
                for item in refreshed["team_mailbox"]["messages"]
            )
        )

    def test_dummy_dag_unlock_and_intervention_requests_can_change_state_or_disappear(self) -> None:
        self.install_dummy_dag()
        self.write_worker_handoff(
            "A2",
            status="waiting",
            blockers=["waiting for config handoff"],
            requested_unlocks=["config.yaml"],
            next_checkin="after manager unlock",
            checkpoint_status="waiting",
            pending_work=["apply config and continue"],
            dependencies=["A1-001"],
            resume_instruction="unlock config then resume the lane",
        )
        self.seed_worker_runtime(
            "A2",
            runtime_status="waiting",
            heartbeat_state="healthy",
            evidence="blocked on config",
        )

        state = self.fetch_state()
        unlock_request = next(item for item in state["a0_console"]["requests"] if item["agent"] == "A2")
        self.assertEqual(unlock_request["request_type"], "unlock")
        self.assertEqual(unlock_request["response_state"], "pending")

        resumed = read_json(
            f"{self.base_url}/api/a0/respond",
            {
                "request_id": unlock_request["id"],
                "message": "Unlock approved; resume after config sync.",
                "action": "resume",
            },
        )
        self.assertTrue(resumed["ok"])

        resumed_state = self.fetch_state()
        resumed_request = next(item for item in resumed_state["a0_console"]["requests"] if item["id"] == unlock_request["id"])
        self.assertEqual(resumed_request["response_state"], "resume")

        self.write_worker_handoff(
            "A2",
            status="stale",
            blockers=["worker exited with 7"],
            requested_unlocks=[],
            next_checkin="manual intervention",
            checkpoint_status="stalled",
            pending_work=["recover worker and re-enter lane"],
            dependencies=["A1-001"],
            resume_instruction="inspect failure before relaunch",
        )
        self.seed_worker_runtime(
            "A2",
            runtime_status="stale",
            heartbeat_state="stale",
            evidence="process_exit",
            escalation="worker exited with 7",
        )

        intervention_state = self.fetch_state()
        self.assertFalse(any(item["id"] == unlock_request["id"] for item in intervention_state["a0_console"]["requests"]))
        intervention_request = next(item for item in intervention_state["a0_console"]["requests"] if item["agent"] == "A2")
        self.assertEqual(intervention_request["request_type"], "worker_intervention")
        self.assertEqual(intervention_request["response_state"], "pending")

        cancelled = read_json(
            f"{self.base_url}/api/a0/respond",
            {
                "request_id": intervention_request["id"],
                "message": "Cancel this intervention request; keep the lane parked.",
                "action": "cancel",
            },
        )
        self.assertTrue(cancelled["ok"])

        final_state = self.fetch_state()
        final_request = next(item for item in final_state["a0_console"]["requests"] if item["id"] == intervention_request["id"])
        self.assertEqual(final_request["response_state"], "cancel")
        self.assertIn("Cancel this intervention request", final_request["response_note"])

    def test_dummy_dag_replan_resets_stale_a0_request_state_and_reassigns_owner(self) -> None:
        self.install_dummy_dag()

        plan_request = read_json(
            f"{self.base_url}/api/tasks/action",
            {"task_id": "A1-001", "action": "submit_plan", "agent": "A1", "note": "initial dummy plan"},
        )
        self.assertTrue(plan_request["ok"])

        state = self.fetch_state()
        original_request = next(item for item in state["a0_console"]["requests"] if item.get("task_id") == "A1-001")
        self.assertEqual(original_request["response_state"], "pending")

        responded = read_json(
            f"{self.base_url}/api/a0/respond",
            {
                "request_id": original_request["id"],
                "message": "Resume with the original draft while I review it.",
                "action": "resume",
            },
        )
        self.assertTrue(responded["ok"])

        replanned = read_json(
            f"{self.base_url}/api/workflow/update",
            {
                "task_id": "A1-001",
                "agent": "A0",
                "note": "Reassign this root lane to A2 and require a fresh plan.",
                "updates": {
                    "owner": "A2",
                    "claimed_by": "A2",
                    "status": "pending",
                    "claim_state": "claimed",
                    "dependencies": ["A2-001"],
                    "plan_required": True,
                    "plan_state": "pending_review",
                    "plan_summary": "fresh plan after manager replan",
                    "claim_note": "manager replanned the lane",
                    "review_note": "old approval is stale",
                },
            },
        )
        self.assertTrue(replanned["ok"])
        self.assertEqual(replanned["task"]["owner"], "A2")
        self.assertEqual(replanned["task"]["claimed_by"], "A2")

        refreshed = self.fetch_state()
        replanned_request = next(item for item in refreshed["a0_console"]["requests"] if item.get("task_id") == "A1-001")
        self.assertEqual(replanned_request["agent"], "A2")
        self.assertEqual(replanned_request["response_state"], "pending")
        self.assertEqual(replanned_request["body"], "fresh plan after manager replan")
        self.assertTrue(
            any(
                item.get("related_task_ids") == ["A1-001"] and item.get("to") in {"A2", "all"}
                for item in refreshed["team_mailbox"]["messages"]
            )
        )

    def test_team_mailbox_send_and_acknowledge_flow(self) -> None:
        sent = read_json(
            f"{self.base_url}/api/team-mail/send",
            {
                "from": "A2",
                "to": "A0",
                "topic": "blocker",
                "body": "Need a gate decision before continuing Hopper audit.",
                "scope": "manager",
                "related_task_ids": ["A2-001"],
            },
        )
        self.assertTrue(sent["ok"])
        message_id = sent["message"]["id"]
        self.assertEqual(sent["message"]["ack_state"], "pending")

        state = self.fetch_state()
        self.assertGreaterEqual(state["team_mailbox"]["pending_count"], 1)
        self.assertTrue(any(item["id"] == message_id for item in state["a0_console"]["inbox"]))

        seen = read_json(f"{self.base_url}/api/team-mail/ack", {"message_id": message_id, "ack_state": "seen"})
        self.assertTrue(seen["ok"])
        self.assertEqual(seen["message"]["ack_state"], "seen")

        resolved = read_json(
            f"{self.base_url}/api/team-mail/ack",
            {"message_id": message_id, "ack_state": "resolved", "resolution_note": "A0 reviewed this blocker."},
        )
        self.assertTrue(resolved["ok"])
        self.assertEqual(resolved["message"]["ack_state"], "resolved")

        refreshed = self.fetch_state()
        self.assertFalse(any(item["id"] == message_id for item in refreshed["a0_console"]["inbox"]))

    def test_team_mail_handler_recovers_from_malformed_requests(self) -> None:
        status_code, invalid_json = request_bytes_allow_error(f"{self.base_url}/api/team-mail/send", b"{broken")
        self.assertEqual(status_code, 400)
        self.assertFalse(invalid_json["ok"])
        self.assertIn("invalid json", invalid_json["error"])

        status_code, missing_body = request_json_allow_error(
            f"{self.base_url}/api/team-mail/send",
            {"from": "A2", "to": "A0", "topic": "blocker"},
        )
        self.assertEqual(status_code, 400)
        self.assertFalse(missing_body["ok"])
        self.assertEqual(missing_body["error"], "body is required")

        sent = read_json(
            f"{self.base_url}/api/team-mail/send",
            {
                "from": "A2",
                "to": "A0",
                "topic": "blocker",
                "body": "Recovered from malformed request and need a decision.",
                "scope": "manager",
                "related_task_ids": ["A2-001", "A2-001"],
            },
        )
        self.assertTrue(sent["ok"])
        self.assertEqual(sent["message"]["ack_state"], "pending")
        self.assertEqual(sent["message"]["related_task_ids"], ["A2-001"])

        refreshed = self.fetch_state()
        self.assertTrue(any(item["id"] == sent["message"]["id"] for item in refreshed["a0_console"]["inbox"]))

    def test_single_worker_shutdown_updates_cleanup_state(self) -> None:
        launch_result = read_json(f"{self.base_url}/api/launch", {"restart": False})
        self.assertTrue(launch_result["ok"])
        self.wait_for_agent_state(expected_provider="ducc", expected_model="claude-sonnet-4-5")

        shutdown = read_json(
            f"{self.base_url}/api/workers/stop",
            {"agent": "A1", "note": "manager cleanup stop for protocol lane"},
        )
        self.assertTrue(shutdown["ok"])
        self.assertEqual(shutdown["agent"], "A1")
        self.assertTrue(shutdown["stopped"])
        self.assertFalse(shutdown["cleanup"]["ready"])
        self.assertIn("A2", shutdown["cleanup"]["active_workers"])

        state = self.fetch_state()
        heartbeats = {item["agent"]: item for item in state["heartbeats"]["agents"]}
        runtime_workers = {item["agent"]: item for item in state["runtime"]["workers"]}
        self.assertEqual(heartbeats["A1"]["state"], "offline")
        self.assertEqual(runtime_workers["A1"]["status"], "stopped")
        self.assertTrue(any(item.get("to") == "A1" for item in state["team_mailbox"]["messages"]))

    def test_team_cleanup_requires_ready_state(self) -> None:
        launch_result = read_json(f"{self.base_url}/api/launch", {"restart": False})
        self.assertTrue(launch_result["ok"])
        self.wait_for_agent_state(expected_provider="ducc", expected_model="claude-sonnet-4-5")

        status_code, blocked_cleanup = request_json_allow_error(
            f"{self.base_url}/api/team-cleanup",
            {"note": "release listener after active work finishes"},
        )
        self.assertEqual(status_code, 400)
        self.assertFalse(blocked_cleanup["ok"])
        self.assertIn("active workers must be stopped", blocked_cleanup["error"])

        self.stop_workers()

        plan_request = read_json(
            f"{self.base_url}/api/tasks/action",
            {"task_id": "A1-001", "action": "submit_plan", "agent": "A1", "note": "plan before cleanup"},
        )
        self.assertTrue(plan_request["ok"])
        status_code, blocked_plan_cleanup = request_json_allow_error(f"{self.base_url}/api/team-cleanup", {})
        self.assertEqual(status_code, 400)
        self.assertIn("pending plan approvals", blocked_plan_cleanup["error"])

        approved = read_json(
            f"{self.base_url}/api/tasks/action",
            {"task_id": "A1-001", "action": "approve_plan", "agent": "A0", "note": "plan accepted"},
        )
        self.assertTrue(approved["ok"])
        review_request = read_json(
            f"{self.base_url}/api/tasks/action",
            {"task_id": "A1-001", "action": "request_review", "agent": "A1", "note": "ready for acceptance"},
        )
        self.assertTrue(review_request["ok"])
        status_code, blocked_review_cleanup = request_json_allow_error(f"{self.base_url}/api/team-cleanup", {})
        self.assertEqual(status_code, 400)
        self.assertIn("pending task reviews", blocked_review_cleanup["error"])

        completed = read_json(
            f"{self.base_url}/api/tasks/action",
            {"task_id": "A1-001", "action": "complete", "agent": "A0", "note": "accepted for cleanup"},
        )
        self.assertTrue(completed["ok"])

        cleanup = read_json(
            f"{self.base_url}/api/team-cleanup",
            {"note": "cleanup gate passed; safe to release the team"},
        )
        self.assertTrue(cleanup["ok"])
        self.assertTrue(cleanup["cleanup"]["ready"])

        refreshed = self.fetch_state()
        self.assertTrue(any(item.get("scope") == "broadcast" and item.get("to") == "all" for item in refreshed["team_mailbox"]["messages"]))

    def test_team_cleanup_can_auto_release_listener(self) -> None:
        self.stop_workers()

        cleanup = read_json(
            f"{self.base_url}/api/team-cleanup",
            {"note": "cleanup gate passed; release listener automatically", "release_listener": True},
        )
        self.assertTrue(cleanup["ok"])
        self.assertTrue(cleanup["cleanup"]["ready"])
        self.assertTrue(cleanup["listener_release_requested"])

        wait_for(lambda: not port_is_listening(self.port), timeout=15, interval=0.5)
        wait_for(lambda: not self.session_state()["server"]["listener_active"], timeout=15, interval=0.5)

    def test_cleanup_blocks_on_mixed_file_locks_then_recovers(self) -> None:
        self.stop_workers()
        self.write_state_payload(
            "state/edit_locks.yaml",
            {
                "locks": [
                    {"path": "state/backlog.yaml", "owner": "A1", "state": "held"},
                    {"path": "state/agent_runtime.yaml", "owner": "", "state": "claimed"},
                ]
            },
        )

        status_code, blocked = request_json_allow_error(
            f"{self.base_url}/api/team-cleanup",
            {"note": "should block on mixed worker/global file locks"},
        )
        self.assertEqual(status_code, 400)
        self.assertFalse(blocked["ok"])
        self.assertIn("outstanding single-writer locks", blocked["error"])
        self.assertIn("state/backlog.yaml (A1)", blocked["error"])
        self.assertIn("state/agent_runtime.yaml (unassigned)", blocked["error"])

        cleanup_state = self.fetch_state()["cleanup"]
        workers_by_agent = {item["agent"]: item for item in cleanup_state["workers"]}
        self.assertIn("locks still held: state/backlog.yaml", workers_by_agent["A1"]["blockers"])
        self.assertEqual(cleanup_state["locked_files"][1]["owner"], "unassigned")

        self.write_state_payload("state/edit_locks.yaml", {"locks": []})
        recovered = read_json(
            f"{self.base_url}/api/team-cleanup",
            {"note": "locks cleared; cleanup can now release listener", "release_listener": True},
        )
        self.assertTrue(recovered["ok"])
        self.assertTrue(recovered["cleanup"]["ready"])
        self.assertTrue(recovered["listener_release_requested"])
        wait_for(lambda: not port_is_listening(self.port), timeout=15, interval=0.5)

    def test_stop_commands_are_idempotent_and_workers_can_relaunch(self) -> None:
        launch_result = read_json(f"{self.base_url}/api/launch", {"restart": False})
        self.assertTrue(launch_result["ok"])
        self.wait_for_agent_state(expected_provider="ducc", expected_model="claude-sonnet-4-5")

        first_stop = self.run_cli_command("stop-agents")
        first_payload = json.loads(first_stop.stdout)
        self.assertTrue(first_payload["ok"])
        self.assertEqual(sorted(first_payload["stopped"]), ["A1", "A2"])

        second_stop = self.run_cli_command("stop-agents")
        second_payload = json.loads(second_stop.stdout)
        self.assertTrue(second_payload["ok"])
        self.assertEqual(second_payload["stopped"], [])

        relaunch = read_json(f"{self.base_url}/api/launch", {"restart": False})
        self.assertTrue(relaunch["ok"])
        self.wait_for_agent_state(expected_provider="ducc", expected_model="claude-sonnet-4-5")

        stop_listener = self.run_cli_command("stop-listener")
        stop_listener_payload = json.loads(stop_listener.stdout)
        self.assertTrue(stop_listener_payload["ok"])
        self.assertTrue(stop_listener_payload["listener_released"])
        wait_for(lambda: not port_is_listening(self.port), timeout=10, interval=0.5)

        stop_listener_again = self.run_cli_command("stop-listener")
        stop_listener_again_payload = json.loads(stop_listener_again.stdout)
        self.assertTrue(stop_listener_again_payload["ok"])
        self.assertTrue(stop_listener_again_payload["listener_released"])

        stop_all = self.run_cli_command("stop-all")
        stop_all_payload = json.loads(stop_all.stdout)
        self.assertTrue(stop_all_payload["ok"])
        self.assertTrue(stop_all_payload["listener_released"])
        wait_for(lambda: self.server.poll() is not None, timeout=10, interval=0.5)

    def test_unknown_api_routes_return_json_errors(self) -> None:
        request = urllib.request.Request(f"{self.base_url}/api/does-not-exist", data=b"{}")
        request.add_header("Content-Type", "application/json")
        with self.assertRaises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(request, timeout=5)
        error = exc_info.exception
        self.assertEqual(error.code, 404)
        payload = json.loads(error.read().decode("utf-8"))
        error.close()
        self.assertFalse(payload["ok"])
        self.assertIn("unknown api route", payload["error"])

    def test_handler_error_recovery_keeps_peek_config_launch_and_stop_listener_semantics(self) -> None:
        status_code, invalid_json = request_bytes_allow_error(f"{self.base_url}/api/config", b"{broken")
        self.assertEqual(status_code, 400)
        self.assertFalse(invalid_json["ok"])
        self.assertIn("invalid json", invalid_json["error"])

        status_code, malformed_config = request_json_allow_error(
            f"{self.base_url}/api/config",
            {"config_text": "- not\n- a mapping\n"},
        )
        self.assertEqual(status_code, 400)
        self.assertFalse(malformed_config["ok"])
        self.assertEqual(malformed_config["error"], "top-level config must be a YAML mapping")

        status_code, peek_missing_lines = request_json_allow_error(f"{self.base_url}/api/peek", {"agent": "A1"})
        self.assertEqual(status_code, 400)
        self.assertFalse(peek_missing_lines["ok"])
        self.assertEqual(peek_missing_lines["error"], "lines list is required")

        status_code, bad_launch = request_json_allow_error(
            f"{self.base_url}/api/launch",
            {"restart": False, "strategy": "selected_model", "provider": "ducc"},
        )
        self.assertEqual(status_code, 400)
        self.assertFalse(bad_launch["ok"])
        self.assertIn("model", bad_launch["error"])

        peek_append = read_json(
            f"{self.base_url}/api/peek",
            {"agent": "A1", "lines": ["recovery line 1", "recovery line 2"]},
        )
        self.assertTrue(peek_append["ok"])

        config_text = json.dumps(json.loads(self.render_config()), indent=2) + "\n"
        config_save = read_json(f"{self.base_url}/api/config", {"config_text": config_text})
        self.assertTrue(config_save["ok"])
        self.assertEqual(config_save["validation_issues"], [])

        peek_state = read_json(f"{self.base_url}/api/peek")
        self.assertIn("A1", peek_state["peek"])
        self.assertTrue(any("recovery line 1" in line for line in peek_state["peek"]["A1"]))

        stop_listener = self.run_cli_command("stop-listener")
        stop_listener_payload = json.loads(stop_listener.stdout)
        self.assertTrue(stop_listener_payload["ok"])
        self.assertTrue(stop_listener_payload["listener_released"])
        wait_for(lambda: not port_is_listening(self.port), timeout=10, interval=0.5)

        session_state = self.session_state()
        self.assertFalse(session_state["server"]["listener_active"])

        stop_all = self.run_cli_command("stop-all")
        stop_all_payload = json.loads(stop_all.stdout)
        self.assertTrue(stop_all_payload["ok"])
        self.assertTrue(stop_all_payload["listener_released"])
        wait_for(lambda: self.server.poll() is not None, timeout=10, interval=0.5)

    def test_cli_api_smoke_suite_covers_config_text_peek_and_stop_listener_alias(self) -> None:
        config_payload = read_json(f"{self.base_url}/api/config")
        self.assertIn("config_text", config_payload)
        self.assertEqual(config_payload["config"]["project"]["repository_name"], "target-repo-it")

        peek_append = read_json(
            f"{self.base_url}/api/peek",
            {"agent": "A1", "lines": ["smoke line 1", "smoke line 2"]},
        )
        self.assertTrue(peek_append["ok"])
        self.assertEqual(peek_append["buffered"], 2)

        peek_state = read_json(f"{self.base_url}/api/peek")
        self.assertTrue(peek_state["ok"])
        self.assertIn("A1", peek_state["peek"])
        self.assertTrue(any("smoke line 1" in line for line in peek_state["peek"]["A1"]))

        config_text = json.dumps(json.loads(self.render_config()), indent=2) + "\n"
        config_save = read_json(f"{self.base_url}/api/config", {"config_text": config_text})
        self.assertTrue(config_save["ok"])
        self.assertEqual(config_save["validation_issues"], [])

        stop_listener = self.run_cli_command("stop-listener")
        stop_listener_payload = json.loads(stop_listener.stdout)
        self.assertTrue(stop_listener_payload["ok"])
        self.assertTrue(stop_listener_payload["listener_released"])
        wait_for(lambda: not port_is_listening(self.port), timeout=10, interval=0.5)

        session_state = self.session_state()
        self.assertFalse(session_state["server"]["listener_active"])

        stop_all = self.run_cli_command("stop-all")
        stop_all_payload = json.loads(stop_all.stdout)
        self.assertTrue(stop_all_payload["ok"])
        self.assertTrue(stop_all_payload["listener_released"])
        wait_for(lambda: self.server.poll() is not None, timeout=10, interval=0.5)

    def test_bootstrap_cold_start_config_save_then_launch_smoke(self) -> None:
        initial_stop = read_json(f"{self.base_url}/api/stop-all", {})
        self.assertTrue(initial_stop["ok"])
        wait_for(lambda: self.server.poll() is not None, timeout=15, interval=0.5)
        wait_for(lambda: not port_is_listening(self.port), timeout=10, interval=0.5)
        if self.server.stdout is not None:
            self.server.stdout.close()

        bootstrap_config_path = self.root / "bootstrap_local_config.yaml"
        self.server = subprocess.Popen(
            _server_launch_cmd(
                self.runtime_script,
                [
                    "up",
                    "--config",
                    str(bootstrap_config_path),
                    "--foreground",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(self.port),
                    "--bootstrap",
                ],
            ),
            cwd=self.root,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        wait_for(self.server_ready)

        state = self.fetch_state()
        self.assertTrue(state["mode"]["cold_start"])
        self.assertTrue(state["launch_blockers"])
        self.assertFalse(bootstrap_config_path.exists())

        bootstrap_config = json.loads(self.render_config())
        bootstrap_save = read_json(f"{self.base_url}/api/config", {"config": bootstrap_config})
        self.assertTrue(bootstrap_save["ok"])
        self.assertFalse(bootstrap_save["cold_start"])
        self.assertTrue(bootstrap_config_path.exists())

        launch_result = read_json(f"{self.base_url}/api/launch", {"restart": False})
        self.assertTrue(launch_result["ok"])
        self.wait_for_agent_state(expected_provider="ducc", expected_model="claude-sonnet-4-5")
        self.stop_workers()

    def test_stop_agents_cli_stops_workers_and_keeps_listener(self) -> None:
        launch_result = read_json(f"{self.base_url}/api/launch", {"restart": False})
        self.assertTrue(launch_result["ok"])
        self.wait_for_agent_state(expected_provider="ducc", expected_model="claude-sonnet-4-5")

        stop_result = self.run_cli_command("stop-agents")
        stop_payload = json.loads(stop_result.stdout)
        self.assertTrue(stop_payload["ok"])
        self.assertEqual(sorted(stop_payload["stopped"]), ["A1", "A2"])

        wait_for(lambda: port_is_listening(self.port), timeout=10, interval=0.5)
        state = self.fetch_state()
        heartbeats = {item["agent"]: item for item in state["heartbeats"]["agents"]}
        runtime_workers = {item["agent"]: item for item in state["runtime"]["workers"]}
        self.assertEqual(heartbeats["A1"]["state"], "offline")
        self.assertEqual(heartbeats["A2"]["state"], "offline")
        self.assertEqual(runtime_workers["A1"]["status"], "stopped")
        self.assertEqual(runtime_workers["A2"]["status"], "stopped")

        session_state = self.session_state()
        self.assertTrue(session_state["server"]["listener_active"])
        self.assertEqual(session_state["workers"], {})

    def test_detached_serve_can_start_and_stop_via_session_state(self) -> None:
        initial_stop = read_json(f"{self.base_url}/api/stop-all", {})
        self.assertTrue(initial_stop["ok"])
        wait_for(lambda: self.server.poll() is not None, timeout=15, interval=0.5)
        wait_for(lambda: not port_is_listening(self.port), timeout=10, interval=0.5)

        detached_result = self.run_cli_command(
            "serve",
            "--config",
            str(self.config_path),
            "--host",
            "127.0.0.1",
        )
        self.assertIn("control plane started in background", detached_result.stdout)
        wait_for(lambda: port_is_listening(self.port), timeout=15, interval=0.5)

        state = self.wait_for_state_available()
        self.assertEqual(state["project"]["repository_name"], "target-repo-it")
        session_state = self.session_state()
        self.assertTrue(session_state["server"]["listener_active"])
        detached_pid = int(session_state["server"]["pid"])
        self.assertGreater(detached_pid, 0)

        detached_stop = self.run_cli_command("stop-all")
        detached_stop_payload = json.loads(detached_stop.stdout)
        self.assertTrue(detached_stop_payload["ok"])
        self.assertTrue(detached_stop_payload["listener_released"])
        wait_for(lambda: not port_is_listening(self.port), timeout=15, interval=0.5)
        wait_for(lambda: not pid_is_running(detached_pid), timeout=15, interval=0.5)

    def test_detached_serve_fails_clearly_when_port_is_busy(self) -> None:
        result = subprocess.run(
            _server_launch_cmd(self.runtime_script, [
                "serve",
                "--config",
                str(self.config_path),
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
            ]),
            cwd=self.root,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn(f"port {self.port} is already in use", result.stderr)
        self.assertIn("stop the existing listener", result.stderr)

    def test_detached_serve_can_recover_after_port_busy_once_listener_is_released(self) -> None:
        busy = subprocess.run(
            _server_launch_cmd(self.runtime_script, [
                "serve",
                "--config",
                str(self.config_path),
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
            ]),
            cwd=self.root,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(busy.returncode, 1)
        self.assertIn(f"port {self.port} is already in use", busy.stderr)

        stop_listener = self.run_cli_command("stop-listener")
        stop_listener_payload = json.loads(stop_listener.stdout)
        self.assertTrue(stop_listener_payload["ok"])
        self.assertTrue(stop_listener_payload["listener_released"])
        wait_for(lambda: not port_is_listening(self.port), timeout=10, interval=0.5)

        recovered = self.run_cli_command(
            "serve",
            "--config",
            str(self.config_path),
            "--host",
            "127.0.0.1",
        )
        self.assertIn("control plane started in background", recovered.stdout)
        wait_for(lambda: port_is_listening(self.port), timeout=15, interval=0.5)

        state = self.wait_for_state_available()
        self.assertEqual(state["project"]["repository_name"], "target-repo-it")

        stop_all = self.run_cli_command("stop-all")
        stop_all_payload = json.loads(stop_all.stdout)
        self.assertTrue(stop_all_payload["ok"])
        self.assertTrue(stop_all_payload["listener_released"])
        wait_for(lambda: not port_is_listening(self.port), timeout=10, interval=0.5)

    def test_launch_failure_surfaces_missing_provider_credentials(self) -> None:
        current_state = self.fetch_state()
        broken_config = deepcopy(current_state["config"])
        broken_config["providers"]["copilot"]["api_key_env_name"] = "MISSING_GITHUB_TOKEN"
        broken_config["resource_pools"]["copilot_pool"]["api_key"] = "replace_me_or_use_api_key_env"

        save_result = read_json(f"{self.base_url}/api/config", {"config": broken_config})
        self.assertTrue(save_result["ok"])

        status_code, failed_launch = request_json_allow_error(
            f"{self.base_url}/api/launch",
            {"restart": False, "strategy": "selected_model", "provider": "copilot", "model": "gpt-5.4"},
        )
        self.assertEqual(status_code, 400)
        self.assertFalse(failed_launch["ok"])
        self.assertEqual(len(failed_launch["failures"]), 2)
        self.assertIn("launch failed for 2 worker(s)", failed_launch["error"])
        self.assertIn("A1: api key missing for pool copilot_pool", failed_launch["error"])
        self.assertTrue(all("api key missing" in item["error"] for item in failed_launch["failures"]))

        state = self.fetch_state()
        provider_queue = {item["resource_pool"]: item for item in state["provider_queue"]}
        self.assertFalse(provider_queue["copilot_pool"]["api_key_present"])
        self.assertIn("api key missing", provider_queue["copilot_pool"]["last_failure"])

        heartbeats = {item["agent"]: item for item in state["heartbeats"]["agents"]}
        runtime_workers = {item["agent"]: item for item in state["runtime"]["workers"]}
        self.assertEqual(heartbeats["A1"]["state"], "stale")
        self.assertEqual(heartbeats["A2"]["state"], "stale")
        self.assertIn("launch_failed", runtime_workers["A1"]["status"])
        self.assertIn("launch_failed", runtime_workers["A2"]["status"])

    def test_invalid_pool_references_are_repaired_before_launch(self) -> None:
        current_state = self.fetch_state()
        repaired_config = deepcopy(current_state["config"])
        repaired_config["providers"] = {"ducc": repaired_config["providers"]["ducc"]}
        repaired_config["resource_pools"] = {"ducc_pool": repaired_config["resource_pools"]["ducc_pool"]}
        repaired_config["project"]["initial_provider"] = "copilot"
        repaired_config["task_policies"]["defaults"]["preferred_providers"] = ["copilot", "ducc", "opencode"]
        for task_entry in repaired_config["task_policies"]["types"].values():
            if isinstance(task_entry, dict):
                task_entry["preferred_providers"] = ["claude_code", "ducc", "opencode"]
        repaired_config["worker_defaults"]["resource_pool_queue"] = ["claude_pool", "ducc_pool", "opencode_pool"]
        repaired_config["workers"][0]["resource_pool"] = "claude_pool"
        repaired_config["workers"][0]["resource_pool_queue"] = ["claude_pool", "ducc_pool", "opencode_pool"]
        repaired_config["workers"][1]["resource_pool"] = "claude_pool"

        save_result = read_json(f"{self.base_url}/api/config", {"config": repaired_config})
        self.assertTrue(save_result["ok"])

        state = self.fetch_state()
        saved_defaults = state["config"]["worker_defaults"]
        self.assertNotIn("initial_provider", state["config"]["project"])
        self.assertEqual(state["config"]["task_policies"]["defaults"]["preferred_providers"], ["ducc"])
        for task_entry in state["config"]["task_policies"]["types"].values():
            if isinstance(task_entry, dict) and "preferred_providers" in task_entry:
                self.assertEqual(task_entry["preferred_providers"], ["ducc"])
        self.assertEqual(saved_defaults["resource_pool_queue"], ["ducc_pool"])
        self.assertNotIn("resource_pool", state["config"]["workers"][0])
        self.assertEqual(state["config"]["workers"][0]["resource_pool_queue"], ["ducc_pool"])
        self.assertNotIn("resource_pool", state["config"]["workers"][1])

        launch_result = read_json(f"{self.base_url}/api/launch", {"restart": False})
        self.assertTrue(launch_result["ok"])
        self.wait_for_agent_state(expected_provider="ducc", expected_model="claude-sonnet-4-5")
        self.stop_workers()

    def test_session_backed_provider_launches_without_api_key(self) -> None:
        current_state = self.fetch_state()
        session_config = deepcopy(current_state["config"])
        session_config["worker_defaults"]["resource_pool_queue"] = ["ducc_pool"]

        save_result = read_json(f"{self.base_url}/api/config", {"config": session_config})
        self.assertTrue(save_result["ok"])

        launch_result = read_json(
            f"{self.base_url}/api/launch",
            {"restart": False, "strategy": "selected_model", "provider": "ducc", "model": "ducc-sonnet-it"},
        )
        self.assertTrue(launch_result["ok"])

        state = self.wait_for_agent_state(expected_provider="ducc", expected_model="ducc-sonnet-it")
        provider_queue = {item["resource_pool"]: item for item in state["provider_queue"]}
        self.assertEqual(provider_queue["ducc_pool"]["auth_mode"], "session")
        self.assertTrue(provider_queue["ducc_pool"]["auth_ready"])
        self.assertTrue(provider_queue["ducc_pool"]["launch_ready"])
        self.assertFalse(provider_queue["ducc_pool"]["api_key_present"])
        self.assertEqual(provider_queue["ducc_pool"]["recursion_guard"], "env+exec-wrapper")
        self.assertTrue(str(provider_queue["ducc_pool"]["launch_wrapper"]).endswith("ducc_single_layer.sh"))

        runtime_workers = {item["agent"]: item for item in state["runtime"]["workers"]}
        self.assertEqual(runtime_workers["A1"]["provider"], "ducc")
        self.assertEqual(runtime_workers["A2"]["provider"], "ducc")
        self.assertEqual(runtime_workers["A1"]["recursion_guard"], "env+exec-wrapper")
        self.assertTrue(str(runtime_workers["A1"]["launch_wrapper"]).endswith("ducc_single_layer.sh"))

        process_snapshot = state["processes"]["A1"]
        self.assertEqual(process_snapshot["recursion_guard"], "env+exec-wrapper")
        self.assertTrue(str(process_snapshot["wrapper_path"]).endswith("ducc_single_layer.sh"))
        self.assertEqual(process_snapshot["launch"]["recursion_guard"], "env+exec-wrapper")
        self.assertTrue(str(process_snapshot["launch"]["wrapper_path"]).endswith("ducc_single_layer.sh"))
        self.assertTrue(str(process_snapshot["command"]["binary"]).endswith("ducc_single_layer.sh"))
        self.assertTrue(process_snapshot["command"]["uses_wrapper"])
        self.assertNotIn("--prompt-file", process_snapshot["command"]["argv"])
        self.assertNotIn("--cwd", process_snapshot["command"]["argv"])
        self.assertEqual(process_snapshot["runtime"]["pid"], process_snapshot["pid"])
        self.assertEqual(process_snapshot["runtime"]["worktree_path"], process_snapshot["worktree_path"])
        self.assertEqual(process_snapshot["progress_pct"], 27)
        self.assertEqual(process_snapshot["usage"]["total_tokens"], 420)
        self.assertEqual(process_snapshot["phase"], "ducc boot")

        self.assertEqual(provider_queue["ducc_pool"]["active_workers"], 2)
        self.assertEqual(provider_queue["ducc_pool"]["usage"]["total_tokens"], 840)
        self.assertEqual(provider_queue["ducc_pool"]["progress_pct"], 27)
        self.assertEqual(len(provider_queue["ducc_pool"]["running_agents"]), 2)
        self.assertEqual(provider_queue["ducc_pool"]["running_agents"][0]["usage"]["total_tokens"], 420)

        self.stop_workers()

    def test_dashboard_exposes_manager_identity_and_handoff_details(self) -> None:
        state = self.fetch_state()
        runtime_workers = {item["agent"]: item for item in state["runtime"]["workers"]}
        self.assertEqual(runtime_workers["A0"]["provider"], "none")
        self.assertEqual(runtime_workers["A0"]["model"], "none")

        heartbeats = {item["agent"]: item for item in state["heartbeats"]["agents"]}
        self.assertEqual(heartbeats["A0"]["state"], "healthy")
        self.assertIn("polling", heartbeats["A0"]["evidence"])
        self.assertNotEqual(heartbeats["A0"]["last_seen"], "2026-03-10")

        manager_report = state["manager_report"]
        self.assertIn("Stage: live manager polling", manager_report)
        self.assertIn("Poll loop: every 5 seconds", manager_report)

        merge_queue = {item["agent"]: item for item in state["merge_queue"]}
        self.assertEqual(merge_queue["A1"]["checkpoint_status"], "not started")
        self.assertIn("needs baseline tensor contract from A6", merge_queue["A1"]["attention_summary"])
        self.assertIn(
            "needs baseline tensor contract from A6 for final public shape decisions",
            merge_queue["A1"]["blockers"],
        )
        self.assertIn("freeze dtype names", merge_queue["A1"]["pending_work"])
        self.assertIn("Start by producing the smallest protocol draft", merge_queue["A1"]["resume_instruction"])
        self.assertIn(
            "Update when protocol names and scale encoding proposal are ready for review",
            merge_queue["A1"]["next_checkin"],
        )

        a0_console = state["a0_console"]
        self.assertGreaterEqual(a0_console["pending_count"], 1)
        a0_requests = {item["agent"]: item for item in a0_console["requests"]}
        self.assertIn("needs baseline tensor contract from A6", a0_requests["A1"]["body"])

    def test_a0_console_records_user_reply(self) -> None:
        state = self.fetch_state()
        request = next((item for item in state["a0_console"]["requests"] if item["agent"] == "A1"), None)
        self.assertIsNotNone(request)

        response = read_json(
            f"{self.base_url}/api/a0/respond",
            {"request_id": request["id"], "message": "Approve protocol name freeze; resume with the current tensor contract.", "action": "resume"},
        )
        self.assertTrue(response["ok"])

        refreshed = self.fetch_state()
        a0_requests = {item["id"]: item for item in refreshed["a0_console"]["requests"]}
        self.assertEqual(a0_requests[request["id"]]["response_state"], "resume")
        self.assertIn("Approve protocol name freeze", a0_requests[request["id"]]["response_note"])
        self.assertTrue(any("Approve protocol name freeze" in item["body"] for item in refreshed["a0_console"]["messages"]))

    def test_process_exit_surfaces_escalation_in_attention_summary(self) -> None:
        failing_binary = self.bin_dir / "opencode"
        failing_binary.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
        failing_binary.chmod(0o755)

        launch_result = read_json(
            f"{self.base_url}/api/launch",
            {"restart": False, "strategy": "selected_model", "provider": "opencode", "model": "o4-mini"},
        )
        self.assertTrue(launch_result["ok"])

        wait_for(
            lambda: any(
                item.get("agent") == "A1" and item.get("status") == "stale"
                for item in self.fetch_state()["merge_queue"]
            ),
            timeout=15,
            interval=0.5,
        )

        state = self.fetch_state()
        merge_queue = {item["agent"]: item for item in state["merge_queue"]}
        self.assertNotEqual(merge_queue["A1"]["attention_summary"], "process_exit")
        self.assertIn("worker exited with 7", merge_queue["A1"]["attention_summary"])

    def test_launch_failure_can_be_replanned_into_a_clean_new_review_chain(self) -> None:
        self.install_dummy_dag()
        failing_binary = self.bin_dir / "opencode"
        failing_binary.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
        failing_binary.chmod(0o755)

        launch_result = read_json(
            f"{self.base_url}/api/launch",
            {"restart": False, "strategy": "selected_model", "provider": "opencode", "model": "o4-mini"},
        )
        self.assertTrue(launch_result["ok"])

        wait_for(
            lambda: any(
                item.get("agent") == "A1"
                and item.get("status") == "stale"
                and "worker exited with 7" in item.get("attention_summary", "")
                for item in self.fetch_state()["merge_queue"]
            ),
            timeout=15,
            interval=0.5,
        )

        failed_state = self.fetch_state()
        failed_request = next(item for item in failed_state["a0_console"]["requests"] if item["agent"] == "A1")
        self.assertEqual(failed_request["request_type"], "worker_intervention")
        self.assertIn("worker exited with 7", failed_request["body"])

        replanned = read_json(
            f"{self.base_url}/api/workflow/update",
            {
                "task_id": "A1-001",
                "agent": "A0",
                "note": "Long-term fix: move the failed root lane to A2 with a fresh review gate.",
                "updates": {
                    "owner": "A2",
                    "claimed_by": "A2",
                    "status": "pending",
                    "claim_state": "claimed",
                    "dependencies": ["A2-001"],
                    "plan_required": True,
                    "plan_state": "pending_review",
                    "plan_summary": "fresh launch fix plan owned by A2",
                    "claim_note": "replanned after A1 launch failure",
                    "review_note": "A1 failure is superseded by the new repair lane",
                },
            },
        )
        self.assertTrue(replanned["ok"])

        self.write_worker_handoff(
            "A1",
            status="parked",
            blockers=[],
            requested_unlocks=[],
            next_checkin="await reassignment",
            checkpoint_status="parked",
            pending_work=["capture failure notes only"],
            dependencies=[],
            resume_instruction="do not resume this failed launch lane",
        )
        self.write_worker_handoff(
            "A2",
            status="ready",
            blockers=[],
            requested_unlocks=[],
            next_checkin="after plan approval",
            checkpoint_status="claimed",
            pending_work=["implement the new repair plan after approval"],
            dependencies=["A2-001"],
            resume_instruction="wait for manager approval on the fresh repair plan",
        )

        runtime_after_fix = deepcopy(failed_state["runtime"])
        for item in runtime_after_fix["workers"]:
            if item.get("agent") == "A1":
                item["status"] = "stopped"
            elif item.get("agent") == "A2":
                item["status"] = "healthy"
        self.write_state_payload("state/agent_runtime.yaml", runtime_after_fix)

        heartbeats_after_fix = deepcopy(failed_state["heartbeats"])
        for item in heartbeats_after_fix["agents"]:
            if item.get("agent") == "A1":
                item["state"] = "offline"
                item["evidence"] = "lane parked after manager replan"
                item["escalation"] = "none"
            elif item.get("agent") == "A2":
                item["state"] = "healthy"
                item["evidence"] = "repair lane claimed"
                item["escalation"] = "none"
        self.write_state_payload("state/heartbeats.yaml", heartbeats_after_fix)

        refreshed = self.fetch_state()
        requests = refreshed["a0_console"]["requests"]
        self.assertFalse(any(item["id"] == failed_request["id"] for item in requests))
        replanned_request = next(item for item in requests if item.get("task_id") == "A1-001")
        self.assertEqual(replanned_request["agent"], "A2")
        self.assertEqual(replanned_request["request_type"], "plan_review")
        self.assertEqual(replanned_request["response_state"], "pending")
        self.assertEqual(replanned_request["body"], "fresh launch fix plan owned by A2")

        merge_queue = {item["agent"]: item for item in refreshed["merge_queue"]}
        self.assertNotIn("worker exited with 7", merge_queue["A1"]["attention_summary"])
        self.assertNotIn("worker exited with 7", merge_queue["A2"]["attention_summary"])
        self.assertEqual(merge_queue["A2"]["attention_summary"], "implement the new repair plan after approval")
        self.assertIn("A1-001", refreshed["cleanup"]["pending_plan_reviews"])
        self.assertTrue(
            any(
                item.get("related_task_ids") == ["A1-001"] and item.get("to") in {"A2", "all"}
                for item in refreshed["team_mailbox"]["messages"]
            )
        )

    def test_ducc_prompt_file_flag_is_sanitized_for_stale_configs(self) -> None:
        current_state = self.fetch_state()
        session_config = deepcopy(current_state["config"])
        session_config["providers"] = {"ducc": session_config["providers"]["ducc"]}
        session_config["resource_pools"] = {"ducc_pool": session_config["resource_pools"]["ducc_pool"]}
        session_config["worker_defaults"]["resource_pool_queue"] = ["ducc_pool"]
        session_config["providers"]["ducc"]["command_template"] = [
            "ducc",
            "--model",
            "{model}",
            "--prompt-file",
            "{prompt_file}",
            "--cwd",
            "{worktree_path}",
        ]

        save_result = read_json(f"{self.base_url}/api/config", {"config": session_config})
        self.assertTrue(save_result["ok"])

        launch_result = read_json(
            f"{self.base_url}/api/launch",
            {"restart": False, "strategy": "selected_model", "provider": "ducc", "model": "ducc-sonnet-it"},
        )
        self.assertTrue(launch_result["ok"])

        state = self.wait_for_agent_state(expected_provider="ducc", expected_model="ducc-sonnet-it")
        process_snapshot = state["processes"]["A1"]
        self.assertNotIn("--prompt-file", process_snapshot["command"]["argv"])
        self.assertNotIn("--cwd", process_snapshot["command"]["argv"])
        self.stop_workers()

    def test_session_probe_failure_surfaces_actionable_error(self) -> None:
        current_state = self.fetch_state()
        broken_config = deepcopy(current_state["config"])
        broken_config["providers"]["ducc"]["session_probe_command"] = ["ducc", "session-fail"]
        broken_config["worker_defaults"]["resource_pool_queue"] = ["ducc_pool"]

        save_result = read_json(f"{self.base_url}/api/config", {"config": broken_config})
        self.assertTrue(save_result["ok"])

        status_code, failed_launch = request_json_allow_error(
            f"{self.base_url}/api/launch",
            {"restart": False, "strategy": "selected_model", "provider": "ducc", "model": "ducc-sonnet-it"},
        )
        self.assertEqual(status_code, 400)
        self.assertFalse(failed_launch["ok"])
        self.assertIn("ducc session unavailable", failed_launch["error"])
        self.assertTrue(all("ducc session unavailable" in item["error"] for item in failed_launch["failures"]))

        state = self.fetch_state()
        provider_queue = {item["resource_pool"]: item for item in state["provider_queue"]}
        self.assertEqual(provider_queue["ducc_pool"]["auth_mode"], "session")
        self.assertFalse(provider_queue["ducc_pool"]["auth_ready"])
        self.assertFalse(provider_queue["ducc_pool"]["launch_ready"])
        self.assertIn("ducc session unavailable", provider_queue["ducc_pool"]["auth_detail"])

    def test_auth_failure_repair_relaunch_clears_stale_requests_and_attention(self) -> None:
        self.install_dummy_dag()
        broken_config = deepcopy(self.fetch_state()["config"])
        broken_config["providers"]["ducc"]["session_probe_command"] = ["ducc", "session-fail"]
        broken_config["worker_defaults"]["resource_pool_queue"] = ["ducc_pool"]
        self.assertTrue(read_json(f"{self.base_url}/api/config", {"config": broken_config})["ok"])

        status_code, failed_launch = request_json_allow_error(
            f"{self.base_url}/api/launch",
            {"restart": False, "strategy": "selected_model", "provider": "ducc", "model": "ducc-sonnet-it"},
        )
        self.assertEqual(status_code, 400)
        self.assertFalse(failed_launch["ok"])

        failed_state = self.fetch_state()
        failed_requests = [
            item
            for item in failed_state["a0_console"]["requests"]
            if item.get("agent") in {"A1", "A2"} and "ducc session unavailable" in item.get("body", "")
        ]
        self.assertTrue(any(item["request_type"] == "worker_intervention" for item in failed_requests))
        self.assertTrue(any(item["agent"] == "A1" for item in failed_requests))

        repaired_config = deepcopy(failed_state["config"])
        repaired_config["providers"]["ducc"]["session_probe_command"] = ["ducc", "session-ok"]
        self.assertTrue(read_json(f"{self.base_url}/api/config", {"config": repaired_config})["ok"])

        relaunched = read_json(
            f"{self.base_url}/api/launch",
            {"restart": False, "strategy": "selected_model", "provider": "ducc", "model": "ducc-sonnet-it"},
        )
        self.assertTrue(relaunched["ok"])
        recovered = self.wait_for_agent_state(expected_provider="ducc", expected_model="ducc-sonnet-it")

        self.assertFalse(
            any(
                item.get("agent") in {"A1", "A2"} and "ducc session unavailable" in item.get("body", "")
                for item in recovered["a0_console"]["requests"]
            )
        )
        merge_queue = {item["agent"]: item for item in recovered["merge_queue"]}
        self.assertNotIn("ducc session unavailable", merge_queue["A1"]["attention_summary"])
        self.assertNotIn("ducc session unavailable", merge_queue["A2"]["attention_summary"])
        provider_queue = {item["resource_pool"]: item for item in recovered["provider_queue"]}
        self.assertTrue(provider_queue["ducc_pool"]["auth_ready"])
        self.assertTrue(provider_queue["ducc_pool"]["launch_ready"])

        self.stop_workers()

    def test_initial_launch_provider_falls_back_to_configured_ducc(self) -> None:
        current_state = self.fetch_state()
        ducc_only_config = deepcopy(current_state["config"])
        ducc_only_config["providers"] = {"ducc": ducc_only_config["providers"]["ducc"]}
        ducc_only_config["resource_pools"] = {"ducc_pool": ducc_only_config["resource_pools"]["ducc_pool"]}
        ducc_only_config["worker_defaults"]["resource_pool_queue"] = ["ducc_pool"]
        ducc_only_config["task_policies"]["defaults"]["preferred_providers"] = ["ducc"]
        for entry in ducc_only_config["task_policies"]["types"].values():
            entry["preferred_providers"] = ["ducc"]

        save_result = read_json(f"{self.base_url}/api/config", {"config": ducc_only_config})
        self.assertTrue(save_result["ok"])

        state = self.fetch_state()
        self.assertEqual(state["launch_policy"]["initial_provider"], "ducc")
        self.assertEqual(state["launch_policy"]["default_provider"], "ducc")

        launch_result = read_json(f"{self.base_url}/api/launch", {"restart": False})
        self.assertTrue(launch_result["ok"])
        self.assertEqual(launch_result["launch_policy"]["provider"], "ducc")

        self.wait_for_agent_state(expected_provider="ducc", expected_model="claude-sonnet-4-5")
        self.stop_workers()

    def test_worker_prompt_forbids_nested_agent_orchestration(self) -> None:
        launch_result = read_json(f"{self.base_url}/api/launch", {"restart": False})
        self.assertTrue(launch_result["ok"])
        self.wait_for_agent_state(expected_provider="ducc", expected_model="claude-sonnet-4-5")

        prompt_path = self.warp_root / "runtime" / "generated_prompts" / "A1.md"
        prompt_text = prompt_path.read_text(encoding="utf-8")
        self.assertIn("Do not start nested control-plane sessions", prompt_text)
        self.assertIn("claude-code", prompt_text)
        self.assertIn("ducc", prompt_text)

        self.stop_workers()

    def test_worker_context_cannot_start_nested_control_plane(self) -> None:
        nested_port = find_free_port()
        nested_env = dict(self.env)
        nested_env["CONTROL_PLANE_WORKER_CONTEXT"] = "1"
        nested_env["CONTROL_PLANE_WORKER_AGENT"] = "A1"
        nested_env["CONTROL_PLANE_RECURSION_POLICY"] = "forbid-nested-control-plane"

        result = subprocess.run(
            _server_launch_cmd(self.runtime_script, [
                "up",
                "--config",
                str(self.config_path),
                "--host",
                "127.0.0.1",
                "--port",
                str(nested_port),
            ]),
            cwd=self.root,
            env=nested_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("refusing to start nested control plane", result.stderr)
        self.assertFalse(port_is_listening(nested_port))

    def test_silent_and_stop_all_cli_preserve_then_release_workers(self) -> None:
        launch_result = read_json(f"{self.base_url}/api/launch", {"restart": False})
        self.assertTrue(launch_result["ok"])
        self.wait_for_agent_state(expected_provider="ducc", expected_model="claude-sonnet-4-5")

        silent_result = self.run_cli_command("silent")
        silent_payload = json.loads(silent_result.stdout)
        self.assertTrue(silent_payload["ok"])
        self.assertTrue(silent_payload["listener_released"])
        wait_for(lambda: not port_is_listening(self.port), timeout=10, interval=0.5)

        session_state = self.session_state()
        self.assertFalse(session_state["server"]["listener_active"])
        worker_pids = [
            int(worker["pid"]) for worker in session_state["workers"].values() if int(worker.get("pid") or 0)
        ]
        self.assertTrue(worker_pids)
        self.assertTrue(all(pid > 0 for pid in worker_pids))

        stop_all_result = self.run_cli_command("stop-all")
        stop_all_payload = json.loads(stop_all_result.stdout)
        self.assertTrue(stop_all_payload["ok"])
        self.assertTrue(stop_all_payload["listener_released"])
        wait_for(lambda: not port_is_listening(self.port), timeout=10, interval=0.5)
        wait_for(lambda: self.server.poll() is not None, timeout=10, interval=0.5)

    def test_multi_agent_launch_policies_and_heartbeats(self) -> None:
        initial_state = self.fetch_state()
        self.assertEqual(initial_state["launch_policy"]["default_strategy"], "initial_provider")
        resolved_workers = {item["agent"]: item for item in initial_state["resolved_workers"]}
        self.assertEqual(
            resolved_workers["A1"]["test_command"],
            "uv run pytest tests/reference_layers/standalone_moe_layer/tests/test_imports_and_interfaces.py",
        )
        self.assertEqual(resolved_workers["A1"]["task_type"], "protocol")
        self.assertEqual(resolved_workers["A1"]["locked_pool"], "ducc_pool")
        self.assertEqual(resolved_workers["A2"]["test_command"], "uv run pytest tests/moe_test.py -k test_moe")
        self.assertEqual(resolved_workers["A2"]["task_type"], "audit_hopper")
        self.assertEqual(resolved_workers["A2"]["locked_pool"], "ducc_pool")

        launch_result = read_json(f"{self.base_url}/api/launch", {"restart": False})
        self.assertTrue(launch_result["ok"])
        self.assertEqual(launch_result["launch_policy"]["strategy"], "initial_provider")

        state = self.wait_for_agent_state(expected_provider="ducc", expected_model="claude-sonnet-4-5")
        runtime_workers = {item["agent"]: item for item in state["runtime"]["workers"]}
        self.assertEqual(runtime_workers["A1"]["status"], "healthy")
        self.assertEqual(runtime_workers["A2"]["status"], "healthy")

        self.stop_workers()

        selected_result = read_json(
            f"{self.base_url}/api/launch",
            {"restart": False, "strategy": "selected_model", "provider": "opencode", "model": "gpt-5.4-mini-it"},
        )
        self.assertTrue(selected_result["ok"])
        self.assertEqual(selected_result["launch_policy"]["provider"], "opencode")

        selected_state = self.wait_for_agent_state(expected_provider="opencode", expected_model="gpt-5.4-mini-it")
        selected_runtime = {item["agent"]: item for item in selected_state["runtime"]["workers"]}
        self.assertEqual(selected_runtime["A1"]["provider"], "opencode")
        self.assertEqual(selected_runtime["A2"]["provider"], "opencode")

        self.stop_workers()

        elastic_result = read_json(f"{self.base_url}/api/launch", {"restart": False, "strategy": "elastic"})
        self.assertTrue(elastic_result["ok"])
        elastic_state = self.wait_for_agent_state(expected_provider="ducc", expected_model="claude-sonnet-4-5")
        elastic_runtime = {item["agent"]: item for item in elastic_state["runtime"]["workers"]}
        self.assertEqual(elastic_runtime["A1"]["provider"], "ducc")
        self.assertEqual(elastic_runtime["A2"]["provider"], "ducc")

        self.stop_workers()


if __name__ == "__main__":
    unittest.main()
