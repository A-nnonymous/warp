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

See `bootstrap/OPERATING_LOOP.md` for the canonical validation commands and area-specific triggers.

## Bootstrap Doc Optimization (2026-03-12)

- README deduplicated from 421→199 lines; commands consolidated to one table
- Validation commands single-sourced to OPERATING_LOOP.md
- Bootstrap audit feedback loop added to BOOTSTRAP.md and canonical prompt
- `governance/axioms.md` created as human-write-only foundation, placed first in bootstrap read order

## Runtime Launcher Fallback (2026-03-12)

- `detach_process` in control_plane.py and test harness both prefer system python when yaml is importable
- This fixed 24/24 test failures in offline environments where `uv` cannot reach PyPI
- Settled as invariant in SETTLED_INVARIANTS.md

## Architecture Audit Findings (2026-03-12)

State file inconsistencies to address before launch:

- `manager_local` pool referenced in agent_runtime.yaml but undeclared in config and provider_stats
- Gate G5 has no corresponding backlog item
- Frontend is a 2959-line single file with no test infrastructure
