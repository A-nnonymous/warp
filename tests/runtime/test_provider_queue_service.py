from __future__ import annotations

import unittest

from runtime.cp.services.provider_queue import provider_connection_quality, provider_failure_detail, provider_queue_item
from runtime.cp.services.telemetry_views import running_agent_telemetry, summarize_pool_usage


class ProviderQueueServiceTest(unittest.TestCase):
    def test_provider_connection_quality_tracks_launch_readiness_and_latency(self) -> None:
        self.assertEqual(provider_connection_quality(False, 5.0), 0.0)
        self.assertEqual(provider_connection_quality(True, 10.0), 1.0)
        self.assertEqual(provider_connection_quality(True, 50.0), 0.9)
        self.assertEqual(provider_connection_quality(True, 150.0), 0.8)

    def test_provider_failure_detail_prefers_binary_and_auth_failures(self) -> None:
        self.assertIn(
            "provider binary missing",
            provider_failure_detail(
                pool_name="ducc_pool",
                binary="ducc",
                binary_found=False,
                auth_ready=False,
                auth_detail="ignored",
                last_failure="old failure",
            ),
        )
        self.assertEqual(
            provider_failure_detail(
                pool_name="ducc_pool",
                binary="ducc",
                binary_found=True,
                auth_ready=False,
                auth_detail="ducc session unavailable",
                last_failure="old failure",
            ),
            "ducc session unavailable",
        )
        self.assertEqual(
            provider_failure_detail(
                pool_name="ducc_pool",
                binary="ducc",
                binary_found=True,
                auth_ready=True,
                auth_detail="",
                last_failure="worker exited with 1",
            ),
            "worker exited with 1",
        )

    def test_provider_queue_item_shapes_provider_queue_view(self) -> None:
        running_agent = running_agent_telemetry(
            "A1",
            {"phase": "boot", "progress_pct": 27, "usage": {"input_tokens": 300, "output_tokens": 120, "total_tokens": 420}},
        )
        pool_usage = summarize_pool_usage([running_agent], last_activity_at="2026-03-16T09:40:00")
        item = provider_queue_item(
            pool_name="ducc_pool",
            provider_name="ducc",
            model="ducc-sonnet-it",
            priority=50,
            binary="ducc",
            binary_found=True,
            recursion_guard="env+exec-wrapper",
            launch_wrapper="/tmp/ducc_single_layer.sh",
            auth_mode="session",
            auth_ready=True,
            auth_detail="session ready",
            api_key_present=False,
            latency_ms=20.0,
            work_quality=0.75,
            pool_usage=pool_usage,
            last_failure="",
        )
        self.assertTrue(item["launch_ready"])
        self.assertEqual(item["connection_quality"], 1.0)
        self.assertEqual(item["active_workers"], 1)
        self.assertEqual(item["usage"]["total_tokens"], 420)
        self.assertEqual(item["progress_pct"], 27)
        self.assertEqual(item["last_activity_at"], "2026-03-16T09:40:00")
        self.assertEqual(item["score"], 5082.5)


if __name__ == "__main__":
    unittest.main()
