# Latest Checkpoint

Timestamp: 2026-03-16 02:1x CST
Project: sonicmoe-fp8
Phase: control-plane architecture refactor
Manager: A0

## Snapshot

- Latest completed stage commit before this session: `e4d25fc` (`extract dashboard queue service`)
- This stage extracted backlog workflow/task-action semantics into `runtime/cp/services/workflow_patch.py`
- `backlog_mixin.py` now delegates task action mutation, workflow patch shaping, and patch summary generation to pure service helpers
- New targeted test file `runtime/test_workflow_patch_service.py` covers claim/plan/review/complete guards, workflow patch shaping, validation, and summary text
- Targeted regression/integration slice is green:
  - `runtime.test_workflow_patch_service`
  - `runtime.test_control_plane_architecture`
  - `runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_task_actions_drive_plan_and_review_flow`
  - `runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_workflow_update_allows_a0_replan`
- Next likely seam if continuing in a fresh session: extract backlog mailbox recipient/topic fanout or add typed contracts for workflow/task-action payloads

## What Changed This Session

### Refactoring
- Added `runtime/cp/services/workflow_patch.py` with `apply_task_action()`, `apply_workflow_patch()`, `validate_workflow_updates()`, and `summarize_workflow_patch()`
- Slimmed `runtime/cp/backlog_mixin.py` so it keeps persistence/mailbox orchestration while delegating pure backlog state transitions to the service layer
- Exported workflow patch helpers from `runtime/cp/services/__init__.py`
- Updated `runtime/cp/CODE_INDEX.md` to include the new workflow patch service

### Tests
- Added `runtime/test_workflow_patch_service.py`
- Verified targeted architecture + integration regression slice remains green after extraction

## Current Goal

Continue shrinking manager-side mixins into pure services without breaking workflow/review semantics.

## Next Safe Step

1. Start a new session from this commit and choose one seam only:
   - backlog mailbox fanout / notification payload service
   - typed contracts for workflow/task-action payloads

## Resume Rule

Start from `RESUME.md`.

---

Timestamp: 2026-03-13
Project: sonicmoe-fp8
Phase: post-audit bootstrap
Manager: A0

## Snapshot

- Governance scaffold complete, axioms.md in place
- Bootstrap docs optimized and audit-maintained
- Full architecture audit completed and acted upon
- Integration tests: 24/24 passing (all bugs fixed)
- Dead code removed: ~400 lines of duplicate methods across mixins
- monitor_loop refactored: batched I/O (1 load + 1 dump per file per tick, down from N)
- build_dashboard_state refactored: parameter threading eliminates ~10 redundant YAML reads per API call
- utils.py / network.py / telemetry.py deduped: 6 duplicate function bodies removed
- cli.py unreachable branch removed, signature cleaned
- 233GB of leaked test temp dirs cleaned from /tmp
- Stale logs, session states, generated files cleaned
- FP8 project plan exists in `strategy/integration_plan.md`
- Baseline trace exists in `strategy/baseline_trace.md`
- Real implementation has not started
- No governed experiments have been launched

## What Changed This Session

### Bug Fixes
- `dashboard_mixin.py`: manager_runtime_entry no longer emits undeclared `manager_local` pool; uses `none` consistently with A0's role
- `state_mixin.py`: `update_heartbeat` now creates new agent entries (upsert) instead of silently skipping unknown agents
- `state_mixin.py`: `update_runtime_entry` ensures `workers` key is set on runtime dict when creating entries from empty state
- `test_control_plane_integration.py`: setUp excludes `worktrees/`, `node_modules/`, `__pycache__/`, `.git/`, `logs/` from copytree (was copying 48GB)
- `test_control_plane_integration.py`: setUp resets state files so tests start with clean first-launch environment
- `test_control_plane_integration.py`: test assertions updated for `none` provider/model on A0

### Refactoring
- `launch_mixin.py`: removed dead `stop_worker`, `stop_worker_locked` duplicates (canonical copies live in `backlog_mixin.py`)
- `state_mixin.py`: removed dead `runtime_worker_entries`, `edit_lock_state`, `cleanup_status`, `confirm_team_cleanup`, `release_listener_after_cleanup` (canonical copies live in `mailbox_mixin.py` and `backlog_mixin.py`)
- `state_mixin.py`: `monitor_loop` rewritten to batch all heartbeat and runtime updates into single load/dump per file per tick (was N loads + N dumps per tick)
- `dashboard_mixin.py`: `build_dashboard_state` now threads `runtime_state` and `heartbeat_state` through `merge_queue()`, `cleanup_status()`, `manager_heartbeat_entry()`, `dashboard_heartbeats_state()` — eliminates ~10 redundant `load_yaml` calls per `/api/state` request (was ~11 reads of 2 files, now 2 reads)
- `network.py`: removed 5 duplicate function bodies (`is_placeholder_path`, `is_local_host`, `path_exists_via_ls`, `host_reachable_via_ping`, `terminate_process_tree`); canonical copies remain in `utils.py`, `network.py` re-exports `terminate_process_tree` for `cli.py`
- `telemetry.py`: removed duplicate `merge_usage_counts` body; imports from `utils.py`
- `telemetry.py`: `read_log_telemetry` no longer calls `progress_from_mapping()` twice per JSON line; result is cached in a local variable
- `cli.py`: removed unreachable `elif args.command == "serve" and cold_start` branch and unused `cold_start` parameter from `apply_runtime_defaults()`

### Doc Fixes
- `bootstrap/REPO_MAP.md`: corrected `control_plane.py` description to reflect it's a 24-line re-export entry point, not the full backend
- `governance/control_plane_playbook.md`: fixed read order numbering (was 9,10,9,10 → now 9,10,11,12)

### Cleanup
- Removed 233GB of leaked `/tmp/fp8-*` test temp directories
- Removed `__pycache__`, empty log files, stale session state files, generated prompts/wrappers

## Audit Issues Status

- `manager_local` pool: FIXED (changed to `none`)
- Gate G5 backlog item: already existed as A4-002 (checkpoint note was stale)
- A5-001 dependency drift: still open (minor)
- 3 of 4 provider pools unreachable: expected (only ducc_pool is configured)
- Frontend single-file: still open (not addressed this session)

## Known Remaining Technical Debt

- Frontend still a single ~3000-line file with no test infrastructure
- A5-001 dependency drift: still open (minor)
- 3 of 4 provider pools unreachable: expected (only ducc_pool is configured)

## Current Goal

Pass G0 Protocol Freeze.

## Must-keep Facts

- final target is torch-only MoE enhancement
- `tests/reference_layers/standalone_moe_layer` is the main correctness baseline
- `tests/reference_layers/standalone_moe_layer/moe_standalone/compat.py` is the key reference compatibility shim
- Paddle is semantic reference plus compatibility input
- grouped_gemm already has float8-related hooks
- QuACK already exists for Blackwell-oriented flow

## Next Safe Step

1. Advance G0: launch A1 (protocol freeze) and A6 (baseline trace freeze)

## Resume Rule

Start from `RESUME.md`.

For a first boot on a clean machine, start from `new_machine_prompt.md`.
