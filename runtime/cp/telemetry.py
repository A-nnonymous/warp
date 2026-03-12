from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .utils import safe_int, slugify, truncate_text


def merge_usage_counts(current: dict[str, int], update: dict[str, int]) -> dict[str, int]:
    merged = dict(current)
    for key, value in update.items():
        merged[key] = max(int(merged.get(key, 0)), int(value))
    total = int(merged.get("total_tokens", 0))
    if total <= 0:
        merged["total_tokens"] = int(merged.get("input_tokens", 0)) + int(merged.get("output_tokens", 0))
    return merged


def usage_from_mapping(payload: Any) -> dict[str, int]:
    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    if not isinstance(payload, dict):
        return usage

    alias_map = {
        "input_tokens": "input_tokens",
        "prompt_tokens": "input_tokens",
        "input": "input_tokens",
        "prompt": "input_tokens",
        "output_tokens": "output_tokens",
        "completion_tokens": "output_tokens",
        "output": "output_tokens",
        "completion": "output_tokens",
        "total_tokens": "total_tokens",
        "tokens": "total_tokens",
        "total": "total_tokens",
    }

    candidates: list[dict[str, Any]] = [payload]
    for key in ("usage", "token_usage", "tokens", "metrics", "stats"):
        value = payload.get(key)
        if isinstance(value, dict):
            candidates.append(value)

    for candidate in candidates:
        for key, value in candidate.items():
            normalized = slugify(key)
            canonical = alias_map.get(normalized)
            amount = safe_int(value)
            if canonical and amount is not None:
                usage[canonical] = max(usage[canonical], amount)

    for value in payload.values():
        if isinstance(value, dict):
            usage = merge_usage_counts(usage, usage_from_mapping(value))

    return usage


def progress_from_mapping(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        return None
    for key in ("progress", "progress_pct", "progress_percent", "percent", "completion", "completion_pct"):
        value = payload.get(key)
        amount = safe_int(value)
        if amount is not None and 0 <= amount <= 100:
            return amount
    for value in payload.values():
        if isinstance(value, dict):
            nested = progress_from_mapping(value)
            if nested is not None:
                return nested
    return None


def message_from_mapping(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("message", "status", "event", "phase", "detail", "summary", "step"):
        value = str(payload.get(key, "")).strip()
        if value:
            return value
    for value in payload.values():
        if isinstance(value, dict):
            nested = message_from_mapping(value)
            if nested:
                return nested
    return ""


def usage_from_text(line: str) -> dict[str, int]:
    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    patterns = {
        "input_tokens": [r"input[_\s-]?tokens?\s*[:=]\s*(\d+)", r"prompt[_\s-]?tokens?\s*[:=]\s*(\d+)"],
        "output_tokens": [
            r"output[_\s-]?tokens?\s*[:=]\s*(\d+)",
            r"completion[_\s-]?tokens?\s*[:=]\s*(\d+)",
        ],
        "total_tokens": [r"total[_\s-]?tokens?\s*[:=]\s*(\d+)", r"tokens?\s*[:=]\s*(\d+)"],
    }
    for key, regexes in patterns.items():
        for regex in regexes:
            match = re.search(regex, line, flags=re.IGNORECASE)
            if match:
                usage[key] = max(usage[key], int(match.group(1)))
    return merge_usage_counts({}, usage)


def progress_from_text(line: str) -> int | None:
    match = re.search(r"\b(\d{1,3})%\b", line)
    if not match:
        return None
    value = int(match.group(1))
    return value if 0 <= value <= 100 else None


def read_log_telemetry(log_path: Path) -> dict[str, Any]:
    telemetry = {
        "phase": "",
        "progress_pct": None,
        "last_activity_at": "",
        "last_line": "",
        "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        "log_size_bytes": 0,
    }
    if not log_path.exists():
        return telemetry

    try:
        stat = log_path.stat()
        telemetry["log_size_bytes"] = int(stat.st_size)
        telemetry["last_activity_at"] = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-160:]
    except OSError:
        return telemetry

    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    phase = ""
    progress = None
    last_line = ""
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        last_line = truncate_text(line)
        parsed: Any = None
        if line.startswith("{") and line.endswith("}"):
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                parsed = None
        if isinstance(parsed, dict):
            usage = merge_usage_counts(usage, usage_from_mapping(parsed))
            progress = progress_from_mapping(parsed) if progress_from_mapping(parsed) is not None else progress
            message = message_from_mapping(parsed)
            if message:
                phase = truncate_text(message)
        else:
            usage = merge_usage_counts(usage, usage_from_text(line))
            text_progress = progress_from_text(line)
            if text_progress is not None:
                progress = text_progress
            if not phase and line:
                phase = truncate_text(line)

    telemetry["phase"] = phase or last_line
    telemetry["progress_pct"] = progress
    telemetry["last_line"] = last_line
    telemetry["usage"] = usage
    return telemetry
