from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from runtime.cp.cli import resolve_runtime_config
from runtime.cp.config_mixin import ConfigMixin
from runtime.cp.launch_mixin import LaunchMixin
from runtime.cp.network import safe_relative_web_path, strip_command_args
from runtime.cp.provider_mixin import ProviderMixin
from runtime.cp.routing_mixin import RoutingMixin


class _ConfigHarness(RoutingMixin, ProviderMixin, ConfigMixin):
    def __init__(self, config: dict[str, object]):
        self.config = config
        self.project = config.get("project", {}) if isinstance(config, dict) else {}
        self.providers = config.get("providers", {}) if isinstance(config, dict) else {}
        self.resource_pools = config.get("resource_pools", {}) if isinstance(config, dict) else {}

    def provider_queue(self) -> list[dict[str, object]]:
        return []

    def backlog_items(self) -> list[dict[str, object]]:
        return []


class _LaunchHarness(LaunchMixin):
    def __init__(self, repo_root: Path):
        self._repo_root = repo_root

    def target_repo_root(self) -> Path:
        return self._repo_root

    def branch_exists(self, branch: str) -> bool:
        del branch
        return False


class ControlPlaneRuntimeEdgesTest(unittest.TestCase):
    def test_repair_config_resource_pool_references_clears_stale_entries(self) -> None:
        harness = _ConfigHarness(
            {
                "project": {"initial_provider": "ghost"},
                "providers": {"ducc": {"auth_mode": "session"}},
                "resource_pools": {"ducc_pool": {"provider": "ducc", "model": "claude"}},
                "task_policies": {
                    "defaults": {"preferred_providers": ["ghost", "ducc"]},
                    "types": {"protocol": {"preferred_providers": ["ducc", "ghost"]}},
                },
                "worker_defaults": {"resource_pool": "ghost_pool", "resource_pool_queue": ["ghost_pool", "ducc_pool"]},
                "workers": [
                    {
                        "agent": "A1",
                        "resource_pool": "ghost_pool",
                        "resource_pool_queue": ["ghost_pool", "ducc_pool"],
                    }
                ],
            }
        )

        repaired, repairs = harness.repair_config_resource_pool_references(harness.config)

        self.assertNotIn("initial_provider", repaired["project"])
        self.assertEqual(repaired["task_policies"]["defaults"]["preferred_providers"], ["ducc"])
        self.assertEqual(repaired["task_policies"]["types"]["protocol"]["preferred_providers"], ["ducc"])
        self.assertNotIn("resource_pool", repaired["worker_defaults"])
        self.assertEqual(repaired["worker_defaults"]["resource_pool_queue"], ["ducc_pool"])
        self.assertNotIn("resource_pool", repaired["workers"][0])
        self.assertEqual(repaired["workers"][0]["resource_pool_queue"], ["ducc_pool"])
        self.assertGreaterEqual(len(repairs), 5)

    def test_validate_config_section_filters_to_workers_scope(self) -> None:
        harness = _ConfigHarness(
            {
                "project": {
                    "repository_name": "warp",
                    "local_repo_root": "/missing/project",
                    "reference_workspace_root": "/missing/reference",
                    "dashboard": {"host": "bad-host", "port": 0},
                },
                "providers": {"ducc": {"auth_mode": "session", "command_template": ["ducc"]}},
                "resource_pools": {"ducc_pool": {"provider": "ducc", "model": "claude", "priority": 100}},
                "worker_defaults": {"environment_type": "none"},
                "workers": [],
            }
        )
        broken_workers = [
            {
                "agent": "A1",
                "branch": "shared-branch",
                "worktree_path": "/tmp/a1",
                "resource_pool": "ducc_pool",
                "test_command": "pytest",
                "submit_strategy": "patch_handoff",
            },
            {
                "agent": "A2",
                "branch": "shared-branch",
                "worktree_path": "/tmp/a2",
                "resource_pool": "ducc_pool",
                "submit_strategy": "patch_handoff",
            },
        ]

        with patch("runtime.cp.config_mixin.path_exists_via_ls", return_value=False), patch(
            "runtime.cp.config_mixin.host_reachable_via_ping", return_value=False
        ):
            validation = harness.validate_config_section("workers", broken_workers)

        self.assertFalse(validation["ok"])
        self.assertTrue(validation["validation_issues"])
        self.assertTrue(all(issue["field"].startswith("workers[") for issue in validation["validation_issues"]))
        self.assertTrue(all("worker " in item or "workers[" in item for item in validation["launch_blockers"]))
        self.assertFalse(any(item.startswith("project.") for item in validation["validation_errors"]))

    def test_ensure_worktree_rejects_existing_non_git_directory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="warp-launch-") as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            worktree_path = Path(temp_dir) / "dirty-worktree"
            worktree_path.mkdir()
            (worktree_path / "stray.txt").write_text("not a git worktree\n", encoding="utf-8")
            harness = _LaunchHarness(repo_root)

            with self.assertRaisesRegex(RuntimeError, "not an initialized git worktree"):
                harness.ensure_worktree({"worktree_path": str(worktree_path), "branch": "feature/test"})

    def test_ensure_environment_surfaces_sync_failure_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="warp-env-") as temp_dir:
            harness = _LaunchHarness(Path(temp_dir))
            worker = {"worktree_path": temp_dir, "sync_command": "uv sync"}
            failed = SimpleNamespace(returncode=1, stdout="", stderr="uv lock failed")
            with patch("runtime.cp.launch_mixin.run_shell", return_value=failed):
                with self.assertRaisesRegex(RuntimeError, "uv lock failed"):
                    harness.ensure_environment(worker)

    def test_resolve_runtime_config_uses_template_when_bootstrap_requested(self) -> None:
        with tempfile.TemporaryDirectory(prefix="warp-cli-") as temp_dir:
            temp_root = Path(temp_dir)
            requested_path = temp_root / "missing-local-config.yaml"
            template_path = temp_root / "config_template.yaml"
            template_path.write_text("project: {}\n", encoding="utf-8")
            args = SimpleNamespace(config=requested_path, bootstrap=True)

            with patch("runtime.cp.cli.RUNTIME_DIR", temp_root), patch("runtime.cp.cli.CONFIG_TEMPLATE_PATH", template_path):
                config_path, persist_path, cold_start, reason = resolve_runtime_config(args)

        self.assertEqual(config_path, template_path)
        self.assertEqual(persist_path, requested_path)
        self.assertTrue(cold_start)
        self.assertIn("cold-start bootstrapped from template", reason)

    def test_network_helpers_sanitize_command_and_static_paths(self) -> None:
        command = ["ducc", "--model", "claude", "--prompt-file", "/tmp/prompt.md", "--cwd", "/tmp/worktree"]
        cleaned = strip_command_args(command, {"--prompt-file", "--cwd"})

        self.assertEqual(cleaned, ["ducc", "--model", "claude"])
        self.assertEqual(safe_relative_web_path("/"), Path("index.html"))
        self.assertEqual(safe_relative_web_path("/assets/app.js"), Path("assets/app.js"))
        self.assertIsNone(safe_relative_web_path("/../../etc/passwd"))


if __name__ == "__main__":
    unittest.main()
