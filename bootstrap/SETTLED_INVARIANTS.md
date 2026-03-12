# Settled Invariants

These are the highest-value decisions that a takeover agent should not accidentally regress.

## Provider and Launch Defaults

- The default initial provider is `ducc`.
- The canonical default launch strategy is `initial_provider`, not `initial_copilot`.
- Backward compatibility for older `initial_copilot` payloads must remain intact.

## Settings and Launch Semantics

- Launch from the dashboard must persist dirty settings before worker launch.
- Section-level save and validate remain important, but unsaved valid edits must not cause launch to use stale placeholder config.
- A0 plan is the default execution target; manual worker fields are overrides, not required input.

## Worktree Semantics

- Derived worker worktrees live under `warp/worktrees/`.
- Worktree creation must run against `project.local_repo_root`, not the `warp` repo root.
- The frontend must not invent novel filesystem worktree roots that the backend cannot derive consistently.

## Environment Semantics

- For `uv`, `environment_path` is optional metadata and may point to a path that does not yet exist locally.
- For `venv`, `environment_path` is required and must exist.
- `uv sync` remains the real bootstrap mechanism for uv-backed workers.

## UI Semantics

- Branch Merge Status layout should remain flow-based and readable without absolute positioning.
- Shared defaults belong in `worker_defaults`; worker cards should stay lean and exception-oriented.

## Data-Driven Routing

- Resource-pool choice should stay driven by task policies, provider availability, and persisted quality history.
- Backlog `task_type` plus `task_policies` should remain the source of task-aware routing and test command selection.

## Code Index Maintenance

- Every code addition or structural change must update `CODE_INDEX.md` in the affected directory.
- New exports must appear in the index; split or merged modules must be reflected.
- Index files: `runtime/cp/CODE_INDEX.md` (backend), `runtime/web/src/CODE_INDEX.md` (frontend).

## Runtime Launcher Fallback

- When system Python already has PyYAML, both the test harness and `detach_process` must prefer `sys.executable` over `uv run`.
- `uv run --with PyYAML` is the fallback, not the default, because it requires network access to resolve packages.
- The `_server_launch_cmd` helper in the test file and the launcher logic in `detach_process` must stay aligned on this priority.
