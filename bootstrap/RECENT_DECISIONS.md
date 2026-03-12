# Recent Decisions

This file captures the most important recent development context that is not obvious from the repo layout alone.

## Collaboration and Manager UX

Recent control-plane work added:

- mailbox compose and mailbox peek flows
- A0 console request handling
- workflow patching and preset actions for replan, reassign, and reopen
- cleanup readiness and guarded cleanup confirmation
- per-worker shutdown without collapsing the whole listener

These are implemented runtime behaviors, not future proposals.

## ducc-First Operating Model

The repo was moved to a ducc-first default path:

- runtime default provider is `ducc`
- checked-in template prefers `ducc`
- dashboard launch defaults are `Initial Provider` plus `ducc`
- README now documents ducc as the out-of-box path

## Settings and Bootstrap Fixes

Recent bug fixes established these behaviors:

- dashboard launch persists dirty settings before launch
- frontend and backend now agree on worktree semantics
- backend worktree initialization uses the target repository root from config
- `uv` environment paths are no longer blocked just because the `.venv` path does not already exist
- merge-status cards were cleaned up to avoid visual misalignment

## Coordination Extensions Still In Design

`governance/agent_team_patterns.md` contains both rationale and future-facing pattern extensions.

Already implemented:

- durable team mailbox
- A0 review and approval flows
- cleanup readiness and worker shutdown semantics

Still not fully promoted to first-class runtime law:

- richer task claim and release semantics across the backlog schema
- broader completion-hook style acceptance gates beyond the current review flow
- further teammate-to-teammate coordination extensions beyond the current mailbox model

Treat those items as design territory unless the runtime and state schema explicitly support them.

## Validation Baseline

The reliable validation path for meaningful warp workflow changes is:

1. `python3 -m py_compile runtime/control_plane.py runtime/test_control_plane_integration.py`
2. `cd runtime/web && npm run build`
3. `python3 -m unittest runtime.test_control_plane_integration -v`

## If You Touch These Areas Again

- `runtime/control_plane.py`: re-check config validation, launch blockers, and worktree/bootstrap behavior together
- `runtime/web/src/App.tsx`: re-check settings hydration, section save behavior, and launch behavior together
- `README.md`: keep operator instructions aligned with runtime behavior in the same patch
