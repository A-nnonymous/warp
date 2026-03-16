from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.cp.constants import PROVIDER_STATS_PATH
from runtime.cp.contracts import (
    A0ConsoleState,
    BacklogItem,
    CleanupState,
    CleanupWorkerState,
    DashboardState,
    LaunchPolicyState,
    ManagerControlState,
    ProcessCommand,
    ProcessSnapshot,
    ProviderQueueItem,
    RunningAgentTelemetry,
    TelemetryUsage,
    RuntimeWorkerEntry,
    TeamMailboxMessage,
    WorkerHandoffSummary,
    WorkflowPatch,
)
from runtime.cp.services.provider_queue import provider_queue_item
from runtime.cp.services.telemetry_views import command_contract, normalize_usage, process_snapshot_entry, running_agent_telemetry, summarize_pool_usage
from runtime.cp.stores import (
    BacklogStore,
    HeartbeatStore,
    LockStore,
    MailboxStore,
    ManagerConsoleStore,
    ProviderStatsStore,
    RuntimeStore,
)


class ControlPlaneArchitectureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="warp-arch-")
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_contracts_are_runtime_typing_shapes(self) -> None:
        backlog_item: BacklogItem = {"id": "A1-001", "status": "pending", "title": "Task"}
        runtime_worker: RuntimeWorkerEntry = {"agent": "A1", "resource_pool": "ducc_pool", "status": "active"}
        cleanup_worker: CleanupWorkerState = {"agent": "A1", "ready": False, "blockers": ["active workers"]}
        cleanup_state: CleanupState = {"ready": False, "blockers": ["active workers"], "workers": [cleanup_worker]}
        workflow_patch: WorkflowPatch = {"status": "review", "dependencies": ["A0-001"]}
        mailbox_message: TeamMailboxMessage = {"from": "A1", "to": "A0", "topic": "status_note"}
        a0_console: A0ConsoleState = {"requests": [], "messages": [], "inbox": [], "pending_count": 0}
        handoff: WorkerHandoffSummary = {"checkpoint_status": "checkpointed", "pending_work": ["merge patch"]}
        control: ManagerControlState = {"worker_count": 1, "active_agents": ["A1"]}
        launch_policy: LaunchPolicyState = {"default_strategy": "elastic", "available_strategies": ["elastic"]}
        usage: TelemetryUsage = normalize_usage({"input_tokens": 12, "output_tokens": 4, "total_tokens": 16})
        command: ProcessCommand = command_contract(["ducc"], "")
        running_agent: RunningAgentTelemetry = running_agent_telemetry("A1", {"phase": "boot", "usage": usage})
        process_snapshot: ProcessSnapshot = process_snapshot_entry(
            resource_pool="ducc_pool",
            provider="ducc",
            model="claude",
            pid=123,
            alive=True,
            returncode=None,
            wrapper_path="",
            recursion_guard="env-only",
            worktree_path="/tmp/worktree",
            log_path="/tmp/worker.log",
            command=["ducc"],
            telemetry={"phase": "boot", "usage": usage},
        )
        pool_usage = summarize_pool_usage([running_agent])
        provider_queue_item_view: ProviderQueueItem = provider_queue_item(
            pool_name="ducc_pool",
            provider_name="ducc",
            model="claude",
            priority=50,
            binary="ducc",
            binary_found=True,
            recursion_guard="env-only",
            launch_wrapper="",
            auth_mode="api_key",
            auth_ready=True,
            auth_detail="api key configured",
            api_key_present=True,
            latency_ms=12.0,
            work_quality=0.9,
            pool_usage=pool_usage,
            last_failure="",
        )
        dashboard: DashboardState = {
            "updated_at": "2026-03-16T00:00:00Z",
            "last_event": "boot",
            "mode": {"state": "configured", "cold_start": False, "listener_active": True},
            "project": {"repository_name": "warp"},
            "commands": {"serve": "python serve", "up": "python up"},
            "launch_policy": launch_policy,
            "manager_report": "ok",
            "runtime": {"workers": [runtime_worker]},
            "heartbeats": {"agents": [{"agent": "A0", "state": "healthy"}]},
            "backlog": {"items": [backlog_item]},
            "gates": {"gates": [{"id": "G1", "status": "open"}]},
            "processes": {"A1": process_snapshot},
            "provider_queue": [provider_queue_item_view],
            "resolved_workers": [],
            "merge_queue": [{"agent": "A1", "checkpoint_status": handoff["checkpoint_status"]}],
            "a0_console": a0_console,
            "team_mailbox": {"messages": [mailbox_message], "pending_count": 1},
            "cleanup": cleanup_state,
            "config": {"project": {"repository_name": "warp"}},
            "config_text": "project: warp",
            "validation_errors": [],
            "launch_blockers": [],
            "peek": {},
        }
        self.assertEqual(backlog_item["id"], "A1-001")
        self.assertEqual(runtime_worker["agent"], "A1")
        self.assertIn("active workers", cleanup_state["blockers"])
        self.assertEqual(cleanup_state["workers"][0]["agent"], "A1")
        self.assertEqual(workflow_patch["status"], "review")
        self.assertEqual(mailbox_message["from"], "A1")
        self.assertEqual(a0_console["pending_count"], 0)
        self.assertEqual(launch_policy["default_strategy"], "elastic")
        self.assertEqual(process_snapshot["provider"], "ducc")
        self.assertEqual(process_snapshot["command"]["binary"], "ducc")
        self.assertEqual(provider_queue_item_view["resource_pool"], "ducc_pool")
        self.assertEqual(provider_queue_item_view["running_agents"][0]["usage"]["total_tokens"], 16)
        self.assertEqual(control["worker_count"], 1)
        self.assertEqual(dashboard["runtime"]["workers"][0]["agent"], "A1")

    def test_backlog_store_normalizes_claim_and_status(self) -> None:
        store = BacklogStore(self.root / "backlog.yaml")
        persisted = store.persist(
            {
                "project": "demo",
                "items": [
                    {
                        "id": "A1-001",
                        "title": "Example",
                        "status": "in_progress",
                        "claimed_by": "A1",
                        "dependencies": ["A0", "A0", "A2"],
                    }
                ],
            }
        )
        item = persisted["items"][0]
        self.assertEqual(item["claim_state"], "in_progress")
        self.assertEqual(item["status"], "in_progress")
        self.assertEqual(item["dependencies"], ["A0", "A2"])
        loaded = store.load()
        self.assertEqual(loaded["items"][0]["id"], "A1-001")

    def test_mailbox_store_normalizes_scope_and_ack_state(self) -> None:
        store = MailboxStore(self.root / "team_mailbox.yaml")
        persisted = store.persist(
            {
                "messages": [
                    {
                        "from": "A1",
                        "to": "A0",
                        "scope": "weird",
                        "topic": "status_note",
                        "body": "hello",
                        "ack_state": "bogus",
                        "related_task_ids": ["A1-001", "A1-001"],
                    }
                ]
            }
        )
        message = persisted["messages"][0]
        self.assertEqual(message["scope"], "direct")
        self.assertEqual(message["ack_state"], "pending")
        self.assertEqual(message["related_task_ids"], ["A1-001"])
        self.assertTrue(message["id"])

    def test_runtime_store_normalizes_worker_entries(self) -> None:
        store = RuntimeStore(self.root / "agent_runtime.yaml")
        persisted = store.persist({"workers": [{"agent": "A1", "resource_pool": "", "provider": "", "model": ""}]})
        worker = persisted["workers"][0]
        self.assertEqual(worker["resource_pool"], "unassigned")
        self.assertEqual(worker["provider"], "unassigned")
        self.assertEqual(worker["model"], "unassigned")

    def test_heartbeat_store_round_trip(self) -> None:
        store = HeartbeatStore(self.root / "heartbeats.yaml")
        persisted = store.persist({"agents": [{"agent": "A1", "state": "healthy", "evidence": "log", "expected_next_checkin": "soon", "escalation": "none"}]})
        self.assertEqual(persisted["agents"][0]["state"], "healthy")
        loaded = store.load()
        self.assertEqual(loaded["agents"][0]["agent"], "A1")

    def test_lock_store_round_trip(self) -> None:
        store = LockStore(self.root / "edit_locks.yaml")
        persisted = store.persist({"policy": {"single_writer": True}, "locks": [{"path": "state/backlog.yaml", "owner": "A1", "state": "held"}]})
        self.assertEqual(persisted["locks"][0]["owner"], "A1")
        loaded = store.load()
        self.assertEqual(loaded["policy"]["single_writer"], True)

    def test_provider_stats_store_applies_default_entry_factory(self) -> None:
        store = ProviderStatsStore(self.root / PROVIDER_STATS_PATH.name, lambda: {"score": 0, "latency_ms": None})
        persisted = store.persist({"ducc_pool": {"score": 3}})
        self.assertEqual(persisted["ducc_pool"]["score"], 3)
        loaded = store.load()
        self.assertEqual(loaded["ducc_pool"]["score"], 3)
        self.assertIsNone(loaded["ducc_pool"]["latency_ms"])

    def test_manager_console_store_round_trip(self) -> None:
        store = ManagerConsoleStore(self.root / "manager_console.yaml")
        persisted = store.persist(
            {
                "requests": {"r1": {"status": "pending", "request_type": "task_review"}, 7: "bad"},
                "messages": [{"body": "hi", "direction": "user_to_a0"}, "bad"],
            }
        )
        self.assertIn("r1", persisted["requests"])
        self.assertNotIn("7", persisted["requests"])
        loaded = store.load()
        self.assertEqual(loaded["messages"][0]["body"], "hi")
        self.assertEqual(len(loaded["messages"]), 1)


if __name__ == "__main__":
    unittest.main()
