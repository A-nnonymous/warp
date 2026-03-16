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

    def test_compute_manager_control_state_marks_stale_and_dependency_blocked_workers(self) -> None:
        control = compute_manager_control_state(
            workers=[{"agent": "A5", "task_id": "A5-001"}, {"agent": "A6", "task_id": "A6-001"}],
            runtime_state=None,
            heartbeat_state={"agents": [{"agent": "A5", "state": "stale"}, {"agent": "A6", "state": "healthy"}]},
            backlog_items=[{"id": "A0-010", "status": "done"}, {"id": "A6-001", "status": "pending", "dependencies": ["A0-999"]}],
            task_record_for_worker=lambda worker: {
                "A5": {"id": "A5-001", "status": "pending"},
                "A6": {"id": "A6-001", "status": "pending", "dependencies": ["A0-999"]},
            }.get(worker["agent"], {}),
        )
        self.assertEqual(control["attention_agents"], ["A5"])
        self.assertEqual(control["blocked_agents"], ["A6"])

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

    def test_summarize_worker_handoff_covers_process_exit_blockers_pending_and_fallbacks(self) -> None:
        parse_list = lambda text: [line.removeprefix("- ").strip() for line in text.splitlines() if line.strip()]
        parse_paragraph = lambda text: str(text).strip()

        exited = summarize_worker_handoff(
            runtime_entry={"status": "stopped"},
            heartbeat={"state": "error", "evidence": "process_exit", "escalation": "manual restart", "expected_next_checkin": "soon"},
            parse_list=parse_list,
            parse_paragraph=parse_paragraph,
        )
        self.assertEqual(exited["attention_summary"], "manual restart")
        self.assertEqual(exited["checkpoint_status"], "error")
        self.assertEqual(exited["next_checkin"], "soon")

        blocked = summarize_worker_handoff(
            runtime_entry={"status": "stopped"},
            heartbeat={"state": "healthy", "evidence": "no runtime heartbeat yet", "expected_next_checkin": "later"},
            status_sections={"blockers": "- waiting on config\n"},
            parse_list=parse_list,
            parse_paragraph=parse_paragraph,
        )
        self.assertEqual(blocked["attention_summary"], "waiting on config")

        pending = summarize_worker_handoff(
            runtime_entry={"status": "stopped"},
            heartbeat={"state": "healthy", "evidence": "", "expected_next_checkin": "later"},
            checkpoint_sections={"pending work": "- rerun tests\n"},
            parse_list=parse_list,
            parse_paragraph=parse_paragraph,
        )
        self.assertEqual(pending["attention_summary"], "rerun tests")

        fallback = summarize_worker_handoff(
            runtime_entry={"status": "stopped"},
            heartbeat={"state": "stale", "evidence": "heartbeat lag", "escalation": "", "expected_next_checkin": "later"},
            parse_list=parse_list,
            parse_paragraph=parse_paragraph,
        )
        self.assertEqual(fallback["attention_summary"], "heartbeat lag")

        quiet = summarize_worker_handoff(
            runtime_entry={"status": "stopped"},
            heartbeat={"state": "", "evidence": "no runtime heartbeat yet", "expected_next_checkin": "manual"},
            parse_list=parse_list,
            parse_paragraph=parse_paragraph,
        )
        self.assertEqual(quiet["attention_summary"], "")
        self.assertEqual(quiet["checkpoint_status"], "unknown")


if __name__ == "__main__":
    unittest.main()
