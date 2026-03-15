from __future__ import annotations

from pathlib import Path
from typing import Any

from ..utils import dump_yaml, load_yaml, now_iso


class LockStore:
    def __init__(self, path: Path):
        self.path = path

    @staticmethod
    def default_state() -> dict[str, Any]:
        return {"policy": {}, "locks": [], "last_updated": ""}

    @staticmethod
    def normalize_lock(item: dict[str, Any]) -> dict[str, str]:
        normalized = dict(item)
        return {
            "path": str(normalized.get("path") or "").strip(),
            "owner": str(normalized.get("owner") or "").strip(),
            "state": str(normalized.get("state") or "free").strip() or "free",
            "intent": str(normalized.get("intent") or "").strip(),
            "updated_at": str(normalized.get("updated_at") or "").strip(),
        }

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self.default_state()
        data = load_yaml(self.path)
        if not isinstance(data, dict):
            return self.default_state()
        locks = data.get("locks", [])
        return {
            "policy": data.get("policy") if isinstance(data.get("policy"), dict) else {},
            "locks": [self.normalize_lock(item) for item in locks if isinstance(item, dict)],
            "last_updated": str(data.get("last_updated") or "").strip(),
        }

    def persist(self, state: dict[str, Any]) -> dict[str, Any]:
        locks = state.get("locks", []) if isinstance(state, dict) else []
        payload = {
            "policy": state.get("policy") if isinstance(state, dict) and isinstance(state.get("policy"), dict) else {},
            "locks": [self.normalize_lock(item) for item in locks if isinstance(item, dict)],
            "last_updated": now_iso(),
        }
        dump_yaml(self.path, payload)
        return payload
