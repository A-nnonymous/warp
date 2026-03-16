from __future__ import annotations

import unittest

from runtime.cp.services.telemetry_views import (
    command_contract,
    normalize_usage,
    process_snapshot_entry,
    running_agent_telemetry,
    summarize_pool_usage,
)


class TelemetryViewServiceTest(unittest.TestCase):
    def test_normalize_usage_defaults_missing_payload(self) -> None:
        self.assertEqual(normalize_usage(None), {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})

    def test_command_contract_marks_wrapper_usage(self) -> None:
        command = command_contract(["/tmp/ducc_wrapper.sh", "ducc", "--model", "x"], "/tmp/ducc_wrapper.sh")
        self.assertEqual(command["binary"], "/tmp/ducc_wrapper.sh")
        self.assertTrue(command["uses_wrapper"])
        self.assertIn("ducc --model x", command["display"])

    def test_running_agent_and_pool_summary_shape_usage(self) -> None:
        a1 = running_agent_telemetry(
            "A1",
            {"phase": "boot", "progress_pct": 27, "usage": {"input_tokens": 300, "output_tokens": 120, "total_tokens": 420}},
        )
        a2 = running_agent_telemetry(
            "A2",
            {"phase": "boot", "progress_pct": 12, "usage": {"input_tokens": 120, "output_tokens": 35, "total_tokens": 155}},
        )
        summary = summarize_pool_usage([a1, a2], last_activity_at="2026-03-16T09:40:00")
        self.assertEqual(summary["usage"]["total_tokens"], 575)
        self.assertEqual(summary["progress_pct"], 20)
        self.assertEqual(summary["running_agents"][0]["usage"]["total_tokens"], 420)
        self.assertEqual(summary["last_activity_at"], "2026-03-16T09:40:00")

    def test_process_snapshot_entry_shapes_command_and_usage(self) -> None:
        snapshot = process_snapshot_entry(
            resource_pool="ducc_pool",
            provider="ducc",
            model="ducc-sonnet-it",
            pid=123,
            alive=True,
            returncode=None,
            wrapper_path="/tmp/ducc_wrapper.sh",
            recursion_guard="env+exec-wrapper",
            worktree_path="/tmp/worktree",
            log_path="/tmp/worker.log",
            command=["/tmp/ducc_wrapper.sh", "ducc", "--model", "ducc-sonnet-it"],
            telemetry={
                "phase": "ducc boot",
                "progress_pct": 27,
                "last_activity_at": "2026-03-16T09:40:00",
                "last_line": "worker starting",
                "usage": {"input_tokens": 300, "output_tokens": 120, "total_tokens": 420},
            },
        )
        self.assertEqual(snapshot["command"]["binary"], "/tmp/ducc_wrapper.sh")
        self.assertTrue(snapshot["command"]["uses_wrapper"])
        self.assertEqual(snapshot["usage"]["total_tokens"], 420)
        self.assertEqual(snapshot["phase"], "ducc boot")


if __name__ == "__main__":
    unittest.main()
