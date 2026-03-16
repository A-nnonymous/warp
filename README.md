# WARP

English: `README.md` | 中文：[`README_CN.md`](README_CN.md)

**Workload-Aware Agents Routing Protocol** — a protocol and runtime for orchestrating parallel AI agent teams against any target repository.

WARP defines how a manager agent (A0) plans work, schedules dependency-aware tasks, routes workers to providers, manages branch isolation, and observes progress — all through a single control plane with a live dashboard.

It is **project-agnostic**: point it at any repo, define a backlog, and WARP handles the rest.

---

## For Human

### First Principle

WARP is an **agent-autonomous** framework.

That means:

- **A0 is the primary operator**
- **A0 may make decisions, revise plans, and reshape workflow on its own**
- the **control plane is mainly for human observation and exception handling**
- humans step in when A0 hits ambiguity, risk, or a decision it cannot safely resolve alone

Do not think of the dashboard as a place where a human must manually drive every step.
Think of it as a place where a human watches the system, audits durable state, and intervenes only when needed.

### Quick Start

```bash
# Dashboard only (detaches by default)
python runtime/control_plane.py serve

# Dashboard + launch dependency-ready workers
python runtime/control_plane.py up
```

Default listener: `0.0.0.0:8233`

### Short Decision Table

| If you want to... | Use this | Default stance |
|-------------------|----------|----------------|
| See what A0 and workers are doing | **Control plane dashboard** | Observe first |
| Approve, reject, unblock, or steer a durable workflow decision | **A0 Console** | Human intervenes only when needed |
| Do dense coding, debugging, or design discussion | **External Copilot** | Keep high-bandwidth work outside |
| Change task truth such as owner, status, dependencies, or plan state | **Workflow update** | Write durable facts back |
| Leave durable coordination context for others | **Mailbox** | Notify only when it affects others |
| Pause or hand off unfinished work | **Checkpoint** | Preserve resumability |

### Recommended Human Workflow

Human-first rule: let A0 run the workflow by default, treat the control plane as the durable source of truth, and treat any external Copilot session as a high-bandwidth scratchpad for engineering work.

Recommended default loop:

1. Use the dashboard to understand what A0 is already doing.
2. Let A0 continue autonomously unless there is ambiguity, risk, or a blocked decision.
3. Use **A0 Console** only for approvals, unblock decisions, owner changes, and workflow steering that need durable manager involvement.
4. Use an external Copilot session for dense implementation, debugging, or design discussion.
5. Before ending that external session, write durable state back into WARP through workflow updates, mailbox messages, or checkpoints.

This keeps the system easy to steer without forcing every long engineering conversation into the dashboard UI, and without turning the human into A0's manual replacement.

### Which Surface To Use

| Situation | Best Surface | Why |
|-----------|--------------|-----|
| Approve / reject a plan | **A0 Console** | This is a manager decision and should stay visible to A0 and future sessions |
| Unblock a worker or give resume guidance | **A0 Console** | The instruction should become durable workflow state |
| Change owner, claim state, gate, plan state, or task status | **Workflow update in control plane** | These are canonical execution facts |
| Cross-worker coordination or heads-up notes | **Team mailbox** | Other workers and future sessions can see it |
| Large code edit, debugging session, or design exploration | **External Copilot** | Better bandwidth, iteration speed, and conversational ergonomics |
| End of session, handoff, or likely interruption | **Checkpoint + optional mailbox/workflow write-back** | Prevents hidden context loss |

### Lifecycle And Persistence

The intended operating model is asymmetric:

- **A0 + control plane** should be long-lived.
- **External Copilot sessions** should be short-lived and replaceable.

In practice:

- keep A0 and the dashboard running as the team's durable operating memory
- open external Copilot sessions per task, per incident, or per design thread
- never assume that an external chat transcript is the system of record
- before leaving an external session, push back the minimum durable facts that another human or agent would need

Good durable write-backs are:

- a workflow update when task state changed
- a mailbox message when another worker or A0 needs to know something
- a checkpoint when the task has partially completed but is not done

### When A Checkpoint Is Required

Require a worker checkpoint when any of these are true:

- the session is ending
- a task will be handed to another agent or resumed later
- meaningful progress was made but final integration is not done
- the current state includes non-obvious findings, blockers, or next steps that would be expensive to rediscover

The checkpoint should make the next session cheap, not exhaustive.

### Mailbox vs Workflow Update

Use **workflow update** when the task record itself changed:

- owner
- claim state
- task status
- plan state
- dependencies
- manager note

Use **mailbox** when you need to communicate durable context without changing the task record itself:

- handoff notes
- blocker notifications
- coordination requests
- review pings
- design questions

If both happened, do both: update the workflow first, then send the mailbox note that explains the coordination impact.

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

**A0 Console**: pop-out window for manager approvals, unblock decisions, and workflow patching. Use it for durable manager actions, not for every long engineering conversation.

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
| `runtime/` | Control plane, config, dashboard frontend, and generated runtime artifacts under `runtime/generated/` |
| `tests/` | Isolated Python test suite for control plane and services |
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
source ~/.bashrc && cd runtime/web && npm install && npm run build
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
