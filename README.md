# warp control plane

This repository hosts a standalone multi-agent control plane for coordinating delivery work against an external target repository.

Its job is to keep the FP8 program executable as coordinated manager and worker work, not as ad hoc local notes. WARP stands for Workload-aware Agents Routing Protocol, and the control plane owns:

- agent planning and backlog state
- worker launch and stop orchestration
- provider and resource-pool routing
- branch and merge visibility for manager-owned integration
- resumable checkpoints, heartbeats, and runtime status

Default target repository name: `target-repo`

## Structure

- `strategy/`: program intent, scope, and baseline mapping
- `governance/`: operating rules, decisions, and machine policy
- `state/`: live backlog, gates, heartbeats, mailbox, and lock state
- `status/agents/`: live worker status feeds
- `checkpoints/`: resumable manager and worker snapshots
- `experiments/`: experiment registry
- `reports/`: production-facing reporting and delivery artifacts
- `bootstrap/`: low-overhead handoff package for zero-context AI agents continuing warp development

## Documentation Architecture

The markdown system is intentionally split by responsibility:

- `README.md`: shortest reliable operator overview
- `bootstrap/`: low-context AI-agent takeover for continued `warp` development
- `governance/`: stable process law and control-plane design rules
- `strategy/`: current plan and technical baseline mapping
- `state/`, `status/`, `checkpoints/`: live durable control state
- `reports/`: synthesized operational and delivery outputs

For the authoritative markdown map, read `governance/documentation_architecture.md`.

## Minimum files to read

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
11. `governance/experiments/registry.yaml`
12. `strategy/integration_plan.md`
13. `strategy/baseline_trace.md`

## Rule

No work is considered active unless it is reflected here.

## Collaboration protocol

Warp treats collaboration as durable repository state, not transient provider chat.

- tasks can be claimed, reviewed, reopened, and completed through explicit control-plane state transitions
- plan approval is explicit for risky work before implementation proceeds
- `state/team_mailbox.yaml` is the provider-agnostic inbox for worker-to-worker and worker-to-A0 messages
- A0 Console is the operational view over pending approvals, unresolved inbox items, and manager replies
- the Operations tab and A0 Console both expose mailbox peek cards plus a mailbox composer so coordination messages can be read and written directly from the dashboard
- A0 can patch workflow state directly from the control plane to reassign owners, change claim and review posture, and request replans without editing YAML by hand
- pending A0 requests can preload the workflow form with replan, reassign, and reopen presets so manager feedback can be turned into a structured workflow change in one step
- cleanup readiness is explicit: the control plane tracks active workers, pending reviews, and outstanding single-writer locks before the team can be considered safe to release
- workers can be shut down individually from the dashboard without collapsing the full listener session
- once cleanup is ready, A0 can optionally auto-release the listener as part of confirming the cleanup gate

## Startup entrypoints

- zero-context warp-development handoff: `bootstrap/BOOTSTRAP.md`
- cold start on a new machine: `new_machine_prompt.md`
- resume an interrupted session: `RESUME.md`
- manager behavior and interruption law: `governance/manager_protocol.md`
- markdown responsibility map: `governance/documentation_architecture.md`
- control-plane execution checklist: `governance/control_plane_playbook.md`
- launch workers: `governance/worker_launch_playbook.md`
- run integrated frontend and backend: `runtime/control_plane.py`
- current production snapshot: `reports/manager_report.md`

## Agent bootstrap

If a fresh AI agent needs to continue developing `warp` itself with minimal context cost, start from `bootstrap/BOOTSTRAP.md`.

That bootstrap package is distinct from:

- `RESUME.md`, which restores an active control session
- `new_machine_prompt.md`, which rebuilds state on a new machine

The bootstrap folder packages:

- the canonical takeover prompt
- the compact repo map
- the settled workflow invariants that should not be regressed
- the default validation loop for control-plane changes
- the recent decisions that are easiest to accidentally rediscover the hard way

The governance layer now also separates two stable concerns that used to diffuse across multiple docs:

- `governance/manager_protocol.md` for manager objectives, interruption priority, checkpoint-first rules, self-evolution, and planning authority
- `governance/documentation_architecture.md` for markdown responsibility boundaries and anti-noise rules

## Deployment assumption

The default target is a Linux machine with Hopper or Blackwell GPUs and a fully provisioned SonicMoE runtime environment.

- expected hardware: H100, H200, B200, or GB200
- expected environment: CUDA, PyTorch, Triton, and SonicMoE dependencies are already installed and usable from the active shell
- expected behavior: worker `test_command` values can run immediately on the same machine without extra bootstrap steps

