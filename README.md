# WARP Control Plane

**Workload-Aware Agents Routing Protocol** — a multi-agent orchestration system for coordinating parallel delivery work against an external target repository.

WARP manages agent planning, worker lifecycle, provider routing, dependency-aware scheduling, branch integration, and runtime observability through a single control plane with a web dashboard.

## Quick Start

```bash
# Dashboard only (detaches by default)
python runtime/control_plane.py serve

# Dashboard + launch dependency-ready workers
python runtime/control_plane.py up
```

Default listener: `0.0.0.0:8233`

## Architecture

```
A0 (Manager)
├── A1  Protocol freeze       ─┐
├── A6  Baseline trace         │  G0: no dependencies
│                               │
├── A2  Hopper audit      ← A1 │
├── A3  Blackwell audit   ← A1 │  G1-G3: depend on protocol
├── A7  Benchmark         ← A1 │
│                               │
├── A4  Reference path  ← A1,A6│  G1: depend on protocol + baseline
├── A5  Baseline tests  ← A4,A6│  G4: depend on reference + baseline
└── A4-002 Training step← A4,A5│  G5: depend on reference + tests
```

Workers launch only when upstream dependencies are satisfied. The monitor loop auto-launches newly-runnable agents every 5 seconds.

## Repository Layout

| Directory | Purpose |
|-----------|---------|
| `runtime/` | Control plane source, config, dashboard frontend |
| `strategy/` | Program intent, scope, baseline mapping |
| `governance/` | Operating rules, decisions, machine policy |
| `state/` | Live backlog, gates, heartbeats, mailbox, locks |
| `status/agents/` | Per-worker status feeds |
| `checkpoints/` | Resumable manager and worker snapshots |
| `reports/` | Delivery artifacts and manager reports |
| `bootstrap/` | Zero-context handoff package for new sessions |

## Commands

### Lifecycle

| Command | Effect |
|---------|--------|
| `serve` | Start dashboard, no workers |
| `up` | Start dashboard + launch workers |
| `stop-agents` | Stop workers, keep dashboard |
| `silent` | Close dashboard, keep workers |
| `stop-all` | Stop everything |

### Flags

| Flag | Purpose |
|------|---------|
| `--foreground` | Keep `serve` attached to shell |
| `--open-browser` | Auto-open dashboard |
| `--bootstrap` | Force cold-start mode |
| `--host <addr>` | Bind address |
| `--port <port>` | Listen port |
| `--config <path>` | Non-default config file |

### Minimal Environment Fallback

```bash
uv run --no-project --with 'PyYAML>=6.0.2' python runtime/control_plane.py serve
```

## Dashboard

### Toolbar

Launch | Restart | **Soft Stop** | Stop Agents | Silent Mode | Stop All | Refresh

- **Soft Stop**: saves each agent's progress to `checkpoints/agents/` before stopping — safe for session handoff
- **Stop Agents**: immediate SIGTERM, no checkpoint

### Tabs

| Tab | Content |
|-----|---------|
| **Overview** | Task DAG, agent peek (real-time output), progress metrics, branch merge status, agent health cards |
| **Operations** | Provider queue, processes, backlog, gates, runtime topology, heartbeats, mailbox, manager report |
| **Settings** | Project paths, resource pools, merge policy, worker defaults, per-worker overrides |

### A0 Console

Pop-out window for manager approvals, unblock decisions, resume notes, and workflow patching. Accessible from Overview or toolbar.

## Configuration

Minimum in `runtime/local_config.yaml`:

```yaml
project:
  local_repo_root: /path/to/target-repo
  integration_branch: main

providers:
  ducc:
    auth_mode: session
```

A0 derives worktree paths, branches, and test commands automatically from backlog state. Use Settings to override only when needed; `Reset to A0` clears manual pins.

### Per-Agent Identity

Each worker commits under its own name:

| Agent | Git Name | Email |
|-------|----------|-------|
| A0 | A0-Manager | panzhaowu@baidu.com |
| A1 | A1-Protocol | panzhaowu@baidu.com |
| A2 | A2-Hopper | panzhaowu@baidu.com |
| ... | A{n}-{Role} | panzhaowu@baidu.com |

## Key Concepts

| Term | Definition |
|------|-----------|
| **A0 Plan** | Derived target state from backlog + runtime + task policies. Default execution target for all workers. |
| **Override** | Human-pinned exception over A0 plan. `Reset to A0` removes it. |
| **Soft Stop** | Checkpoint-then-stop: launches a brief session per agent to save progress before shutdown. |
| **Task DAG** | Dependency graph on Overview tab. Nodes colored by status: green=done, blue=active, amber=pending, gray=blocked. |
| **Peek** | Real-time sliding window of each agent's parsed output (from ducc stream-json). |

## Operational State

### Session Resume

| Scenario | Start here |
|----------|-----------|
| Zero-context handoff | `bootstrap/BOOTSTRAP.md` |
| Resume interrupted session | `RESUME.md` |
| Cold start on new machine | `new_machine_prompt.md` |

### Minimum Files for Live Session

1. `checkpoints/manager/latest.md`
2. `reports/manager_report.md`
3. `state/backlog.yaml` + `state/gates.yaml`
4. `state/heartbeats.yaml` + `state/agent_runtime.yaml`
5. `state/team_mailbox.yaml` + `state/edit_locks.yaml`
6. `status/agents/` + `checkpoints/agents/`
7. `strategy/integration_plan.md` + `strategy/baseline_trace.md`

### Heartbeats

States: `healthy` | `stale` | `not-started` | `offline`. Tracked in `state/heartbeats.yaml`.

### Concurrency

High-conflict control files are single-writer. Claim in `state/edit_locks.yaml` before editing.

## Deployment

Target: Linux with Hopper or Blackwell GPUs and a provisioned SonicMoE environment.

- Hardware: H100, H200, B200, or GB200
- Stack: CUDA + PyTorch + Triton + SonicMoE
- Blackwell kernels: set `USE_QUACK_GEMM=1` in worker environment

### Frontend Rebuild

```bash
cd runtime/web && npm install && npm run build
```

Source in `runtime/web/src/`, static assets served from `runtime/web/static/`.
