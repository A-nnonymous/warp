from __future__ import annotations

import unittest

from runtime.cp.services import task_action_notification, workflow_patch_notifications


class BacklogNotificationServiceTest(unittest.TestCase):
    def test_task_action_notification_routes_manager_and_direct_messages(self) -> None:
        plan_request = task_action_notification(
            task_id="A1-001",
            action="submit_plan",
            actor="A1",
            note="freeze the public protocol before coding",
            updated={"id": "A1-001", "claimed_by": "A1", "owner": "A1"},
        )
        self.assertEqual(plan_request, {
            "sender": "A1",
            "recipient": "A0",
            "topic": "review_request",
            "body": "freeze the public protocol before coding",
            "related_task_ids": ["A1-001"],
            "scope": "manager",
        })

        approval = task_action_notification(
            task_id="A1-001",
            action="approve_plan",
            actor="A0",
            note="approved; continue with the narrowest contract",
            updated={"id": "A1-001", "claimed_by": "A2", "owner": "A1"},
        )
        self.assertEqual(approval, {
            "sender": "A0",
            "recipient": "A2",
            "topic": "status_note",
            "body": "approved; continue with the narrowest contract",
            "related_task_ids": ["A1-001"],
            "scope": "direct",
        })

    def test_task_action_notification_skips_unknown_actions_and_blank_notes(self) -> None:
        self.assertIsNone(task_action_notification(task_id="A1-001", action="claim", actor="A1", note="claimed", updated={"id": "A1-001"}))
        self.assertIsNone(task_action_notification(task_id="A1-001", action="submit_plan", actor="A1", note="", updated={"id": "A1-001"}))

    def test_workflow_patch_notifications_fan_out_to_single_recipient_or_broadcast(self) -> None:
        direct = workflow_patch_notifications(
            task_id="A1-001",
            before={"owner": "A1", "claimed_by": "A1"},
            updated={"owner": "A2", "claimed_by": "A2", "plan_state": "pending_review"},
            summary="owner: A1 -> A2",
            note="",
        )
        self.assertEqual(direct, [{
            "sender": "A0",
            "recipient": "all",
            "topic": "status_note",
            "body": "A0 updated A1-001: owner: A1 -> A2",
            "related_task_ids": ["A1-001"],
            "scope": "broadcast",
        }])

        rejected = workflow_patch_notifications(
            task_id="A1-002",
            before={"owner": "A0", "claimed_by": ""},
            updated={"owner": "A2", "claimed_by": "A2", "plan_state": "rejected"},
            summary="plan state: pending_review -> rejected",
            note="needs a revised plan",
        )
        self.assertEqual(rejected, [{
            "sender": "A0",
            "recipient": "A2",
            "topic": "design_question",
            "body": "needs a revised plan",
            "related_task_ids": ["A1-002"],
            "scope": "direct",
        }])


if __name__ == "__main__":
    unittest.main()
