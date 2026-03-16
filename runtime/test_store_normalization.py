from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.cp.stores import BacklogStore, MailboxStore, RuntimeStore


class StoreNormalizationTest(unittest.TestCase):
    def test_backlog_store_normalizes_claim_and_plan_state(self) -> None:
        normalized = BacklogStore.normalize_item(
            {
                "id": " A1-001 ",
                "status": "pending",
                "claim_state": "invalid",
                "claimed_by": "A1",
                "dependencies": ["A0-001", "A0-001", ""],
                "outputs": [" report.md ", ""],
                "done_when": [" green ", ""],
                "plan_state": "bogus",
            }
        )
        self.assertEqual(normalized["id"], "A1-001")
        self.assertEqual(normalized["claim_state"], "claimed")
        self.assertEqual(normalized["status"], "pending")
        self.assertEqual(normalized["dependencies"], ["A0-001"])
        self.assertEqual(normalized["outputs"], ["report.md"])
        self.assertEqual(normalized["done_when"], ["green"])
        self.assertEqual(normalized["plan_state"], "none")

        completed = BacklogStore.normalize_item({"id": "A1-002", "status": "active", "claim_state": "completed"})
        self.assertEqual(completed["status"], "completed")
        review = BacklogStore.normalize_item({"id": "A1-003", "status": "pending", "claim_state": "review"})
        self.assertEqual(review["status"], "review")
        active = BacklogStore.normalize_item({"id": "A1-004", "status": "pending", "claim_state": "in_progress"})
        self.assertEqual(active["status"], "active")

    def test_backlog_store_load_and_persist_handle_invalid_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "backlog.yaml"
            store = BacklogStore(path)
            self.assertEqual(store.load(), store.default_state())

            path.write_text("- not-a-dict\n", encoding="utf-8")
            self.assertEqual(store.load(), store.default_state())

            persisted = store.persist(
                {
                    "project": "warp",
                    "phase": "coverage",
                    "items": [{"id": "A1-001", "claimed_by": "A1"}, "skip"],
                }
            )
            self.assertEqual(persisted["project"], "warp")
            self.assertEqual(len(persisted["items"]), 1)
            self.assertTrue(persisted["last_updated"])

            reloaded = store.load()
            self.assertEqual(reloaded["project"], "warp")
            self.assertEqual(reloaded["items"][0]["claim_state"], "claimed")

    def test_mailbox_store_normalizes_manager_scope_and_load_persist(self) -> None:
        normalized = MailboxStore.normalize_message(
            {
                "from": "A1",
                "scope": "manager",
                "topic": "review_request",
                "related_task_ids": ["A1-001", "A1-001", ""],
                "ack_state": "bogus",
            }
        )
        self.assertEqual(normalized["to"], "A0")
        self.assertEqual(normalized["ack_state"], "pending")
        self.assertEqual(normalized["related_task_ids"], ["A1-001"])
        self.assertTrue(normalized["id"])
        self.assertTrue(normalized["created_at"])

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mailbox.yaml"
            store = MailboxStore(path)
            self.assertEqual(store.load(), {"messages": []})

            path.write_text("[]\n", encoding="utf-8")
            self.assertEqual(store.load(), {"messages": []})

            persisted = store.persist({"messages": [normalized, "skip"]})
            self.assertEqual(len(persisted["messages"]), 1)
            self.assertEqual(store.load()["messages"][0]["scope"], "manager")

    def test_runtime_store_normalizes_workers_and_handles_invalid_state(self) -> None:
        normalized = RuntimeStore.normalize_worker({"agent": " A1 ", "resource_pool": "", "provider": "", "model": "", "status": " active "})
        self.assertEqual(normalized["agent"], "A1")
        self.assertEqual(normalized["resource_pool"], "unassigned")
        self.assertEqual(normalized["provider"], "unassigned")
        self.assertEqual(normalized["model"], "unassigned")
        self.assertEqual(normalized["status"], "active")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime.yaml"
            store = RuntimeStore(path)
            self.assertEqual(store.load(), {"workers": [], "last_updated": ""})

            path.write_text("[]\n", encoding="utf-8")
            self.assertEqual(store.load(), {"project": "", "last_updated": "", "schema": {}, "workers": []})

            persisted = store.persist(
                {
                    "project": " warp ",
                    "schema": {"version": 1},
                    "workers": [normalized, "skip"],
                }
            )
            self.assertEqual(persisted["project"], "warp")
            self.assertEqual(persisted["schema"], {"version": 1})
            self.assertEqual(len(persisted["workers"]), 1)
            self.assertTrue(persisted["last_updated"])

            reloaded = store.load()
            self.assertEqual(reloaded["workers"][0]["resource_pool"], "unassigned")
            self.assertEqual(reloaded["schema"], {"version": 1})


if __name__ == "__main__":
    unittest.main()
