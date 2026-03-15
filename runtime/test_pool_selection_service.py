from __future__ import annotations

import unittest

from runtime.cp.services import (
    best_pool_for_provider,
    best_pool_for_worker,
    configured_pool_candidates,
    queue_pool_candidates,
    rank_pool_candidates,
    recommended_pool_plan,
)


class PoolSelectionServiceTest(unittest.TestCase):
    def test_configured_pool_candidates_honors_worker_then_defaults(self) -> None:
        resource_pools = {"fast": {}, "steady": {}, "fallback": {}}
        defaults = {"resource_pool_queue": ["steady", "fallback"]}
        self.assertEqual(
            configured_pool_candidates({"resource_pool": "fast"}, defaults, resource_pools),
            ["fast"],
        )
        self.assertEqual(
            configured_pool_candidates({}, defaults, resource_pools),
            ["steady", "fallback"],
        )

    def test_rank_pool_candidates_applies_provider_affinity(self) -> None:
        evaluations = {
            "openai_fast": {"provider": "openai", "score": 70},
            "ducc_steady": {"provider": "ducc", "score": 95},
        }
        ordered = rank_pool_candidates(["ducc_steady", "openai_fast"], evaluations, ["openai", "ducc"])
        self.assertEqual(ordered, ["openai_fast", "ducc_steady"])

    def test_recommended_pool_plan_locks_first_launch_ready_preferred_provider(self) -> None:
        worker = {"agent": "A1", "resource_pool_queue": ["openai_fast", "ducc_steady", "openai_backup"]}
        profile = {"task_type": "routing", "preferred_providers": ["openai", "ducc"]}
        provider_queue = [
            {"resource_pool": "openai_fast", "provider": "openai", "score": 70, "launch_ready": False},
            {"resource_pool": "ducc_steady", "provider": "ducc", "score": 99, "launch_ready": True},
            {"resource_pool": "openai_backup", "provider": "openai", "score": 60, "launch_ready": True},
        ]
        plan = recommended_pool_plan(
            worker=worker,
            resource_pools={"openai_fast": {}, "ducc_steady": {}, "openai_backup": {}},
            defaults={},
            provider_queue=provider_queue,
            profile=profile,
        )
        self.assertEqual(plan["recommended_pool"], "openai_backup")
        self.assertEqual(plan["locked_pool"], "openai_backup")
        self.assertEqual(plan["recommended_queue"], ["openai_backup", "openai_fast", "ducc_steady"])
        self.assertIn("task policy plus provider quality", plan["reason"])

    def test_recommended_pool_plan_preserves_explicit_override(self) -> None:
        worker = {"agent": "A1", "resource_pool": "ducc_steady"}
        profile = {"task_type": "routing", "preferred_providers": ["openai", "ducc"]}
        plan = recommended_pool_plan(
            worker=worker,
            resource_pools={"openai_fast": {}, "ducc_steady": {}},
            defaults={},
            provider_queue=[
                {"resource_pool": "openai_fast", "provider": "openai", "score": 99, "launch_ready": True},
                {"resource_pool": "ducc_steady", "provider": "ducc", "score": 40, "launch_ready": True},
            ],
            profile=profile,
        )
        self.assertEqual(plan["recommended_pool"], "ducc_steady")
        self.assertEqual(plan["locked_pool"], "ducc_steady")
        self.assertEqual(plan["reason"], "explicit worker pool override")

    def test_queue_pool_candidates_and_best_pool_helpers_share_provider_queue_logic(self) -> None:
        provider_queue = [
            {"resource_pool": "openai_low", "provider": "openai", "score": 10, "priority": 10, "launch_ready": False},
            {"resource_pool": "openai_high", "provider": "openai", "score": 80, "priority": 50, "launch_ready": True},
            {"resource_pool": "ducc_best", "provider": "ducc", "score": 90, "priority": 40, "launch_ready": True},
        ]
        self.assertEqual(queue_pool_candidates({}, provider_queue), ["openai_low", "openai_high", "ducc_best"])
        self.assertEqual(best_pool_for_provider("openai", provider_queue)[0], "openai_high")
        self.assertEqual(best_pool_for_worker({"agent": "A2"}, provider_queue)[0], "ducc_best")
        self.assertEqual(
            best_pool_for_worker({"agent": "A2", "resource_pool_queue": ["openai_low", "openai_high"]}, provider_queue)[0],
            "openai_high",
        )


if __name__ == "__main__":
    unittest.main()
