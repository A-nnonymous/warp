# Operating Loop

## Default Development Loop

1. Read the bootstrap files first.
2. Do a quick bootstrap-maintenance pass: note confusion, fix the small issues now.
3. Inspect only the task-relevant runtime, frontend, config, or doc files.
4. Implement the smallest coherent change.
5. Rebuild compiled assets if frontend source changed.
6. Run compile checks and workflow tests.
7. Update docs in the same change when operator behavior changed.

## Human-First Operating Surfaces

Use the most humane surface that still preserves durable state:

- remember that A0 is the default workflow operator; the human mainly observes and intervenes on exceptions
- use the control plane for approvals, unblock instructions, workflow changes, and other canonical execution facts that need human involvement
- use external Copilot sessions for dense implementation, debugging, and design iteration
- before ending an external session, write the durable result back into workflow state, mailbox, or checkpoints

Default write-back rule:

- workflow update for task-state changes
- mailbox for durable coordination context
- checkpoint for resumability, handoff, or interruption safety

## Validation Commands

- Python syntax: `python3 -m py_compile runtime/control_plane.py tests/runtime/test_control_plane_integration.py`
- Frontend build: `cd runtime/web && npm run build`
- Integration suite: `python3 -m unittest tests.runtime.test_control_plane_integration -v`

## When Extra Validation Is Required

Run an additional live check when changing:

- settings save and validate behavior: confirm section saves persist the intended runtime config
- launch policy or provider defaults: confirm launch blockers and selected provider/model behavior match UI expectations
- worktree derivation or initialization: confirm derived paths and actual git worktree creation stay aligned
- environment bootstrap semantics: confirm `uv` and `venv` validation rules still match runtime bootstrap behavior
- section-level save fallback behavior: confirm launch cannot silently use stale placeholder config

Preferred live check pattern:

1. start the control plane with `python runtime/control_plane.py serve` or the equivalent `uv run` wrapper
2. load `runtime/local_config.yaml` through the runtime or Settings flow
3. confirm `launch_blockers` and validation output match the intended UI behavior
4. cross-check worktree paths, branch names, and environment semantics against runtime state
5. if launch behavior changed, attempt a representative launch path and confirm provider/model selection

## Editing Rules For Warp

- Preserve the simplest operator path first.
- Keep `worker_defaults` as the shared layer; use per-worker overrides only for real exceptions.
- Keep A0-derived values authoritative when safe to infer.
- Avoid stale duplication between runtime behavior and README/docs.
- Never change frontend source without rebuilding static assets.

## Area-Specific Validation Triggers

When touching these areas, cross-check the related concerns together:

- `runtime/control_plane.py`: config validation, launch blockers, and worktree/bootstrap behavior
- `runtime/web/src/App.tsx`: settings hydration, section save behavior, and launch behavior
- `README.md` / `README_CN.md`: operator instructions must match runtime behavior in the same patch

## Handoff Rules

If you settle a new workflow invariant, update this bootstrap folder so the next agent does not have to rediscover it.

If you notice a bootstrap inefficiency but do not fix it immediately, leave behind a concrete proposal instead of a vague note.
