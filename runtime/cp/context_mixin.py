from __future__ import annotations

from typing import Any

from .constants import STATE_DIR
from .utils import dedupe_strings, load_yaml, yaml_text


class ContextMixin:
    """Per-agent context scoping for prompt rendering.

    Filters backlog, gates, and runtime state to only the entries relevant
    to a specific worker, then renders them inline in the prompt so the
    agent never needs to read the full shared state files.
    """

    def scoped_backlog_brief(self, worker: dict[str, Any], profile: dict[str, Any]) -> str:
        """Return YAML for the agent's own tasks plus direct upstream dependencies."""
        agent = str(worker.get("agent", "")).strip()
        task_id = str(worker.get("task_id") or profile.get("task_id") or "").strip()
        all_items = self.backlog_items()

        own_items = [
            item for item in all_items
            if str(item.get("owner", "")).strip() == agent
            or str(item.get("id", "")).strip() == task_id
        ]
        dep_ids: set[str] = set()
        for item in own_items:
            deps = item.get("dependencies")
            if isinstance(deps, list):
                for dep in deps:
                    dep_ids.add(str(dep).strip())

        dep_items = [
            item for item in all_items
            if str(item.get("id", "")).strip() in dep_ids
            and item not in own_items
        ]

        scoped = own_items + dep_items
        if not scoped:
            return "items: []"
        return yaml_text({"items": scoped}).rstrip()

    def scoped_gates_brief(self, worker: dict[str, Any], profile: dict[str, Any]) -> str:
        """Return YAML for only the gates relevant to this agent's tasks."""
        agent = str(worker.get("agent", "")).strip()
        task_id = str(worker.get("task_id") or profile.get("task_id") or "").strip()
        all_items = self.backlog_items()

        own_items = [
            item for item in all_items
            if str(item.get("owner", "")).strip() == agent
            or str(item.get("id", "")).strip() == task_id
        ]
        dep_ids: set[str] = set()
        for item in own_items:
            deps = item.get("dependencies")
            if isinstance(deps, list):
                for dep in deps:
                    dep_ids.add(str(dep).strip())
        dep_items = [
            item for item in all_items
            if str(item.get("id", "")).strip() in dep_ids
        ]

        needed_gate_ids: set[str] = set()
        for item in own_items + dep_items:
            gate = str(item.get("gate", "")).strip()
            if gate:
                needed_gate_ids.add(gate)

        gates_data = load_yaml(STATE_DIR / "gates.yaml")
        all_gates = gates_data.get("gates", []) if isinstance(gates_data, dict) else []
        if not isinstance(all_gates, list):
            all_gates = []

        # Also include parent gates (one level of depends_on)
        for gate in all_gates:
            if str(gate.get("id", "")).strip() in needed_gate_ids:
                parent_deps = gate.get("depends_on")
                if isinstance(parent_deps, list):
                    for parent_id in parent_deps:
                        needed_gate_ids.add(str(parent_id).strip())

        scoped = [g for g in all_gates if str(g.get("id", "")).strip() in needed_gate_ids]
        if not scoped:
            return "gates: []"
        return yaml_text({"gates": scoped}).rstrip()

    def scoped_runtime_brief(self, worker: dict[str, Any]) -> str:
        """Return YAML for only this agent's runtime entry."""
        agent = str(worker.get("agent", "")).strip()
        runtime_data = load_yaml(STATE_DIR / "agent_runtime.yaml")
        all_workers = runtime_data.get("workers", []) if isinstance(runtime_data, dict) else []
        if not isinstance(all_workers, list):
            all_workers = []

        own_entry = [w for w in all_workers if str(w.get("agent", "")).strip() == agent]
        if not own_entry:
            return "workers: []"
        return yaml_text({"workers": own_entry}).rstrip()

    def render_inline_state_context(self, worker: dict[str, Any], profile: dict[str, Any]) -> str:
        """Render scoped state context as inline markdown for the prompt."""
        agent = str(worker.get("agent", "")).strip()
        task_type = str(profile.get("task_type", "default")).strip()
        task_id = str(worker.get("task_id") or profile.get("task_id") or "").strip()

        backlog_yaml = self.scoped_backlog_brief(worker, profile)
        gates_yaml = self.scoped_gates_brief(worker, profile)
        runtime_yaml = self.scoped_runtime_brief(worker)

        # Extract IDs for the scope summary line
        backlog_ids: list[str] = []
        for line in backlog_yaml.splitlines():
            stripped = line.strip()
            if stripped.startswith("- id:") or stripped.startswith("id:"):
                val = stripped.split(":", 1)[1].strip()
                if val:
                    backlog_ids.append(val)

        gate_ids: list[str] = []
        for line in gates_yaml.splitlines():
            stripped = line.strip()
            if stripped.startswith("- id:") or stripped.startswith("id:"):
                val = stripped.split(":", 1)[1].strip()
                if val:
                    gate_ids.append(val)

        scope_line = (
            f"Scope: agent={agent}, task_type={task_type}"
            f", backlog=[{', '.join(backlog_ids)}]"
            f", gates=[{', '.join(gate_ids)}]"
        )

        return f"""## Scoped state context (auto-generated)

{scope_line}

### Your backlog

```yaml
{backlog_yaml}
```

### Your gates

```yaml
{gates_yaml}
```

### Your runtime entry

```yaml
{runtime_yaml}
```"""

    def scoped_context_files(self, worker: dict[str, Any], profile: dict[str, Any]) -> list[str]:
        """Return the filtered strategy file list for this agent's task type.

        If the task type defines prompt_context_files, use that list (override).
        Otherwise fall back to the global project-level prompt_context_files.
        State files and governance/operating_model.md are never included
        (state is inlined; mandatory rules cover governance).
        """
        type_files = profile.get("prompt_context_files", [])
        if isinstance(type_files, list) and type_files:
            return dedupe_strings(type_files)
        return dedupe_strings(self.prompt_context_files())
