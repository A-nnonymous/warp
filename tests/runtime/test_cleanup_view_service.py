from __future__ import annotations

import unittest

from runtime.cp.services import cleanup_locked_files, cleanup_review_maps, cleanup_status_view, cleanup_worker_row


class CleanupViewServiceTest(unittest.TestCase):
    def test_cleanup_review_maps_groups_pending_reviews_by_agent(self) -> None:
        backlog_items = [
            {"id": "A1-001", "claimed_by": "A1", "plan_state": "pending_review", "status": "pending"},
            {"id": "A1-002", "owner": "A1", "status": "review"},
            {"id": "A2-001", "claimed_by": "A2", "claim_state": "review"},
            {"id": "A3-001", "status": "done"},
        ]

        plan_reviews_by_agent, task_reviews_by_agent, pending_plan_reviews, pending_task_reviews = cleanup_review_maps(backlog_items)

        self.assertEqual(plan_reviews_by_agent, {"A1": ["A1-001"]})
        self.assertEqual(task_reviews_by_agent, {"A1": ["A1-002"], "A2": ["A2-001"]})
        self.assertEqual(pending_plan_reviews, ["A1-001"])
        self.assertEqual(pending_task_reviews, ["A1-002", "A2-001"])

    def test_cleanup_locked_files_filters_free_entries_and_groups_by_owner(self) -> None:
        locked_files, locked_files_by_owner = cleanup_locked_files(
            {
                "locks": [
                    {"path": "state/backlog.yaml", "owner": "A1", "state": "held"},
                    {"path": "state/runtime.yaml", "owner": "", "state": "claimed"},
                    {"path": "state/free.yaml", "owner": "A2", "state": "free"},
                    "bad",
                ]
            }
        )

        self.assertEqual(
            locked_files,
            [
                {"path": "state/backlog.yaml", "owner": "A1", "state": "held"},
                {"path": "state/runtime.yaml", "owner": "unassigned", "state": "claimed"},
            ],
        )
        self.assertEqual(
            locked_files_by_owner,
            {"A1": ["state/backlog.yaml"], "unassigned": ["state/runtime.yaml"]},
        )

    def test_cleanup_worker_row_shapes_blockers_and_status_fields(self) -> None:
        row = cleanup_worker_row(
            "A1",
            runtime_workers={"A1": {"status": "stopped"}},
            heartbeat_workers={"A1": {"state": "offline"}},
            active_workers=["A1"],
            plan_reviews_by_agent={"A1": ["A1-001"]},
            task_reviews_by_agent={"A1": ["A1-002"]},
            locked_files_by_owner={"A1": ["state/backlog.yaml"]},
        )

        self.assertFalse(row["ready"])
        self.assertTrue(row["active"])
        self.assertEqual(row["runtime_status"], "stopped")
        self.assertEqual(row["heartbeat_state"], "offline")
        self.assertEqual(
            row["blockers"],
            [
                "process is still alive",
                "pending plan approvals: A1-001",
                "pending task reviews: A1-002",
                "locks still held: state/backlog.yaml",
            ],
        )

    def test_cleanup_status_view_aggregates_global_and_worker_blockers(self) -> None:
        cleanup = cleanup_status_view(
            workers=[{"agent": "A1"}, {"agent": "A2"}],
            runtime_state={"workers": [{"agent": "A1", "status": "active"}, {"agent": "A2", "status": "stopped"}]},
            heartbeat_state={"agents": [{"agent": "A1", "state": "healthy"}, {"agent": "A2", "state": "offline"}]},
            backlog_items=[
                {"id": "A1-001", "claimed_by": "A1", "plan_state": "pending_review"},
                {"id": "A2-001", "claimed_by": "A2", "status": "review"},
            ],
            locks_state={"locks": [{"path": "state/backlog.yaml", "owner": "A2", "state": "held"}]},
            active_workers=["A1"],
            listener_active=True,
        )

        self.assertFalse(cleanup["ready"])
        self.assertTrue(cleanup["listener_active"])
        self.assertEqual(cleanup["active_workers"], ["A1"])
        self.assertEqual(cleanup["pending_plan_reviews"], ["A1-001"])
        self.assertEqual(cleanup["pending_task_reviews"], ["A2-001"])
        self.assertEqual(
            cleanup["blockers"],
            [
                "active workers must be stopped: A1",
                "pending plan approvals: A1-001",
                "pending task reviews: A2-001",
                "outstanding single-writer locks: state/backlog.yaml (A2)",
            ],
        )
        workers_by_agent = {item["agent"]: item for item in cleanup["workers"]}
        self.assertEqual(workers_by_agent["A1"]["blockers"][:2], ["process is still alive", "pending plan approvals: A1-001"])
        self.assertEqual(workers_by_agent["A2"]["blockers"], ["pending task reviews: A2-001", "locks still held: state/backlog.yaml"])

    def test_cleanup_status_view_handles_multi_worker_blocker_combinations(self) -> None:
        cleanup = cleanup_status_view(
            workers=[{"agent": "A1"}, {"agent": "A2"}, {"agent": "A3"}],
            runtime_state={
                "workers": [
                    {"agent": "A1", "status": "active"},
                    {"agent": "A2", "status": "waiting"},
                    {"agent": "A3", "status": "stopped"},
                ]
            },
            heartbeat_state={
                "agents": [
                    {"agent": "A1", "state": "healthy"},
                    {"agent": "A2", "state": "stale"},
                    {"agent": "A3", "state": "offline"},
                ]
            },
            backlog_items=[
                {"id": "A1-001", "claimed_by": "A1", "plan_state": "pending_review"},
                {"id": "A2-001", "claimed_by": "A2", "status": "review"},
            ],
            locks_state={
                "locks": [
                    {"path": "state/backlog.yaml", "owner": "A2", "state": "held"},
                    {"path": "state/runtime.yaml", "owner": "", "state": "claimed"},
                ]
            },
            active_workers=["A1", "A2"],
            listener_active=True,
        )

        self.assertFalse(cleanup["ready"])
        self.assertEqual(cleanup["active_workers"], ["A1", "A2"])
        self.assertEqual(cleanup["pending_plan_reviews"], ["A1-001"])
        self.assertEqual(cleanup["pending_task_reviews"], ["A2-001"])
        self.assertEqual(
            cleanup["blockers"],
            [
                "active workers must be stopped: A1, A2",
                "pending plan approvals: A1-001",
                "pending task reviews: A2-001",
                "outstanding single-writer locks: state/backlog.yaml (A2); state/runtime.yaml (unassigned)",
            ],
        )

        workers_by_agent = {item["agent"]: item for item in cleanup["workers"]}
        self.assertEqual(
            workers_by_agent["A1"]["blockers"],
            ["process is still alive", "pending plan approvals: A1-001"],
        )
        self.assertEqual(
            workers_by_agent["A2"]["blockers"],
            ["process is still alive", "pending task reviews: A2-001", "locks still held: state/backlog.yaml"],
        )
        self.assertEqual(workers_by_agent["A3"]["blockers"], [])
        self.assertEqual(cleanup["locked_files"][1]["owner"], "unassigned")


if __name__ == "__main__":
    unittest.main()