If you are validating Blackwell kernels directly on B200 or GB200, set `USE_QUACK_GEMM=1` in the worker environment before launching those jobs.

## Operating modes

Keep the high-frequency path simple:

- `serve`: start the dashboard only
- `up`: start the dashboard and launch all configured workers immediately
- `stop-agents`: stop workers and keep the dashboard running
- `silent`: close only the dashboard listener and keep workers running
- `stop-all`: stop both the listener and the worker fleet

If `runtime/local_config.yaml` is missing, the runtime automatically falls back to `runtime/config_template.yaml` and enters cold-start mode. If you later save a real config from the Settings page, it is written to `runtime/local_config.yaml` automatically.

## Frontend architecture

The dashboard frontend is now served as compiled static assets from `runtime/web/static/`.

- source code lives in `runtime/web/src/`
- the runtime serves `index.html`, `app.js`, and `app.css` directly instead of embedding HTML and JavaScript inside `control_plane.py`
- UI state is managed in React so tabs, top-bar actions, settings editing, and refresh behavior share one predictable state model

When you change the frontend source, rebuild it with:

`cd runtime/web && npm install && npm run build`

The built assets in `runtime/web/static/` are what the Python runtime serves in production.

## Quickstart

### Standalone usage

Use `warp` as an independent repository and point it at the target codebase you want to coordinate.

From the `warp` repo root:

- start only the dashboard: `python3 runtime/control_plane.py serve`
- start dashboard and worker launch flow: `python3 runtime/control_plane.py up`
- stop workers only: `python3 runtime/control_plane.py stop-agents`
- close the listener but keep workers alive: `python3 runtime/control_plane.py silent`
- stop everything: `python3 runtime/control_plane.py stop-all`

If the machine does not already have the control-plane Python dependency installed, use the self-contained launcher form:

- `uv run --no-project --with 'PyYAML>=6.0.2' python runtime/control_plane.py serve`

On first run, `warp` will fall back to `runtime/config_template.yaml` when `runtime/local_config.yaml` is absent. Save a real config from the Settings page, or create `runtime/local_config.yaml` manually, then set at minimum:

- `project.local_repo_root` to the target repository you want `warp` to manage
- any shared reference workspace path you actually need
- provider credentials or session-backed provider settings
- worker worktree paths and branches, if you do not want A0 to derive them

By default, A0 now derives every worker worktree under `warp/worktrees/`, not next to the target repository. For a target named `target-repo`, the derived paths look like `warp/worktrees/target_repo_a1`, `warp/worktrees/target_repo_a2`, and so on.

The checked-in template also pins the default worker pool to `ducc_pool` and prefers `ducc` first. That means the dashboard and config are immediately usable, but worker launch still requires a `ducc` binary to be installed on the machine.

## Common operations

These are the normal operator commands:

- start dashboard only: `python runtime/control_plane.py serve`
- start dashboard and launch workers: `python runtime/control_plane.py up`
- stop workers but keep dashboard up: `python runtime/control_plane.py stop-agents`
- close dashboard but keep workers running: `python runtime/control_plane.py silent`
- stop everything: `python runtime/control_plane.py stop-all`
- run the integration check: `python3 runtime/test_control_plane_integration.py`
- rebuild the frontend after UI edits: `cd runtime/web && npm run build`

## Starting agent work

Use this path when you want A0 to derive as much as possible and keep manual config minimal:

1. Run `serve` if you only want to prepare config, or `up` if you are ready to launch the worker fleet immediately.
2. Open the Settings tab and fill Project first, especially `Local Repo Root`. This lets A0 derive worker worktree paths.
3. Confirm Merge Policy and Resource Pools.
4. In Worker Defaults, touch only the common defaults you truly want to standardize. Leave advanced defaults blank unless your environment really needs a non-standard sync, test, submit, or git identity fallback.
5. In Worker Config, treat the A0 plan as the default execution target. Only fill an override when a worker must diverge from that plan.
6. If a worker or defaults section drifted into unnecessary manual values, use `Reset to A0` to clear the overrides and return to the derived path.
7. Validate and save each section, then launch or restart workers from the top bar.

Settings semantics:

- `A0 plan` means the control plane's derived target state from backlog, runtime state, task policies, and shared defaults.
- `override` means a human-pinned exception that takes precedence over A0 until cleared.
- `Reset to A0` removes those pinned values so derivation can take over again.

### 1. Primary shell commands

Use these first. They match the runtime defaults and cover the normal manager loop:

`python runtime/control_plane.py serve`

`python runtime/control_plane.py up`

