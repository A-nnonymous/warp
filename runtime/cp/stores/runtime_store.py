from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts import RuntimeState
from ..utils import dump_yaml, load_yaml, now_iso


class RuntimeStore:
    def __init__(self, path: Path):
        self.path = path

    @staticmethod
    def default_state() -> RuntimeState:
        return {"workers": [], "last_updated": ""}

    @staticmethod
    def normalize_worker(entry: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(entry)
        return {
            **normalized,
            "agent": str(normalized.get("agent") or "").strip(),
            "task_id": str(normalized.get("task_id") or "").strip(),
            "repository_name": str(normalized.get("repository_name") or "").strip(),
            "resource_pool": str(normalized.get("resource_pool") or "unassigned").strip() or "unassigned",
            "provider": str(normalized.get("provider") or "unassigned").strip() or "unassigned",
            "model": str(normalized.get("model") or "unassigned").strip() or "unassigned",
            "recursion_guard": str(normalized.get("recursion_guard") or "").strip(),
            "launch_wrapper": str(normalized.get("launch_wrapper") or "").strip(),
            "launch_owner": str(normalized.get("launch_owner") or "").strip(),
            "local_workspace_root": str(normalized.get("local_workspace_root") or "").strip(),
            "repository_root": str(normalized.get("repository_root") or "").strip(),
            "worktree_path": str(normalized.get("worktree_path") or "").strip(),
            "branch": str(normalized.get("branch") or "").strip(),
            "merge_target": str(normalized.get("merge_target") or "").strip(),
            "environment_type": str(normalized.get("environment_type") or "").strip(),
            "environment_path": str(normalized.get("environment_path") or "").strip(),
            "sync_command": str(normalized.get("sync_command") or "").strip(),
            "test_command": str(normalized.get("test_command") or "").strip(),
            "submit_strategy": str(normalized.get("submit_strategy") or "").strip(),
            "git_author_name": str(normalized.get("git_author_name") or "").strip(),
            "git_author_email": str(normalized.get("git_author_email") or "").strip(),
            "status": str(normalized.get("status") or "").strip(),
        }

    def load(self) -> RuntimeState:
        if not self.path.exists():
            return self.default_state()
        data = load_yaml(self.path)
        if not isinstance(data, dict):
            return self.default_state()
        workers = data.get("workers", [])
        return {
            "project": str(data.get("project") or "").strip(),
            "last_updated": str(data.get("last_updated") or "").strip(),
            "schema": data.get("schema") if isinstance(data.get("schema"), dict) else {},
            "workers": [self.normalize_worker(item) for item in workers if isinstance(item, dict)],
        }

    def persist(self, state: dict[str, Any]) -> RuntimeState:
        workers = state.get("workers", []) if isinstance(state, dict) else []
        payload: RuntimeState = {
            "project": str(state.get("project") or "").strip() if isinstance(state, dict) else "",
            "schema": state.get("schema") if isinstance(state, dict) and isinstance(state.get("schema"), dict) else {},
            "last_updated": now_iso(),
            "workers": [self.normalize_worker(item) for item in workers if isinstance(item, dict)],
        }
        dump_yaml(self.path, payload)
        return payload
