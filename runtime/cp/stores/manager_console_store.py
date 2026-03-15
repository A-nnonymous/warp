from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts import A0ConsoleMessage, A0ConsoleRequest, ManagerConsoleState
from ..utils import dump_yaml, load_yaml


class ManagerConsoleStore:
    def __init__(self, path: Path):
        self.path = path

    @staticmethod
    def default_state() -> ManagerConsoleState:
        return {"requests": {}, "messages": []}

    def load(self) -> ManagerConsoleState:
        if not self.path.exists():
            return self.default_state()
        data = load_yaml(self.path)
        if not isinstance(data, dict):
            return self.default_state()
        requests = data.get("requests", {})
        messages = data.get("messages", [])
        normalized_requests: dict[str, A0ConsoleRequest] = {
            str(key): value
            for key, value in requests.items()
            if isinstance(key, str) and isinstance(value, dict)
        } if isinstance(requests, dict) else {}
        normalized_messages: list[A0ConsoleMessage] = [item for item in messages if isinstance(item, dict)] if isinstance(messages, list) else []
        return {
            "requests": normalized_requests,
            "messages": normalized_messages,
        }

    def persist(self, state: dict[str, Any]) -> ManagerConsoleState:
        requests = state.get("requests", {}) if isinstance(state, dict) else {}
        messages = state.get("messages", []) if isinstance(state, dict) else []
        payload: ManagerConsoleState = {
            "requests": {
                str(key): value
                for key, value in requests.items()
                if isinstance(key, str) and isinstance(value, dict)
            } if isinstance(requests, dict) else {},
            "messages": [item for item in messages if isinstance(item, dict)] if isinstance(messages, list) else [],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        dump_yaml(self.path, payload)
        return payload
