from __future__ import annotations

import subprocess
import unittest
from types import SimpleNamespace

from runtime.cp.services.provider_auth import (
    configured_api_key,
    provider_auth_mode,
    provider_auth_status,
    provider_probe_timeout,
    provider_probe_values,
)


class ProviderAuthServiceTest(unittest.TestCase):
    def test_configured_api_key_prefers_pool_then_env(self) -> None:
        provider = {"api_key_env_name": "OPENAI_API_KEY"}
        self.assertEqual(configured_api_key(provider, {"api_key": "pool-secret"}, env={"OPENAI_API_KEY": "env-secret"}), "pool-secret")
        self.assertEqual(
            configured_api_key(provider, {"api_key": "replace_me_or_use_api_key_env"}, env={"OPENAI_API_KEY": "env-secret"}),
            "env-secret",
        )

    def test_provider_auth_mode_timeout_and_probe_values_normalize_inputs(self) -> None:
        self.assertEqual(provider_auth_mode({"session_auth": True}), "session")
        self.assertEqual(provider_auth_mode({"auth_mode": " API_KEY "}), "api_key")
        self.assertEqual(provider_probe_timeout({}, {}), 3.0)
        self.assertEqual(provider_probe_timeout({"session_probe_timeout_sec": "0.01"}, {}), 0.2)
        self.assertEqual(provider_probe_timeout({}, {"session_probe_timeout_sec": 90}), 30.0)
        self.assertEqual(
            provider_probe_values("ducc_pool", "ducc", {"model": "sonnet"}, "ducc", "/usr/bin/ducc"),
            {
                "binary": "ducc",
                "binary_path": "/usr/bin/ducc",
                "model": "sonnet",
                "provider": "ducc",
                "resource_pool": "ducc_pool",
            },
        )

    def test_provider_auth_status_handles_session_probe_success_and_failure(self) -> None:
        provider = {"auth_mode": "session", "session_probe_command": ["ducc", "status", "{resource_pool}"]}
        format_calls: list[tuple[object, dict[str, str]]] = []
        run_calls: list[tuple[list[str], float]] = []

        def fake_format(command: object, values: dict[str, str]) -> list[str]:
            format_calls.append((command, values))
            return ["ducc", "status", values["resource_pool"]]

        def fake_run(command: list[str], timeout: float) -> SimpleNamespace:
            run_calls.append((command, timeout))
            return SimpleNamespace(returncode=0, stdout="ready", stderr="")

        status = provider_auth_status(
            pool_name="ducc_pool",
            provider_name="ducc",
            provider=provider,
            pool={"model": "sonnet"},
            binary="ducc",
            binary_path="/usr/bin/ducc",
            format_command_fn=fake_format,
            run_command_fn=fake_run,
        )
        self.assertEqual(status, ("session", True, "ready", False))
        self.assertEqual(format_calls[0][1]["resource_pool"], "ducc_pool")
        self.assertEqual(run_calls[0], (["ducc", "status", "ducc_pool"], 3.0))

        def failing_run(command: list[str], timeout: float) -> SimpleNamespace:
            return SimpleNamespace(returncode=7, stdout="", stderr="ducc session unavailable")

        failed_status = provider_auth_status(
            pool_name="ducc_pool",
            provider_name="ducc",
            provider=provider,
            pool={"model": "sonnet"},
            binary="ducc",
            binary_path="/usr/bin/ducc",
            format_command_fn=fake_format,
            run_command_fn=failing_run,
        )
        self.assertEqual(failed_status, ("session", False, "ducc session unavailable", False))

    def test_provider_auth_status_handles_probe_errors_and_api_key_paths(self) -> None:
        provider = {"auth_mode": "session", "session_probe_command": ["ducc", "status"]}

        def broken_format(command: object, values: dict[str, str]) -> list[str]:
            raise ValueError("bad template")

        formatting_failed = provider_auth_status(
            pool_name="ducc_pool",
            provider_name="ducc",
            provider=provider,
            pool={},
            binary="ducc",
            binary_path="/usr/bin/ducc",
            format_command_fn=broken_format,
            run_command_fn=lambda *args, **kwargs: None,
        )
        self.assertEqual(formatting_failed, ("session", False, "session probe formatting failed for pool ducc_pool: bad template", False))

        def timeout_run(command: list[str], timeout: float) -> SimpleNamespace:
            raise subprocess.TimeoutExpired(command, timeout)

        timeout_failed = provider_auth_status(
            pool_name="ducc_pool",
            provider_name="ducc",
            provider=provider,
            pool={},
            binary="ducc",
            binary_path="/usr/bin/ducc",
            format_command_fn=lambda command, values: ["ducc", "status"],
            run_command_fn=timeout_run,
        )
        self.assertIn("session probe failed for pool ducc_pool", timeout_failed[2])

        api_status = provider_auth_status(
            pool_name="openai_pool",
            provider_name="openai",
            provider={"api_key_env_name": "OPENAI_API_KEY"},
            pool={},
            binary="openai",
            binary_path="/usr/bin/openai",
            format_command_fn=lambda command, values: [],
            run_command_fn=lambda *args, **kwargs: None,
            env={"OPENAI_API_KEY": "secret"},
        )
        self.assertEqual(api_status, ("api_key", True, "api key available via OPENAI_API_KEY", True))

        missing_api_status = provider_auth_status(
            pool_name="openai_pool",
            provider_name="openai",
            provider={"api_key_env_name": "OPENAI_API_KEY"},
            pool={},
            binary="openai",
            binary_path="/usr/bin/openai",
            format_command_fn=lambda command, values: [],
            run_command_fn=lambda *args, **kwargs: None,
            env={},
        )
        self.assertEqual(missing_api_status, ("api_key", False, "api key missing for pool openai_pool; expected env OPENAI_API_KEY", False))


if __name__ == "__main__":
    unittest.main()
