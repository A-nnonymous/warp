# Latest Checkpoint

Timestamp: 2026-03-12
Project: sonicmoe-fp8
Phase: post-audit bootstrap
Manager: A0

## Snapshot

- Governance scaffold complete, axioms.md added as human-write-only foundation
- Bootstrap docs optimized: README 421→199 lines, validation commands single-sourced, audit feedback loop added
- Full architecture audit completed: backend (4855 lines), frontend (2959 lines), config, state files
- Integration tests: 24/24 passing after uv-fallback fix
- Frontend build: skipped (current machine has no npm; static assets from prior build intact)
- FP8 project plan exists in `strategy/integration_plan.md`
- Baseline trace exists in `strategy/baseline_trace.md`
- Real implementation has not started
- No governed experiments have been launched

## What Changed This Session

- `governance/axioms.md`: 7 foundational axioms (human-write-only)
- `README.md`: deduplicated commands (5→1), added key terms, disambiguated read lists
- `bootstrap/`: audit feedback mechanism, validation single-sourced to OPERATING_LOOP.md
- `runtime/control_plane.py`: detach_process prefers system python when yaml is available
- `runtime/test_control_plane_integration.py`: _server_launch_cmd falls back to system python

## Known Issues From Audit

- `manager_local` resource pool referenced in agent_runtime.yaml but undeclared in config/provider_stats
- Gate G5 (Training Closure) has no backlog item
- A5-001 task dependencies narrower than its gate G4 dependencies (potential drift)
- 3 of 4 provider pools unreachable (only ducc_pool is live)
- Frontend: 2959-line single-file App.tsx, no test infra, no useCallback/memo, no debounce on hydration

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

1. Fix state file inconsistencies (undeclared manager_local pool, missing G5 backlog item)
2. Advance G0: launch A1 (protocol freeze) and A6 (baseline trace freeze)

## Resume Rule

Start from `RESUME.md`.

For a first boot on a clean machine, start from `new_machine_prompt.md`.
