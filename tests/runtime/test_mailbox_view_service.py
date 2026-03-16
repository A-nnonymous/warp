from __future__ import annotations

import unittest

from runtime.cp.services import build_team_mailbox_catalog


class MailboxViewServiceTest(unittest.TestCase):
    def test_build_team_mailbox_catalog_tracks_pending_and_a0_inbox(self) -> None:
        catalog = build_team_mailbox_catalog(
            [
                {"id": "m0", "to": "A1", "scope": "direct", "ack_state": "pending", "body": "worker note"},
                {"id": "m1", "to": "A0", "scope": "direct", "ack_state": "pending", "body": "need decision"},
                {"id": "m2", "to": "all", "scope": "broadcast", "ack_state": "seen", "body": "heads up"},
                {"id": "m3", "to": "A2", "scope": "manager", "ack_state": "resolved", "body": "already handled"},
                "bad",
            ]
        )

        self.assertEqual(catalog["pending_count"], 3)
        self.assertEqual(catalog["a0_pending_count"], 2)
        self.assertEqual([item["id"] for item in catalog["a0_inbox"]], ["m1", "m2"])
        self.assertEqual([item["id"] for item in catalog["messages"]], ["m0", "m1", "m2", "m3"])


if __name__ == "__main__":
    unittest.main()
