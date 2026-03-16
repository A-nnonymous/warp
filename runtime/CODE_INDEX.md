# CODE_INDEX — runtime/

Runtime subtree for the WARP control plane.

## Layout

| Path | Purpose |
|---|---|
| `control_plane.py` | Backward-compatible CLI entry point that re-exports from `runtime/cp/` |
| `cp/` | Backend control-plane package | 
| `web/` | Dashboard frontend source and built static assets |
| `generated/` | Runtime-generated prompts, wrappers, session-state files, and logs |
| `config_template.yaml` | Cold-start config template |
| `local_config.yaml` | Machine-local runtime config (ignored by git) |

## Generated Runtime Artifacts

| Path | Contents |
|---|---|
| `generated/prompts/` | Worker prompts and checkpoint prompts |
| `generated/wrappers/` | Provider wrapper scripts |
| `generated/sessions/` | Session-state snapshots, including port-specific files |
| `generated/logs/` | Control-plane and worker logs |

## Follow-up indexes

- Backend: `runtime/cp/CODE_INDEX.md`
- Frontend: `runtime/web/src/CODE_INDEX.md`