`python runtime/control_plane.py stop-agents`

`python runtime/control_plane.py silent`

`python runtime/control_plane.py stop-all`

What these do by default:

- `serve` starts the dashboard only and detaches automatically
- `up` starts the dashboard and launches all configured workers
- `stop-agents` pauses the worker fleet without removing the dashboard
- `silent` removes only the listener and leaves workers alone
- `stop-all` performs the full shutdown path
- the default listener is `0.0.0.0:8233` unless you override it

### 2. Prepare real multi-agent execution

Fill `runtime/local_config.yaml` from the Settings page or by editing YAML directly. At minimum, replace placeholder values for:

- `project.local_repo_root`
- `project.reference_workspace_root` if your workflow depends on a shared reference repo or baseline workspace
- resource pool credentials or credential env vars
- session-backed providers such as `ducc` only need `providers.<name>.auth_mode: session` plus a working binary on `PATH`; no api key is required
- `worker_defaults.environment_path`
- every worker `worktree_path`

Task-aware defaults now come from explicit `task_policies` plus backlog `task_type` metadata, so you should only set `worker_defaults.test_command` when you want to override A0's policy-driven selection for every worker.

Then use the settings workflow in this order:

1. set Project and Merge Policy once
2. tune Resource Pools in the horizontal pool strip
3. fill only the common `worker_defaults` you really want shared across all workers, mainly pool routing and environment defaults
4. open `advanced defaults` only when you need non-standard shared sync, test, submit, or git identity behavior
5. add workers with only agent identity and exceptional routing overrides that differ from the defaults or A0 plan
6. open the advanced override panel for a worker only when that worker truly needs a different task, branch, worktree, environment, test, submit, or git identity path
7. use `Reset to A0` whenever a worker or defaults block should fall back to derived values again

Also set `project.integration_branch`, optional `project.manager_git_identity`, and any per-worker `git_identity` overrides you want the runtime to apply inside worker worktrees.

### 3. Optional launch flags

Add parameters only when the default path is not enough:

- `--open-browser`: open the dashboard automatically after startup
- `--foreground`: keep `serve` attached to the current shell instead of detaching
- `--bootstrap`: force template-backed cold-start mode
- `--host 127.0.0.1`: bind to a specific address instead of the default `0.0.0.0`
- `--port 9000`: move the listener to a different port
- `--config <path>`: load a non-default runtime config file
- `--log-file <path>`: change the detached log path
- `--detach`: force detach on a non-`serve` command

Examples:

`python runtime/control_plane.py serve --open-browser`

`python runtime/control_plane.py up --open-browser`

`python runtime/control_plane.py serve --bootstrap --foreground`

### 4. Resume paused work

After `stop-agents`, use one of these paths:

1. Click `Launch` to start workers again with the current config.
2. Click `Restart` if you want a full stop-and-relaunch cycle.
3. Re-run `python runtime/control_plane.py up` if the control plane itself is not running.

## Launch parameters

Use the short form by default:

- `serve` opens the control plane only
- `up` opens the control plane and launches workers

Add these only when needed:

- `--open-browser` opens the dashboard automatically
- `--foreground` disables the default fire-and-forget behavior of `serve`
- `--bootstrap` forces template-backed cold-start mode
- `--port 9000` to change the dashboard port
- `--host 127.0.0.1` or another address if you do not want the default `0.0.0.0`
- `--detach` only if you want to force detach on a non-serve command
- `--log-file <path>` to change the detached log path
- `--config <path>` only if you do not want the default `runtime/local_config.yaml`

## Stop commands

Use these shell commands when you want to control a running detached session from the same machine. The runtime now records per-port session state, so `--port 8233` targets the listener you actually care about even if another control-plane instance was started elsewhere.

- stop worker agents only: `python runtime/control_plane.py stop-agents`
- enter silent mode by closing the dashboard listener only: `python runtime/control_plane.py silent`
- compatibility alias for silent mode: `python runtime/control_plane.py stop-listener`
- stop both the dashboard listener and all worker agents: `python runtime/control_plane.py stop-all`

`silent` is the soft stop path:

- it closes the HTTP listener but leaves worker processes running
- it updates session state so later stop commands still know the listener is already gone
- it is the right option when you want to reduce exposure to scans without interrupting work

`stop-all` is the hard stop path:

- it terminates worker process groups, not just parent PIDs
- it waits for the target listener port to be released before reporting success
- when the dashboard is running on `8233`, the command verifies that `8233` is actually clean before it returns

### Fire-and-forget mode

`python runtime/control_plane.py serve` is already the default detached path. It binds `0.0.0.0:8233` unless you override host or port. Use `--foreground` only when you want logs in the current shell.

