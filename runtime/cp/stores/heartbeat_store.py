from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts import HeartbeatState
from ..utils import dump_yaml, load_yaml, now_iso


class HeartbeatStore:
    def __init__(self, path: Path):
        self.path = path

    @staticmethod
    def default_state() -> HeartbeatState:
        return {"agents": [], "last_updated": ""}

    @staticmethod
    def normalize_agent(entry: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(entry)
        return {
            **normalized,
            "agent": str(normalized.get("agent") or "").strip(),
            "role": str(normalized.get("role") or "worker").strip() or "worker",
            "state": str(normalized.get("state") or "not-started").strip() or "not-started",
            "last_seen": str(normalized.get("last_seen") or "").strip(),
            "evidence": str(normalized.get("evidence") or "").strip(),
            "expected_next_checkin": str(normalized.get("expected_next_checkin") or "").strip(),
            "escalation": str(normalized.get("escalation") or "").strip(),
        }

    def load(self) -> HeartbeatState:
        if not self.path.exists():
            return self.default_state()
        data = load_yaml(self.path)
        if not isinstance(data, dict):
            return self.default_state()
        agents = data.get("agents", [])
        return {
            "project": str(data.get("project") or "").strip(),
            "last_updated": str(data.get("last_updated") or "").strip(),
            "agents": [self.normalize_agent(item) for item in agents if isinstance(item, dict)],
        }

    def persist(self, state: dict[str, Any]) -> HeartbeatState:
        agents = state.get("agents", []) if isinstance(state, dict) else []
        payload: HeartbeatState = {
            "project": str(state.get("project") or "").strip() if isinstance(state, dict) else "",
            "last_updated": now_iso(),
            "agents": [self.normalize_agent(item) for item in agents if isinstance(item, dict)],
        }
        dump_yaml(self.path, payload)
        return payload
