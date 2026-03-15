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

    def test_validate_workflow_updates_rejects_unknown_fields(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
