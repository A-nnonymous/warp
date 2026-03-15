from __future__ import annotations

import unittest

from runtime.cp.services import compute_manager_control_state, summarize_worker_handoff


class DashboardSummaryServiceTest(unittest.TestCase):
    def test_compute_manager_control_state_classifies_agents(self) -> None:
        workers = [
            {"agent": "A1", "task_id": "A1-001"},
            {"agent": "A2", "task_id": "A2-001"},
            {"agent": "A3", "task_id": "A3-001"},
            {"agent": "A4", "task_id": "A4-001"},
        ]
        runtime_state = {
            "workers": [
                {"agent": "A1", "status": "active"},
                {"agent": "A2", "status": "stopped"},
                {"agent": "A3", "status": "launch_failed: port busy"},
                {"agent": "A4", "status": "stopped"},
            ]
        }
        heartbeat_state = {
            "agents": [
                {"agent": "A1", "state": "healthy"},
                {"agent": "A2", "state": "healthy"},
                {"agent": "A3", "state": "healthy"},
                {"agent": "A4", "state": "healthy"},
            ]
        }
        backlog_items = [
            {"id": "A0-000", "status": "completed"},
            {"id": "A1-001", "status": "active"},
            {"id": "A2-001", "status": "pending"},
            {"id": "A3-001", "status": "pending"},
            {"id": "A4-001", "status": "blocked", "dependencies": ["A0-000", "A9-999"]},
        ]
        by_task_id = {item["id"]: item for item in backlog_items}

        control = compute_manager_control_state(
            workers=workers,
            runtime_state=runtime_state,
            heartbeat_state=heartbeat_state,
            backlog_items=backlog_items,
            task_record_for_worker=lambda worker: by_task_id.get(worker.get("task_id", ""), {}),
        )

        self.assertEqual(control["worker_count"], 4)
        self.assertEqual(control["active_agents"], ["A1"])
        self.assertEqual(control["runnable_agents"], ["A2"])
        self.assertEqual(control["attention_agents"], ["A3"])
        self.assertEqual(control["blocked_agents"], ["A4"])

    def test_summarize_worker_handoff_prefers_runtime_failure_then_sections(self) -> None:
        summary = summarize_worker_handoff(
            runtime_entry={"status": "launch_failed: provider missing"},
            heartbeat={
                "state": "error",
                "evidence": "process_exit",
                "escalation": "re-auth provider",
                "expected_next_checkin": "manual",
            },
            status_meta={"status": "waiting"},
            status_sections={
                "blockers": "- missing token\n- port busy\n",
                "requested unlocks": "- config.yaml\n",
                "next check-in condition": "after auth is restored",
            },
            checkpoint_meta={"status": "checkpointed"},
            checkpoint_sections={
                "pending work": "- retry launch\n",
                "dependencies": "- A0-100\n- A0-100\n",
                "resume instruction": "rerun launch once provider is ready",
            },
            parse_list=lambda text: [line.removeprefix("- ").strip() for line in text.splitlines() if line.strip()],
            parse_paragraph=lambda text: str(text).strip(),
        )

        self.assertEqual(summary["checkpoint_status"], "checkpointed")
        self.assertEqual(summary["attention_summary"], "launch_failed: provider missing")
        self.assertEqual(summary["blockers"], ["missing token", "port busy"])
        self.assertEqual(summary["requested_unlocks"], ["config.yaml"])
        self.assertEqual(summary["pending_work"], ["retry launch"])
        self.assertEqual(summary["dependencies"], ["A0-100"])
        self.assertEqual(summary["resume_instruction"], "rerun launch once provider is ready")
        self.assertEqual(summary["next_checkin"], "after auth is restored")


if __name__ == "__main__":
    unittest.main()
