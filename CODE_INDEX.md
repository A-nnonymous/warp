# CODE_INDEX — repository root

Top-level navigation index for WARP. Prefer this file before grepping the full tree.

## Major Directories

| Path | Purpose | Follow-up index |
|---|---|---|
| `runtime/` | Control plane backend, frontend, config templates, generated runtime artifacts | `runtime/CODE_INDEX.md` |
| `tests/` | Isolated Python test suite | `tests/CODE_INDEX.md` |
| `bootstrap/` | Minimal takeover package for new agent sessions | Read `bootstrap/BOOTSTRAP.md` first |
| `governance/` | Durable rules, operating model, architecture decisions | Start with `governance/manager_protocol.md` |
| `strategy/` | Program plans, baseline traces, integration context | Inspect task-relevant files only |
| `state/` | Durable workflow state, mailbox, locks, heartbeats | Live state: edit carefully |
| `status/agents/` | Worker status feeds | Pair with checkpoints |
| `checkpoints/` | Resumable worker / manager handoff snapshots | `checkpoints/manager/latest.md` for resume |
| `reports/` | Reports, audits, manager-facing artifacts | Historical / delivery output |
| `worktrees/` | Per-worker git worktrees | Runtime-managed |

## Primary Entry Points

- `README.md`: English operator and agent overview.
- `README_CN.md`: Chinese operator and agent overview.
- `RESUME.md`: Resume path for interrupted live sessions.
- `new_machine_prompt.md`: Cold-start recovery prompt.
- `runtime/control_plane.py`: Backward-compatible CLI entry point.
- `runtime/local_config.yaml`: Machine-local runtime config.

## Validation Shortcuts

- Python compile: `python3 -m py_compile runtime/control_plane.py tests/runtime/test_control_plane_integration.py`
- Integration suite: `python3 -m unittest tests.runtime.test_control_plane_integration -v`
- Frontend build: `source ~/.bashrc && cd runtime/web && npm run build`
