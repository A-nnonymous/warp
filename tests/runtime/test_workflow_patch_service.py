from __future__ import annotations

import unittest

from runtime.cp.services import apply_task_action, apply_workflow_patch, summarize_workflow_patch, validate_workflow_updates


class WorkflowPatchServiceTest(unittest.TestCase):
    def test_apply_task_action_advances_plan_and_review_states(self) -> None:
        item = {"id": "A1-001", "status": "pending", "claim_state": "unclaimed", "claimed_by": ""}
        claimed = apply_task_action(item, task_id="A1-001", action="claim", actor="A1", note="own it", current_time="2026-03-16T02:00:00Z")
        self.assertEqual(claimed["claimed_by"], "A1")
        self.assertEqual(claimed["claim_state"], "claimed")

        plan = apply_task_action(
            claimed,
            task_id="A1-001",
            action="submit_plan",
            actor="A1",
            note="freeze public payload contract",
            current_time="2026-03-16T02:01:00Z",
        )
        self.assertTrue(plan["plan_required"])
        self.assertEqual(plan["plan_state"], "pending_review")

        review = apply_task_action(
            {**plan, "plan_state": "approved"},
            task_id="A1-001",
            action="request_review",
            actor="A1",
            note="ready for acceptance",
            current_time="2026-03-16T02:02:00Z",
        )
        self.assertEqual(review["status"], "review")
        self.assertEqual(review["claim_state"], "review")
        self.assertEqual(review["review_requested_at"], "2026-03-16T02:02:00Z")

    def test_complete_requires_plan_approval(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires plan approval"):
            apply_task_action(
                {"id": "A1-001", "plan_required": True, "plan_state": "pending_review"},
                task_id="A1-001",
                action="complete",
                actor="A0",
                note="ship it",
                current_time="2026-03-16T02:03:00Z",
            )

    def test_apply_task_action_release_reject_complete_and_reopen_paths(self) -> None:
        with self.assertRaisesRegex(ValueError, "already claimed by A2"):
            apply_task_action(
                {"id": "A1-001", "claimed_by": "A2", "claim_state": "review"},
                task_id="A1-001",
                action="claim",
                actor="A1",
                note="take over",
                current_time="2026-03-16T02:03:00Z",
            )

        with self.assertRaisesRegex(ValueError, "is claimed by A2"):
            apply_task_action(
                {"id": "A1-001", "claimed_by": "A2", "status": "active"},
                task_id="A1-001",
                action="release",
                actor="A3",
                note="not mine",
                current_time="2026-03-16T02:03:30Z",
            )

        released = apply_task_action(
            {"id": "A1-001", "claimed_by": "A2", "status": "review", "claim_state": "review"},
            task_id="A1-001",
            action="release",
            actor="A0",
            note="manager reset",
            current_time="2026-03-16T02:04:00Z",
        )
        self.assertEqual(released["claimed_by"], "")
        self.assertEqual(released["status"], "pending")
        self.assertEqual(released["claim_state"], "unclaimed")

        started = apply_task_action(
            {"id": "A1-001", "status": "blocked", "claim_note": "keep note"},
            task_id="A1-001",
            action="start",
            actor="A1",
            note="",
            current_time="2026-03-16T02:05:00Z",
        )
        self.assertEqual(started["status"], "active")
        self.assertEqual(started["claim_state"], "in_progress")
        self.assertEqual(started["claim_note"], "keep note")

        approved = apply_task_action(
            {"id": "A1-001", "plan_state": "pending_review"},
            task_id="A1-001",
            action="approve_plan",
            actor="A0",
            note="looks good",
            current_time="2026-03-16T02:06:00Z",
        )
        self.assertEqual(approved["plan_state"], "approved")
        self.assertEqual(approved["plan_reviewed_at"], "2026-03-16T02:06:00Z")

        rejected = apply_task_action(
            {"id": "A1-001", "plan_state": "pending_review", "claimed_by": ""},
            task_id="A1-001",
            action="reject_plan",
            actor="A0",
            note="needs rewrite",
            current_time="2026-03-16T02:07:00Z",
        )
        self.assertEqual(rejected["plan_state"], "rejected")
        self.assertEqual(rejected["claimed_by"], "A0")

        completed = apply_task_action(
            {"id": "A1-001", "plan_required": True, "plan_state": "approved", "review_note": ""},
            task_id="A1-001",
            action="complete",
            actor="A0",
            note="",
            current_time="2026-03-16T02:08:00Z",
        )
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["review_note"], "manager accepted task")

        reopened = apply_task_action(
            {"id": "A1-001", "status": "completed", "claimed_by": "A1", "completed_at": "done", "completed_by": "A0"},
            task_id="A1-001",
            action="reopen",
            actor="A0",
            note="follow-up required",
            current_time="2026-03-16T02:09:00Z",
        )
        self.assertEqual(reopened["status"], "pending")
        self.assertEqual(reopened["claim_state"], "claimed")
        self.assertEqual(reopened["completed_at"], "")
        self.assertEqual(reopened["review_note"], "follow-up required")

    def test_apply_workflow_patch_shapes_lists_and_timestamps(self) -> None:
        updated = apply_workflow_patch(
            {
                "id": "A1-001",
                "status": "review",
                "claim_state": "review",
                "owner": "A1",
                "claimed_by": "A1",
                "review_requested_at": "",
                "completed_at": "2026-03-16T01:30:00Z",
                "completed_by": "A0",
                "plan_state": "approved",
                "plan_review_note": "looks good",
            },
            updates={
                "owner": "A2",
                "claimed_by": "A2",
                "status": "pending",
                "claim_state": "claimed",
                "dependencies": "A2-001, A2-001, A2-002",
                "plan_state": "pending_review",
                "plan_summary": "replan around acceptance feedback",
            },
            current_time="2026-03-16T02:04:00Z",
        )
        self.assertEqual(updated["owner"], "A2")
        self.assertEqual(updated["claimed_by"], "A2")
        self.assertEqual(updated["claimed_at"], "2026-03-16T02:04:00Z")
        self.assertEqual(updated["dependencies"], ["A2-001", "A2-002"])
        self.assertEqual(updated["review_requested_at"], "")
        self.assertEqual(updated["completed_at"], "")
        self.assertEqual(updated["completed_by"], "")
        self.assertEqual(updated["plan_reviewed_at"], "")

    def test_apply_workflow_patch_validates_lists_booleans_and_review_timestamps(self) -> None:
        updated = apply_workflow_patch(
            {
                "id": "A1-001",
                "status": "review",
                "claim_state": "review",
                "review_requested_at": "",
                "plan_state": "none",
                "plan_review_note": "stale",
            },
            updates={
                "dependencies": ["A0-001", "A0-001", "A0-002"],
                "outputs": [" report.md ", ""],
                "done_when": [" tests green ", "tests green"],
                "plan_required": True,
                "plan_state": "approved",
            },
            current_time="2026-03-16T02:10:00Z",
        )
        self.assertEqual(updated["dependencies"], ["A0-001", "A0-002"])
        self.assertEqual(updated["outputs"], ["report.md"])
        self.assertEqual(updated["done_when"], ["tests green"])
        self.assertTrue(updated["plan_required"])
        self.assertEqual(updated["review_requested_at"], "2026-03-16T02:10:00Z")
        self.assertEqual(updated["plan_reviewed_at"], "2026-03-16T02:10:00Z")

        reset = apply_workflow_patch(
            {"id": "A1-001", "claimed_by": "", "claimed_at": "old", "plan_state": "approved", "plan_review_note": "ok"},
            updates={"status": "pending", "plan_state": "none"},
            current_time="2026-03-16T02:11:00Z",
        )
        self.assertEqual(reset["claimed_at"], "")
        self.assertEqual(reset["plan_reviewed_at"], "")
        self.assertEqual(reset["plan_review_note"], "")

        with self.assertRaisesRegex(ValueError, "must be a list or comma-separated string"):
            apply_workflow_patch(
                {"id": "A1-001"},
                updates={"dependencies": 123},
                current_time="2026-03-16T02:12:00Z",
            )

    def test_validate_workflow_updates_rejects_unknown_fields_and_missing_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "updates are required"):
            validate_workflow_updates({})
        with self.assertRaisesRegex(ValueError, "updates are required"):
            validate_workflow_updates([])  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "unsupported workflow update fields"):
            validate_workflow_updates({"bogus": True})

    def test_summarize_workflow_patch_mentions_dependency_and_plan_changes(self) -> None:
        summary = summarize_workflow_patch(
            {"owner": "A1", "dependencies": ["A1-000"], "plan_summary": "old"},
            {"owner": "A2", "dependencies": ["A2-000"], "plan_summary": "new"},
        )
        self.assertIn("owner: A1 -> A2", summary)
        self.assertIn("dependencies:", summary)
        self.assertIn("plan summary updated", summary)

    def test_summarize_workflow_patch_returns_default_when_nothing_changed(self) -> None:
        self.assertEqual(summarize_workflow_patch({"owner": "A1"}, {"owner": "A1"}), "workflow updated")


if __name__ == "__main__":
    unittest.main()
