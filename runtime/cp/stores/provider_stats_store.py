from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..utils import dump_yaml, load_yaml


class ProviderStatsStore:
    def __init__(self, path: Path, default_entry_factory: Callable[[], dict[str, Any]]):
        self.path = path
        self.default_entry_factory = default_entry_factory

    def load(self) -> dict[str, dict[str, Any]]:
        data = load_yaml(self.path) if self.path.exists() else {}
        if not isinstance(data, dict):
            return {}
        stats: dict[str, dict[str, Any]] = {}
        for pool_name, entry in data.items():
            if isinstance(entry, dict):
                stats[str(pool_name)] = {**self.default_entry_factory(), **entry}
        return stats

    def persist(self, state: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        dump_yaml(self.path, state)
        return state
