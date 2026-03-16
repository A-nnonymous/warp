from __future__ import annotations

import os
import subprocess
from typing import Any, Callable


AuthStatusResult = tuple[str, bool, str, bool]


def configured_api_key(provider: dict[str, Any], pool: dict[str, Any], env: dict[str, str] | None = None) -> str:
    api_env_name = provider.get("api_key_env_name")
    configured_value = str(pool.get("api_key", ""))
    if configured_value and configured_value != "replace_me_or_use_api_key_env":
        return configured_value
    if api_env_name:
        source_env = os.environ if env is None else env
        return str(source_env.get(str(api_env_name), ""))
    return ""


def provider_auth_mode(provider: dict[str, Any]) -> str:
    raw_mode = str(provider.get("auth_mode") or "").strip().lower()
    if raw_mode:
        return raw_mode
    if bool(provider.get("session_auth")):
        return "session"
    return "api_key"


def provider_probe_timeout(provider: dict[str, Any], pool: dict[str, Any]) -> float:
    raw_timeout = pool.get("session_probe_timeout_sec", provider.get("session_probe_timeout_sec", 3.0))
    try:
        timeout = float(raw_timeout)
    except (TypeError, ValueError):
        return 3.0
    return min(max(timeout, 0.2), 30.0)


def provider_probe_values(
    pool_name: str,
    provider_name: str,
    pool: dict[str, Any],
    binary: str,
    binary_path: str,
) -> dict[str, str]:
    return {
        "binary": binary,
        "binary_path": binary_path,
        "model": str(pool.get("model", "")),
        "provider": provider_name,
        "resource_pool": pool_name,
    }


def provider_auth_status(
    *,
    pool_name: str,
    provider_name: str,
    provider: dict[str, Any],
    pool: dict[str, Any],
    binary: str,
    binary_path: str,
    format_command_fn: Callable[[Any, dict[str, str]], list[str]],
    run_command_fn: Callable[..., Any],
    env: dict[str, str] | None = None,
) -> AuthStatusResult:
    auth_mode = provider_auth_mode(provider)
    if auth_mode == "session":
        session_probe = pool.get("session_probe_command") or provider.get("session_probe_command")
        if session_probe:
            try:
                probe_command = format_command_fn(
                    session_probe,
                    provider_probe_values(pool_name, provider_name, pool, binary, binary_path),
                )
            except Exception as exc:
                return auth_mode, False, f"session probe formatting failed for pool {pool_name}: {exc}", False
            try:
                result = run_command_fn(probe_command, timeout=provider_probe_timeout(provider, pool))
            except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
                return auth_mode, False, f"session probe failed for pool {pool_name}: {exc}", False
            output = result.stdout.strip() or result.stderr.strip()
            if result.returncode == 0:
                detail = output or f"session ready for pool {pool_name}"
                return auth_mode, True, detail, False
            detail = output or f"session auth unavailable for pool {pool_name}"
            return auth_mode, False, detail, False
        return auth_mode, True, f"session auth enabled for pool {pool_name}", False

    api_env_name = str(provider.get("api_key_env_name") or "").strip()
    api_key = configured_api_key(provider, pool, env=env)
    if api_key:
        return (
            auth_mode,
            True,
            (f"api key available via {api_env_name}" if api_env_name else "api key configured"),
            True,
        )
    if api_env_name:
        return auth_mode, False, f"api key missing for pool {pool_name}; expected env {api_env_name}", False
    return auth_mode, False, f"api key missing for pool {pool_name}", False
