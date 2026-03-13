# WARP

**Workload-Aware Agents Routing Protocol** — a protocol and runtime for orchestrating parallel AI agent teams against any target repository.

WARP defines how a manager agent (A0) plans work, schedules dependency-aware tasks, routes workers to providers, manages branch isolation, and observes progress — all through a single control plane with a live dashboard.

It is **project-agnostic**: point it at any repo, define a backlog, and WARP handles the rest.

---

## For Human

### Quick Start

```bash
# Dashboard only (detaches by default)
python runtime/control_plane.py serve

# Dashboard + launch dependency-ready workers
python runtime/control_plane.py up
```

Default listener: `0.0.0.0:8233`

### Core Capabilities

| Capability | Description |
|-----------|-------------|
| **Dependency-aware scheduling** | Workers launch only when upstream tasks are done; monitor loop auto-launches newly-runnable agents every 5 s |
| **Provider routing** | Pluggable provider backends (ducc, claude, API-key services) with priority scoring and resource pools |
| **Branch isolation** | Each worker gets its own worktree and branch; merge queue handles integration |
| **Soft stop** | Checkpoint-then-stop: agents save progress to `checkpoints/agents/` before shutdown, safe for session handoff |
| **Real-time observability** | Task DAG, agent peek (live output), heartbeats, team mailbox, manager report |
| **Per-agent identity** | Each worker commits under its own git name (`A1-Protocol`, `A2-Auditor`, …) |

### Commands

| Command | Effect |
|---------|--------|
| `serve` | Start dashboard, no workers |
| `up` | Dashboard + launch workers |
| `stop-agents` | SIGTERM workers, keep dashboard |
| `soft-stop` | Checkpoint + stop workers |
| `silent` | Close dashboard, keep workers |
| `stop-all` | Stop everything |

Flags: `--foreground`, `--open-browser`, `--bootstrap`, `--host`, `--port`, `--config`

### Dashboard

**Toolbar**: Launch · Restart · Soft Stop · Stop Agents · Silent Mode · Stop All · Refresh

| Tab | Content |
|-----|---------|
| **Overview** | Task DAG, agent peek, progress metrics, merge status, health cards |
| **Operations** | Provider queue, processes, backlog, gates, topology, heartbeats, mailbox, manager report |
| **Settings** | Project paths, resource pools, merge policy, worker defaults, per-worker overrides |

**A0 Console**: pop-out window for manager approvals, unblock decisions, and workflow patching.

### Configuration

Minimum `runtime/local_config.yaml`:

```yaml
project:
  local_repo_root: /path/to/target-repo
  integration_branch: main

providers:
  ducc:
    auth_mode: session
```

A0 derives worktree paths, branches, and test commands from backlog state. Use the Settings tab to override; `Reset to A0` clears manual pins.

### Repository Layout

| Directory | Purpose |
|-----------|---------|
| `runtime/` | Control plane, config, dashboard frontend |
| `strategy/` | Program intent, scope, baseline mapping |
| `governance/` | Operating rules, decisions, machine policy |
| `state/` | Backlog, gates, heartbeats, mailbox, locks |
| `status/agents/` | Per-worker status feeds |
| `checkpoints/` | Resumable manager and worker snapshots |
| `reports/` | Delivery artifacts and manager reports |
| `bootstrap/` | Zero-context handoff package for new agent sessions |

### Key Concepts

| Term | Definition |
|------|-----------|
| **A0 Plan** | Derived target state from backlog + runtime + policies. Default execution target for all workers. |
| **Override** | Human-pinned exception over A0 plan. `Reset to A0` removes it. |
| **Soft Stop** | Checkpoint-then-stop: each agent saves progress before shutdown. |
| **Task DAG** | Dependency graph (green=done, blue=active, amber=pending, gray=blocked). |
| **Peek** | Real-time sliding window of each agent's parsed output. |
| **Gate** | Synchronization barrier. Tasks behind a gate wait until it opens. |

### Frontend Rebuild

```bash
cd runtime/web && npm install && npm run build
```

### Example Deployment

The initial WARP deployment targets SonicMoE FP8 kernel delivery on Linux with Hopper / Blackwell GPUs. This is one example — WARP itself has no hardware dependency.

---

## For Agent

If you are an AI agent bootstrapping into this repository, **do not read the entire repo**. Follow the minimal-cost path below.

### Bootstrap (zero-context takeover)

Start with [`bootstrap/BOOTSTRAP.md`](bootstrap/BOOTSTRAP.md). It defines:

- The minimal read order (governance → bootstrap files → README → governance protocols)
- A canonical bootstrap prompt you can paste into a fresh session
- Audit requirements and expected finish quality

### Resume (interrupted session)

Start with [`RESUME.md`](RESUME.md). It defines the read order for restoring live state:

1. `checkpoints/manager/latest.md`
2. `reports/manager_report.md`
3. `state/backlog.yaml` + `state/gates.yaml`
4. `state/heartbeats.yaml` + `state/agent_runtime.yaml`
5. `state/team_mailbox.yaml` + `state/edit_locks.yaml`
6. `status/agents/` + `checkpoints/agents/`
7. `strategy/integration_plan.md` + `strategy/baseline_trace.md`

### New Machine

Start with `new_machine_prompt.md` for cold-start recovery.

### Rules

- Prefer the simplest operator workflow.
- Do not reintroduce manual YAML-first setup when A0 can derive the same data.
- Keep docs, runtime, frontend, and tests aligned in the same change.
- Rebuild `runtime/web/static` after any frontend source edit.
- Single-writer discipline: claim in `state/edit_locks.yaml` before editing high-conflict files.
