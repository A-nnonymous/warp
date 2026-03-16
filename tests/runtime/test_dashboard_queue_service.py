from __future__ import annotations

import unittest

from runtime.cp.services import build_a0_request_catalog, build_merge_queue, build_team_mailbox_catalog
from runtime.cp.utils import slugify


class DashboardQueueServiceTest(unittest.TestCase):
    def test_build_merge_queue_shapes_manager_facing_rows(self) -> None:
        workers = [
            {"agent": "A1", "branch": "feat/a1", "submit_strategy": "patch_handoff", "git_identity": {"name": "Worker One", "email": "a1@example.com"}},
            {"agent": "A2", "branch": "feat/a2"},
        ]
        runtime_state = {"workers": [{"agent": "A1", "status": "active"}]}
        heartbeat_state = {"agents": [{"agent": "A2", "state": "stale"}]}
        handoff_by_agent = {
            "A1": {
                "checkpoint_status": "checkpointed",
                "attention_summary": "awaiting review",
                "blockers": ["need A0 signoff"],
                "pending_work": ["land protocol draft"],
                "requested_unlocks": ["state/backlog.yaml"],
                "dependencies": ["A0-100"],
                "resume_instruction": "resume after signoff",
                "next_checkin": "tomorrow",
            },
            "A2": {"checkpoint_status": "waiting"},
        }

        queue = build_merge_queue(
            workers,
            runtime_state,
            heartbeat_state,
            handoff_by_agent,
            integration_branch="main",
            manager_identity={"name": "Manager", "email": "a0@example.com"},
            worker_identity_display=lambda worker: (
                f"{worker['git_identity']['name']} <{worker['git_identity']['email']}>"
                if worker.get("git_identity")
                else "environment default"
            ),
        )

        self.assertEqual(queue[0]["manager_identity"], "Manager <a0@example.com>")
        self.assertEqual(queue[0]["worker_identity"], "Worker One <a1@example.com>")
        self.assertEqual(queue[0]["status"], "active")
        self.assertEqual(queue[0]["requested_unlocks"], ["state/backlog.yaml"])
        self.assertEqual(queue[1]["status"], "stale")
        self.assertEqual(queue[1]["worker_identity"], "environment default")
        self.assertEqual(queue[1]["manager_action"], "A0 merges feat/a2 into main")

    def test_build_a0_request_catalog_merges_reviews_interventions_unlocks_and_inbox(self) -> None:
        backlog_items = [
            {
                "id": "A1-001",
                "claimed_by": "A1",
                "status": "pending",
                "plan_state": "pending_review",
                "plan_summary": "freeze protocol names",
                "claimed_at": "2026-03-16T01:00:00Z",
            },
            {
                "id": "A2-001",
                "claimed_by": "A2",
                "status": "review",
                "review_note": "ready for acceptance",
                "review_requested_at": "2026-03-16T01:05:00Z",
            },
        ]
        merge_queue = [
            {
                "agent": "A3",
                "status": "stale",
                "attention_summary": "worker exited with 7",
                "blockers": ["provider auth missing"],
                "requested_unlocks": [],
                "resume_instruction": "fix auth then relaunch",
                "next_checkin": "manual",
            },
            {
                "agent": "A4",
                "status": "waiting",
                "attention_summary": "needs lock release",
                "blockers": ["waiting for config"],
                "requested_unlocks": ["config.yaml"],
                "resume_instruction": "apply config and continue",
                "next_checkin": "soon",
            },
        ]
        mailbox_messages = [
            {"id": "m1", "to": "A0", "scope": "direct", "ack_state": "pending", "body": "need decision"},
            {"id": "m2", "to": "A1", "scope": "direct", "ack_state": "pending", "body": "not for manager"},
            {"id": "m3", "to": "all", "scope": "broadcast", "ack_state": "resolved", "body": "already done"},
        ]
        request_state = {
            slugify("A2-001_task_review"): {
                "response_state": "resume",
                "response_note": "recheck naming",
                "created_at": "2026-03-16T01:06:00Z",
            },
            slugify("A3_intervention_stale_worker exited with 7"): {
                "response_state": "pending",
                "created_at": "2026-03-16T01:07:00Z",
            },
            slugify("A4_unlock_waiting_config.yaml"): {
                "response_state": "acknowledged",
                "created_at": "2026-03-16T01:08:00Z",
            },
        }
        messages = [{"id": "old", "body": "kept"}]

        mailbox_catalog = build_team_mailbox_catalog(mailbox_messages)
        catalog = build_a0_request_catalog(backlog_items, merge_queue, mailbox_catalog, request_state, messages)

        self.assertEqual(catalog["pending_count"], 3)
        self.assertEqual([item["agent"] for item in catalog["requests"]], ["A1", "A3", "A2", "A4"])
        by_agent = {item["agent"]: item for item in catalog["requests"]}
        self.assertEqual(by_agent["A1"]["request_type"], "plan_review")
        self.assertEqual(by_agent["A2"]["request_type"], "task_review")
        self.assertEqual(by_agent["A2"]["response_state"], "resume")
        self.assertEqual(by_agent["A3"]["request_type"], "worker_intervention")
        self.assertEqual(by_agent["A3"]["title"], "A3 needs intervention")
        self.assertIn("provider auth missing", by_agent["A3"]["body"])
        self.assertEqual(by_agent["A4"]["request_type"], "unlock")
        self.assertEqual(by_agent["A4"]["title"], "A4 requests unlock")
        self.assertIn("needs lock release", by_agent["A4"]["body"])
        self.assertEqual([item["id"] for item in catalog["inbox"]], ["m1"])
        self.assertEqual(catalog["messages"], messages)


if __name__ == "__main__":
    unittest.main()
