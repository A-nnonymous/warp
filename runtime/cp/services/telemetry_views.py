from __future__ import annotations

from typing import Any

from ..contracts import (
    PoolUsageSummary,
    ProcessCommand,
    ProcessLaunchMetadata,
    ProcessRuntimeMetadata,
    ProcessSnapshot,
    RunningAgentTelemetry,
    TelemetryUsage,
)


def normalize_usage(payload: Any) -> TelemetryUsage:
    usage: TelemetryUsage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    if not isinstance(payload, dict):
        return usage
    for key in usage:
        usage[key] = int(payload.get(key, 0) or 0)
    return usage


def command_contract(command: list[str], wrapper_path: str) -> ProcessCommand:
    argv = [str(part) for part in command]
    return {
        "argv": argv,
        "binary": argv[0] if argv else "",
        "display": " ".join(argv),
        "uses_wrapper": bool(wrapper_path and argv and argv[0] == wrapper_path),
    }


def running_agent_telemetry(agent: str, telemetry: dict[str, Any]) -> RunningAgentTelemetry:
    progress_value = telemetry.get("progress_pct")
    return {
        "agent": agent,
        "progress_pct": progress_value if isinstance(progress_value, int) else None,
        "phase": str(telemetry.get("phase", "")),
        "usage": normalize_usage(telemetry.get("usage")),
    }


def process_launch_metadata(wrapper_path: str, recursion_guard: str, command: list[str]) -> ProcessLaunchMetadata:
    return {
        "wrapper_path": wrapper_path,
        "recursion_guard": recursion_guard,
        "command": command_contract(command, wrapper_path),
    }


def process_runtime_metadata(
    *,
    pid: int,
    alive: bool,
    returncode: int | None,
    worktree_path: str,
    log_path: str,
) -> ProcessRuntimeMetadata:
    return {
        "pid": pid,
        "alive": alive,
        "returncode": returncode,
        "worktree_path": worktree_path,
        "log_path": log_path,
    }


def summarize_pool_usage(entries: list[RunningAgentTelemetry], last_activity_at: str = "") -> PoolUsageSummary:
    usage: TelemetryUsage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    progress_values: list[int] = []
    for entry in entries:
        entry_usage = entry["usage"]
        for key in usage:
            usage[key] += entry_usage[key]
        progress_value = entry.get("progress_pct")
        if isinstance(progress_value, int):
            progress_values.append(progress_value)
    return {
        "running_agents": entries,
        "usage": usage,
        "progress_pct": round(sum(progress_values) / len(progress_values)) if progress_values else None,
        "last_activity_at": last_activity_at,
    }


def process_snapshot_entry(
    *,
    resource_pool: str,
    provider: str,
    model: str,
    pid: int,
    alive: bool,
    returncode: int | None,
    wrapper_path: str,
    recursion_guard: str,
    worktree_path: str,
    log_path: str,
    command: list[str],
    telemetry: dict[str, Any],
) -> ProcessSnapshot:
    progress_value = telemetry.get("progress_pct")
    launch = process_launch_metadata(wrapper_path, recursion_guard, command)
    runtime = process_runtime_metadata(
        pid=pid,
        alive=alive,
        returncode=returncode,
        worktree_path=worktree_path,
        log_path=log_path,
    )
    return {
        "resource_pool": resource_pool,
        "provider": provider,
        "model": model,
        "pid": runtime["pid"],
        "alive": runtime["alive"],
        "returncode": runtime["returncode"],
        "wrapper_path": launch["wrapper_path"],
        "recursion_guard": launch["recursion_guard"],
        "worktree_path": runtime["worktree_path"],
        "log_path": runtime["log_path"],
        "command": launch["command"],
        "launch": launch,
        "runtime": runtime,
        "phase": str(telemetry.get("phase", "")),
        "progress_pct": progress_value if isinstance(progress_value, int) else None,
        "last_activity_at": str(telemetry.get("last_activity_at", "")),
        "last_log_line": str(telemetry.get("last_line", "")),
        "usage": normalize_usage(telemetry.get("usage")),
    }
