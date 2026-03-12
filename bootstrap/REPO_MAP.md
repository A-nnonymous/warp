# Repo Map

## Core Purpose

`warp` is a standalone multi-agent control plane that coordinates delivery work against an external target repository.

It owns:

- backlog and gate state
- provider and resource-pool routing
- worker launch and stop orchestration
- manager merge visibility
- resumable checkpoints, heartbeats, and mailbox coordination

## Highest-Value Files

- `runtime/control_plane.py`: backend runtime, API surface, validation, launch, worktree management, state synthesis
- `runtime/config_template.yaml`: cold-start fallback config
- `runtime/local_config.yaml`: real operator config on a machine, ignored by git
- `runtime/web/src/App.tsx`: main dashboard UI and settings logic
- `runtime/web/src/api.ts`: frontend API contract
- `runtime/web/src/types.ts`: frontend data model
- `runtime/web/static/app.js` and `runtime/web/static/app.css`: built frontend assets served in production

## Control-State Files

- `state/backlog.yaml`: tasks, ownership, review state, dependencies
- `state/gates.yaml`: program gates
- `state/heartbeats.yaml`: liveness and escalation
- `state/agent_runtime.yaml`: runtime topology and worker records
- `state/team_mailbox.yaml`: durable collaboration inbox
- `state/edit_locks.yaml`: single-writer lock state

## Operator and Governance Docs

- `README.md`: operator-facing overview and common commands
- `governance/axioms.md`: foundational axioms, human-write-only
- `governance/manager_protocol.md`: manager contract, interruption priority, self-evolution, planning authority
- `governance/documentation_architecture.md`: markdown responsibility map
- `governance/control_plane_playbook.md`: change checklist for warp itself
- `governance/worker_launch_playbook.md`: worker launch semantics
- `governance/operating_model.md`: durable collaboration model
- `governance/agent_team_patterns.md`: intended multi-agent coordination primitives

## Resume vs Bootstrap

- `RESUME.md`: restore live session state
- `new_machine_prompt.md`: first-time recovery on a fresh machine
- `bootstrap/*`: take over ongoing development of warp with minimal context cost

## Build and Validation Paths

- Frontend source lives in `runtime/web/src/`
- Rebuild frontend with `cd runtime/web && npm run build`
- Main regression suite is `python3 -m unittest runtime.test_control_plane_integration -v`
