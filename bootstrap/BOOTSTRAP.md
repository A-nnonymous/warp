# Agent Bootstrap

## Purpose

Use this folder when a zero-context AI agent needs to take over `warp` itself, not just resume a live operator session.

This package is optimized for low token cost:

1. read the bootstrap files first
2. read only the repo files required by the current task
3. avoid re-discovering already-settled workflow decisions

`RESUME.md` and `new_machine_prompt.md` remain the right entrypoints for restoring a live control session. This folder is for continuing control-plane development and self-iteration.

## Minimal Read Order

1. `governance/axioms.md`
2. `bootstrap/REPO_MAP.md`
3. `bootstrap/SETTLED_INVARIANTS.md`
4. `bootstrap/OPERATING_LOOP.md`
5. `bootstrap/RECENT_DECISIONS.md`
6. `README.md`
7. `governance/manager_protocol.md`
8. `governance/documentation_architecture.md`
9. `governance/control_plane_playbook.md`

After that, read only the files directly relevant to the task.

## About Governance Files

Three governance files are part of the default low-cost takeover path:

- `governance/manager_protocol.md`: manager responsibilities, interruption priority, self-evolution, and planning authority
- `governance/documentation_architecture.md`: markdown responsibility boundaries and anti-noise rules
- `governance/control_plane_playbook.md`: change checklist for evolving `warp` itself

Read these additional governance files when the task touches operator-facing workflow or collaboration semantics:

- `governance/operating_model.md`: runtime isolation, lock discipline, heartbeat semantics, and manager loop
- `governance/worker_launch_playbook.md`: worker startup, worktree, branch, and environment semantics
- `governance/agent_team_patterns.md`: current coordination rationale plus still-open pattern extensions

## Canonical Bootstrap Prompt

Paste this into a fresh AI session:

```text
You are taking over development of the warp repository itself.

Your goal is to continue improving the control plane with minimal context-gathering cost and without regressing settled workflow decisions.

Before writing code:
1. Read governance/axioms.md.
2. Read bootstrap/BOOTSTRAP.md.
3. Read bootstrap/REPO_MAP.md.
4. Read bootstrap/SETTLED_INVARIANTS.md.
5. Read bootstrap/OPERATING_LOOP.md.
6. Read bootstrap/RECENT_DECISIONS.md.
7. Read README.md.
8. Read governance/manager_protocol.md.
9. Read governance/documentation_architecture.md.
10. Read governance/control_plane_playbook.md.

Then produce a short takeover report that includes:
- what warp is responsible for
- the current default operator path
- the settled invariants you must not regress
- the exact repo files you now need to inspect for the requested task
- the validation commands you will run before finishing
- redundancies, contradictions, or confusing passages found during bootstrap reading, with concrete fix proposals

Only after that report, fix any bootstrap doc issues you found, then inspect the task-specific files and implement the requested change.

Rules:
- Prefer the simplest operator workflow.
- Do not reintroduce manual YAML-first setup when A0 can derive the same data.
- Keep docs, runtime behavior, frontend state, and tests aligned in the same change.
- Rebuild runtime/web/static after frontend source edits.
- Rebuild frontend with `cd runtime/web && npm run build` immediately after editing any file in `runtime/web/src/`; do not rely on stale built assets.
- Run Python compile checks and the integration suite after meaningful workflow changes.
- If touching settings, launch, worktree, provider routing, or validation logic, check whether current local config behavior still matches the UI.
```

## When To Read More

- For live orchestration state, switch to `RESUME.md`.
- For new-machine recovery, switch to `new_machine_prompt.md`.
- For unresolved technical decisions or still-open tradeoffs, read `governance/decisions.md`.
- For launch and operator workflow changes, read `governance/control_plane_playbook.md`.
- For manager behavior, interruption priority, and self-evolution logic, read `governance/manager_protocol.md`.
- For markdown responsibility boundaries, read `governance/documentation_architecture.md`.
- For collaboration semantics, read `governance/agent_team_patterns.md` and `governance/operating_model.md`.

## Bootstrap Audit Requirement

Every bootstrap must include a feedback pass before starting real work:

1. After reading the bootstrap files, identify redundancies, contradictions, or confusing passages you encountered.
2. Fix them in the same session if the fix is small and clear.
3. If the fix is large, record it as a backlog item with a concrete proposal.

This is not optional. The bootstrap package degrades silently unless every new agent actively maintains it.

## Expected Finish Quality

Every meaningful change should leave behind:

- aligned docs and runtime behavior
- updated compiled frontend assets when UI source changed
- passing validation commands
- no regression of the default ducc-first path
- bootstrap docs updated if a new invariant was settled or an old one was corrected
