from __future__ import annotations

import os
import re
import shlex
import signal
import socket
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit("PyYAML is required. Run `uv sync` or install PyYAML>=6.0.2.") from exc


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def dump_yaml(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=False)


def yaml_text(data: Any) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=False)


def run_shell(command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, shell=True, text=True, capture_output=True)


def run_command(args: list[str], timeout: float = 3.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False, timeout=timeout)


def format_command(template: Any, values: dict[str, str]) -> list[str]:
    if isinstance(template, str):
        return shlex.split(template.format(**values))
    return [str(part).format(**values) for part in template]


def slugify(value: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "_" for char in str(value))
    compact = "_".join(part for part in normalized.split("_") if part)
    return compact or "unassigned"


def dedupe_strings(values: list[Any]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def summarize_list(values: list[str], limit: int = 4) -> str:
    items = [str(value).strip() for value in values if str(value or "").strip()]
    if not items:
        return ""
    if len(items) <= limit:
        return "; ".join(items)
    return "; ".join(items[:limit]) + f"; ... (+{len(items) - limit} more)"


def truncate_text(value: str, limit: int = 220) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    text = str(value or "").strip()
    if not text:
        return None
    if re.fullmatch(r"\d+", text):
        return int(text)
    return None


def merge_usage_counts(current: dict[str, int], update: dict[str, int]) -> dict[str, int]:
    merged = dict(current)
    for key, value in update.items():
        merged[key] = max(int(merged.get(key, 0)), int(value))
    total = int(merged.get("total_tokens", 0))
    if total <= 0:
        merged["total_tokens"] = int(merged.get("input_tokens", 0)) + int(merged.get("output_tokens", 0))
    return merged


def is_placeholder_path(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip()
    if not normalized:
        return False
    return normalized.startswith("/absolute/path/") or normalized in {"unassigned", "none"}


def is_local_host(host: str) -> bool:
    return host in {"127.0.0.1", "localhost", "0.0.0.0", "::1", "::"}


def path_exists_via_ls(path_value: str) -> bool:
    try:
        result = run_command(["ls", "-d", path_value])
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return Path(path_value).exists()
    return result.returncode == 0


def host_reachable_via_ping(host: str) -> bool:
    if is_local_host(host):
        return True
    try:
        result = run_command(["ping", "-c", "1", host], timeout=2.5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        try:
            socket.getaddrinfo(host, None)
        except socket.gaierror:
            return False
        return True
    return result.returncode == 0


def terminate_process_tree(pid: int, sig: int = signal.SIGTERM) -> None:
    try:
        process_group = os.getpgid(pid)
    except OSError:
        return
    try:
        os.killpg(process_group, sig)
    except OSError:
        return
