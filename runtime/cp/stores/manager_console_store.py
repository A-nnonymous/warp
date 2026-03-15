from __future__ import annotations

from pathlib import Path
from typing import Any

from ..utils import dump_yaml, load_yaml


class ManagerConsoleStore:
    def __init__(self, path: Path):
        self.path = path

    @staticmethod
    def default_state() -> dict[str, Any]:
        return {"requests": {}, "messages": []}

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self.default_state()
        data = load_yaml(self.path)
        if not isinstance(data, dict):
            return self.default_state()
        requests = data.get("requests", {})
        messages = data.get("messages", [])
        return {
            "requests": requests if isinstance(requests, dict) else {},
            "messages": messages if isinstance(messages, list) else [],
        }

    def persist(self, state: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "requests": state.get("requests") if isinstance(state.get("requests"), dict) else {},
            "messages": state.get("messages") if isinstance(state.get("messages"), list) else [],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        dump_yaml(self.path, payload)
        return payload
