# warp control plane

This repository hosts a standalone multi-agent control plane for coordinating delivery work against an external target repository.

WARP stands for Workload-aware Agents Routing Protocol. The control plane owns:

- agent planning and backlog state
- worker launch and stop orchestration
- provider and resource-pool routing
- branch and merge visibility for manager-owned integration
- resumable checkpoints, heartbeats, and runtime status

Default target repository name: `target-repo`

## Key terms

- **A0 plan**: the control plane's derived target state from backlog, runtime state, task policies, and shared defaults. It is the default execution target for all workers.
- **A0 Console**: the operational dashboard view over pending approvals, unresolved inbox items, and manager replies.
- **override**: a human-pinned exception that takes precedence over A0 plan until cleared. `Reset to A0` removes pinned values so derivation takes over again.
- **config fallback**: when `runtime/local_config.yaml` is missing, the runtime falls back to `runtime/config_template.yaml` and enters cold-start mode. Saving from the Settings page creates `local_config.yaml` automatically.

## Structure

- `strategy/`: program intent, scope, and baseline mapping
- `governance/`: operating rules, decisions, and machine policy
- `state/`: live backlog, gates, heartbeats, mailbox, and lock state
- `status/agents/`: live worker status feeds
- `checkpoints/`: resumable manager and worker snapshots
- `experiments/`: experiment registry
- `reports/`: production-facing reporting and delivery artifacts
- `bootstrap/`: low-overhead handoff package for zero-context AI agents continuing warp development

For the authoritative markdown map, read `governance/documentation_architecture.md`.

## Startup entrypoints

| Scenario | Start here |
|----------|-----------|
| Zero-context warp development handoff | `bootstrap/BOOTSTRAP.md` |
| Resume an interrupted session | `RESUME.md` |
| Cold start on a new machine | `new_machine_prompt.md` |

Additional references: `governance/manager_protocol.md`, `governance/control_plane_playbook.md`, `governance/worker_launch_playbook.md`.

### Minimum files for live session operator

These files give a returning operator the full current state picture:

1. `checkpoints/manager/latest.md`
2. `reports/manager_report.md`
3. `state/backlog.yaml`
4. `state/gates.yaml`
5. `state/heartbeats.yaml`
6. `state/edit_locks.yaml`
7. `state/team_mailbox.yaml`
8. `state/agent_runtime.yaml`
9. `status/agents/`
10. `checkpoints/agents/`
11. `strategy/integration_plan.md`
12. `strategy/baseline_trace.md`

For a zero-context bootstrap agent, use the read order in `bootstrap/BOOTSTRAP.md` instead.

## Commands

All commands run from the `warp` repo root.

### Core operations

| Command | Effect |
|---------|--------|
| `python runtime/control_plane.py serve` | Start dashboard only (detaches by default) |
| `python runtime/control_plane.py up` | Start dashboard and launch all configured workers |
| `python runtime/control_plane.py stop-agents` | Stop workers, keep dashboard running |
| `python runtime/control_plane.py silent` | Close dashboard listener, keep workers running |
| `python runtime/control_plane.py stop-all` | Stop both listener and worker fleet |

Default listener: `0.0.0.0:8233`.

### Optional flags

Add only when the default path is not enough:

- `--open-browser`: open dashboard in browser after startup
- `--foreground`: keep `serve` attached to current shell
- `--bootstrap`: force template-backed cold-start mode
- `--host <addr>`: bind to specific address
- `--port <port>`: use different port
- `--config <path>`: load non-default config file
- `--log-file <path>`: change detached log path
- `--detach`: force detach on non-`serve` command

### Compatibility fallback

On a machine without the full CUDA stack:

`uv run --no-project --with 'PyYAML>=6.0.2' python runtime/control_plane.py serve`

### Stop behavior details

- `silent`: closes HTTP listener, updates session state, leaves workers alone. Use when reducing exposure without interrupting work.
- `stop-all`: terminates worker process groups (not just parent PIDs), waits for listener port to be released before returning.
- `stop-listener`: compatibility alias for `silent`.
- The runtime records per-port session state, so `--port 8233` targets the correct instance.

### Resume after stop-agents

1. Click `Launch` in dashboard to restart workers with current config.
2. Click `Restart` for a full stop-and-relaunch cycle.
3. Re-run `up` if the control plane itself is not running.

## Deployment assumption

Target: Linux with Hopper or Blackwell GPUs and a fully provisioned SonicMoE runtime environment.

- Expected hardware: H100, H200, B200, or GB200
- Expected environment: CUDA, PyTorch, Triton, and SonicMoE dependencies already installed
- Worker `test_command` values run immediately without extra setup

For Blackwell kernels on B200/GB200, set `USE_QUACK_GEMM=1` in the worker environment.

## Frontend architecture

Dashboard is served as compiled static assets from `runtime/web/static/`.

- Source: `runtime/web/src/`
- Rebuild after edits: `cd runtime/web && npm install && npm run build`
- UI state managed in React

## Settings workflow

1. Run `serve` to prepare config, or `up` to launch immediately.
2. Open Settings, fill Project (especially `Local Repo Root`) so A0 can derive worktree paths.
3. Confirm Merge Policy and Resource Pools.
4. In Worker Defaults, set only common values you want standardized. Leave advanced defaults blank unless needed.
5. In Worker Config, treat A0 plan as default. Only add overrides for real exceptions.
6. Use `Reset to A0` to clear unnecessary manual values.
7. Validate and save each section, then launch or restart from top bar.

### Config minimum

Set at minimum in `runtime/local_config.yaml`:

- `project.local_repo_root`
- `project.reference_workspace_root` (if needed)
- provider credentials or `auth_mode: session` for session-backed providers like `ducc`
- `project.integration_branch`

A0 derives worker worktree paths under `warp/worktrees/` by default. The template pins the default pool to `ducc_pool` with `ducc` first.

## Collaboration protocol

Warp treats collaboration as durable repository state, not transient provider chat.

- Tasks are claimed, reviewed, reopened, and completed through explicit state transitions
- `state/team_mailbox.yaml` is the provider-agnostic inbox
- A0 Console exposes mailbox peek, composer, and workflow patching (replan, reassign, reopen presets)
- Cleanup readiness tracks active workers, pending reviews, and outstanding locks before team release
- Workers can be shut down individually without collapsing the listener

## Dashboard

Three tabs:

1. **Overview**: agent health, delivery progress, branch merge status
2. **Operations**: commands, validation, provider queue, merge queue, runtime state, heartbeats, backlog, manager report
3. **Settings**: project, pools, merge policy, worker defaults, worker overrides

Top bar: Launch, Restart, Stop Agents, Silent Mode, Stop All, Refresh, Copy Command.

## Operating rules

### Execution topology

Every worker must be recorded in `state/agent_runtime.yaml` before it is counted as active.

### Concurrency

High-conflict control files are single-writer. Claim in `state/edit_locks.yaml` before editing.

### Agent checkpoints

Each worker maintains:
- `status/A*.md` for live status
- `checkpoints/agents/A*.md` for resumable checkpoint

### Heartbeats

Tracked in `state/heartbeats.yaml`: `healthy`, `stale`, `not-started`, `offline`.

The manager must include heartbeat state in every production status report.

### Remote access

If the hostname resolves to IPv6 first, the runtime brings up an IPv4 listener on `0.0.0.0` by default, then adds IPv6 as secondary.

## Rule

No work is considered active unless it is reflected here.
