# Latest Checkpoint

Timestamp: 2026-03-10
Project: sonicmoe-fp8
Phase: preflight bootstrap
Manager: A0

## Snapshot

- Governance scaffold exists in ``
- FP8 project plan exists in `strategy/integration_plan.md`
- baseline trace exists in `strategy/baseline_trace.md`
- heartbeat registry exists in `state/heartbeats.yaml`
- edit-lock registry exists in `state/edit_locks.yaml`
- per-agent checkpoints exist in `checkpoints/agents/`
- real implementation has not started
- no governed experiments have been launched

## Current Goal

Pass G0 Protocol Freeze.

## Must-keep Facts

- final target is torch-only MoE enhancement
- `tests/reference_layers/standalone_moe_layer` is the main correctness baseline
- `tests/reference_layers/standalone_moe_layer/moe_standalone/compat.py` is the key reference compatibility shim
- Paddle is semantic reference plus compatibility input
- grouped_gemm already has float8-related hooks
- QuACK already exists for Blackwell-oriented flow

## Resume Rule

Start from `RESUME.md`.

For a first boot on a clean machine, start from `new_machine_prompt.md`.