The detached process writes combined stdout and stderr to `runtime/control_plane.log` by default. You can override that path with `--log-file`.

If your working foreground command uses `uv run ... python`, keep that same launcher and append `--detach` at the end instead of switching interpreters.

### Compatibility fallback

If you need to run the control plane from a lightweight manager machine that does not carry the full CUDA stack, keep the same command shape and only swap the launcher:

`uv run --no-project --with 'PyYAML>=6.0.2' python runtime/control_plane.py serve`

That same standalone path supports the same optional flags, for example:

`uv run --no-project --with 'PyYAML>=6.0.2' python runtime/control_plane.py serve --bootstrap --open-browser`

### Remote access note

If your deployment hostname resolves to IPv6 first, an IPv6-only listener can still look like `ERR_CONNECTION_REFUSED` from the browser when your clients reach the node over IPv4. The runtime now brings up an IPv4 listener on `0.0.0.0` by default, then adds IPv6 as a secondary listener when possible.

## Dashboard capabilities

The local webpage now provides:

- a compact top bar for launch, restart, stop agents, stop all, refresh, and command copy actions
- a `Silent Mode` action that closes the listener without stopping workers
- launch modes for the default initial provider, explicit provider/model pinning, or elastic provider selection
- an `Overview` page that shows agent dashboards, overall delivery progress, and branch merge status at a glance
- an `Operations` page for commands, validation, provider queue, merge queue, runtime state, heartbeats, backlog, and manager report
- a `Settings` page with responsive editable project, pool, merge-policy, worker-default, and worker-override forms
- a horizontal resource-pool strip so pool routing stays visible without a long vertical stack
- a `worker_defaults` layer that fills common environment, sync, test, submit, and git identity values once for the whole fleet
- lean worker cards that focus on identity and branch routing, with advanced overrides hidden until needed
- strict config validation before save, including path checks via `ls` and host checks via `ping`
- provider priority queue with runtime connection-quality and work-quality scoring
- per-worker git commit identities that are applied inside each worker worktree before launch
- a manager-owned merge queue that tracks which worker branch should be integrated into the target branch
- React-managed UI state so page navigation and actions stay interactive under refresh and cold-start edits

## Real usage pattern

For actual SonicMoE FP8 multi-agent delivery, the normal manager loop is:

1. bring the control plane up with `serve`
2. verify Settings and validation output are clean, starting with shared `worker_defaults`
3. use `Initial Provider` for the first fleet launch so the default ducc-backed pool comes up immediately, then switch to `Selected Model` or `Elastic` as needed before pressing `Launch`
4. monitor agent health, backlog progress, and branch merge status from `Overview`
5. inspect provider routing, runtime topology, and heartbeats in `Operations`
6. press `Stop Agents` or run `stop-agents` when you want to pause the worker fleet without losing dashboard state
7. press `Stop All` or run `stop-all --port 8233` when you need the listener port and every worker process fully released
8. let A0 merge finished worker branches into `project.integration_branch`

## Interaction model

The dashboard is intentionally simple:

1. start on `Overview` to judge agent health, overall delivery progress, and which worker branches are waiting for manager merge review
2. move to `Operations` when you need runtime inspection, launch commands, validation, or provider scheduling detail
3. move to `Settings` when you need to edit API keys, provider assignments, Paddle paths, shared worker defaults, or a small number of per-worker overrides
4. let A0 own merge timing and final integration into `project.integration_branch`
5. use `Launch`, `Restart`, `Stop Agents`, or `Stop All` from the top bar for normal operations
6. copy the `serve` or `up` command when you need terminal control

## Execution topology rule

Every real worker must be recorded in `state/agent_runtime.yaml` before it is counted as active.

The runtime record must capture at least:

- repository name
- resource pool
- provider
- model
- worktree path
- branch name
- merge target branch
- environment path or `uv` environment root
- test command
- submit path back to the integration branch

## Concurrency rule

High-conflict control files are single-writer files. An agent must claim them in `state/edit_locks.yaml` before editing them.

## Agent checkpoint rule

Each worker agent must maintain both:

- `status/A*.md` for current live status
- `checkpoints/agents/A*.md` for resumable checkpoint state

## Heartbeat rule

Agent liveness is tracked in `state/heartbeats.yaml`.

- `healthy`: agent heartbeat is within the expected window
- `stale`: agent previously reported but missed the expected window
- `not-started`: agent has no runtime heartbeat yet
- `offline`: agent was intentionally stopped or released

The manager must include heartbeat state in every production status report.