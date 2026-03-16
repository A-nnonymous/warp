from __future__ import annotations

import unittest

from runtime.cp.services import (
    build_task_profile,
    initial_provider_name,
    provider_preference_default,
    select_task_record_for_worker,
    suggested_branch_name,
    suggested_task_id,
    task_policy_config,
    task_policy_defaults,
    task_policy_rule_matches,
    task_policy_rules,
    task_policy_types,
)


class TaskRoutingServiceTest(unittest.TestCase):
    def test_provider_preference_default_uses_pool_priority_then_fallback(self) -> None:
        config = {
            "providers": {"openai": {}, "ducc": {}, "claude": {}},
            "resource_pools": {
                "pool_b": {"provider": "claude", "priority": 20},
                "pool_a": {"provider": "openai", "priority": 50},
                "pool_c": {"provider": "openai", "priority": 10},
            },
        }
        self.assertEqual(provider_preference_default(config), ["openai", "claude", "ducc"])

    def test_initial_provider_name_prefers_configured_valid_provider(self) -> None:
        config = {
            "project": {"initial_provider": "claude"},
            "providers": {"claude": {}, "ducc": {}},
            "resource_pools": {"pool_a": {"provider": "ducc", "priority": 100}},
        }
        self.assertEqual(initial_provider_name(config), "claude")

    def test_initial_provider_name_falls_back_to_default_or_configured_name(self) -> None:
        self.assertEqual(
            initial_provider_name({"providers": {"ducc": {}, "openai": {}}, "project": {"initial_provider": "missing"}}),
            "ducc",
        )
        self.assertEqual(initial_provider_name({"providers": {"anthropic": {}}, "project": {"initial_provider": "custom"}}), "anthropic")

    def test_policy_normalizers_handle_invalid_shapes(self) -> None:
        self.assertEqual(task_policy_config(None), {})
        self.assertEqual(task_policy_defaults({"task_policies": {"defaults": []}}), {
            "task_type": "default",
            "preferred_providers": ["ducc"],
            "suggested_test_command": "",
            "prompt_context_files": [],
        })
        self.assertEqual(
            task_policy_types({"task_policies": {"types": {"good": {"preferred_providers": ["ducc"]}, "bad": "skip"}}}),
            {"good": {"preferred_providers": ["ducc"], "suggested_test_command": "", "prompt_context_files": []}},
        )
        self.assertEqual(task_policy_rules({"task_policies": {"rules": "not-a-list"}}), [])

    def test_task_policy_rule_matches_agent_task_id_and_title_filters(self) -> None:
        worker = {"agent": "A2", "task_id": "A2-001"}
        task = {"id": "A2-001", "title": "Fix dashboard queue"}
        self.assertTrue(
            task_policy_rule_matches(
                {"agents": ["A2"], "task_ids": ["A2-001"], "title_contains": ["dashboard"]},
                worker,
                task,
            )
        )
        self.assertFalse(task_policy_rule_matches({"agents": []}, worker, task))
        self.assertFalse(task_policy_rule_matches({"task_ids": []}, worker, task))
        self.assertFalse(task_policy_rule_matches({"title_contains": "dashboard"}, worker, task))

    def test_select_task_record_for_worker_prefers_owned_runnable_task(self) -> None:
        backlog_items = [
            {"id": "A2-100", "owner": "A2", "status": "completed", "title": "Done"},
            {"id": "A2-101", "owner": "A2", "status": "blocked", "title": "Blocked next"},
            {"id": "A3-001", "owner": "A3", "status": "active", "title": "Other"},
        ]
        worker = {"agent": "A2"}
        self.assertEqual(select_task_record_for_worker(backlog_items, worker)["id"], "A2-101")
        self.assertEqual(suggested_task_id(worker, backlog_items), "A2-101")

    def test_select_task_record_for_worker_handles_explicit_and_fallback_ids(self) -> None:
        backlog_items = [
            {"id": "A1-002", "owner": "A1", "status": "completed", "title": "Done"},
            {"id": "A1-003", "owner": "A1", "status": "completed", "title": "Done too"},
        ]
        self.assertEqual(select_task_record_for_worker(backlog_items, {"task_id": "A1-003"})["id"], "A1-003")
        self.assertEqual(suggested_task_id({"agent": "A9"}, []), "A9-001")
        self.assertEqual(suggested_task_id({}, []), "")

    def test_build_task_profile_matches_rule_and_shapes_branch_name(self) -> None:
        config = {
            "providers": {"ducc": {}, "openai": {}},
            "resource_pools": {
                "fast": {"provider": "openai", "priority": 80},
                "steady": {"provider": "ducc", "priority": 20},
            },
            "task_policies": {
                "defaults": {
                    "task_type": "default",
                    "preferred_providers": ["ducc"],
                    "suggested_test_command": "pytest -q",
                },
                "types": {
                    "dashboard": {
                        "preferred_providers": ["openai", "ducc"],
                        "suggested_test_command": "pytest runtime/test_task_routing_service.py -q",
                    }
                },
                "rules": [
                    {
                        "name": "dashboard keyword",
                        "task_type": "dashboard",
                        "title_contains": ["dashboard"],
                    }
                ],
            },
        }
        backlog_items = [
            {
                "id": "A1-201",
                "owner": "A1",
                "status": "pending",
                "title": "Dashboard service extraction",
            }
        ]
        worker = {"agent": "A1"}
        profile = build_task_profile(worker, backlog_items, config)
        self.assertEqual(profile["task_id"], "A1-201")
        self.assertEqual(profile["task_type"], "dashboard")
        self.assertEqual(profile["matched_rule_name"], "dashboard keyword")
        self.assertEqual(profile["preferred_providers"], ["openai", "ducc"])
        self.assertEqual(
            profile["suggested_test_command"],
            "pytest runtime/test_task_routing_service.py -q",
        )
        self.assertEqual(suggested_branch_name(worker, profile), "a1_dashboard_service_extraction")

    def test_build_task_profile_respects_explicit_task_type_and_branch_override(self) -> None:
        profile = build_task_profile(
            {"agent": "A4", "task_type": "ops", "branch": "keep/me"},
            [],
            {
                "providers": {"ducc": {}},
                "task_policies": {
                    "types": {
                        "ops": {
                            "preferred_providers": ["ducc"],
                            "prompt_context_files": ["STATUS.md", "STATUS.md"],
                        }
                    }
                },
            },
        )
        self.assertEqual(profile["title"], "A4")
        self.assertEqual(profile["task_type"], "ops")
        self.assertEqual(profile["matched_rule_name"], "")
        self.assertEqual(profile["prompt_context_files"], ["STATUS.md"])
        self.assertEqual(suggested_branch_name({"agent": "A4", "branch": "keep/me"}, profile), "keep/me")


if __name__ == "__main__":
    unittest.main()
