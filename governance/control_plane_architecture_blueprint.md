# Control Plane Architecture Blueprint

## Purpose

This document is the architectural blueprint and implementation todo for the next stage of `warp` evolution.

It is written against the post-modularized control plane on the current `main` branch, where the legacy monolithic `runtime/control_plane.py` has already been split into `runtime/cp/` backend modules and `runtime/web/src/` frontend modules.

This file is intentionally both:

- a **professional architecture blueprint**
- an **actionable todo list**

The goal is to move `warp` from a modularized control-plane prototype into a durable, testable, service-grade control-plane product.

---

## Executive Summary

`warp` has already completed the first major restructuring step:

- backend modularization into `runtime/cp/`
- frontend modularization into `runtime/web/src/`
- explicit CLI entrypoints for serve/up/stop paths
- documented code indexes for backend and frontend

That means the next priority is **not** more file splitting for its own sake.

The next priority is to establish a stronger architectural center:

1. **contracts** — one canonical source of truth for core runtime and API structures
2. **stores** — explicit durable-state access layer instead of ad hoc YAML-coupled state logic
3. **domain services** — stable planning, routing, patching, cleanup, and dashboard logic outside mixins
4. **service-grade surfaces** — CLI, HTTP, installability, diagnostics, and long-running runtime behavior
5. **test boundaries** — contracts, stores, planning, routing, cleanup, and dashboard assembly as first-class tested seams

The recommended end state is:

> **Kernel + Stores + Domain Services + API/CLI Surfaces + Web Console**

---

## Current-State Diagnosis

### What is already good

The current branch already contains meaningful architectural progress.

#### Backend

The backend is now decomposed into domain-oriented mixins and support modules:

- `config_mixin.py`
- `backlog_mixin.py`
- `mailbox_mixin.py`
- `routing_mixin.py`
- `context_mixin.py`
- `provider_mixin.py`
- `launch_mixin.py`
- `state_mixin.py`
- `dashboard_mixin.py`
- `api_mixin.py`
- `cli.py`
- `constants.py`
- `network.py`
- `telemetry.py`
- `utils.py`
- `markdown.py`

This is already a major improvement over the previous single-file design.

#### Frontend

The dashboard is also decomposed into:

- tabs (`OverviewTab`, `OperationsTab`, `SettingsTab`)
- focused components (`A0ConsoleView`, `AgentPeekPanel`, cards)
- derivation helpers (`lib/config.ts`, `lib/data.ts`, `lib/workflow.ts`, `lib/utils.ts`)

This means `warp` is already beyond the "prototype in one file" stage.

---

### What is still structurally weak

Despite the modularization, the architecture is not yet fully settled.

#### 1. No true contracts layer

System truth still lives across multiple places at once:

- YAML files in `state/`
- mixin normalization and patch logic
- frontend `types.ts`
- dashboard/API payload dict assembly

This increases drift risk and weakens testability.

#### 2. No real stores layer

State files exist, but durable state access is still mixed into business logic.

The system has state files, but not yet a proper state-access architecture.

#### 3. Mixins are split, but core logic is still service-centric

The current split is good, but many business rules are still living directly inside mixin methods on top of a large shared `ControlPlaneService` object.

This means the system is modularized, but not yet deeply modeled.

#### 4. CLI exists, but product surfaces are incomplete

The current CLI already supports:

- `serve`
- `up`
- `silent`
- `stop-agents`
- `stop-listener`
- `stop-all`

But `warp` still lacks a full control-plane product surface including:

- scaffold/bootstrap command
- doctor/diagnostics command
- stronger validate/status paths
- service installation support
- cleaner control-runtime lifecycle interfaces

#### 5. Test boundaries are still under-defined

The repository now has better code structure, but its stable behavior seams are not yet fully formalized as first-class test layers.

---

## Architectural Goal

The target architecture should be a five-layer system.

---

## Layer 1 — Kernel

The kernel owns stable business rules and state-machine semantics.

It should define:

- task workflow semantics
- heartbeat semantics
- worker-plan derivation semantics
- provider/pool recommendation semantics
- cleanup readiness semantics
- mailbox semantics
- merge queue semantics
- config derivation semantics

### Kernel properties

- Python-first
- minimal IO awareness
- no HTTP awareness
- no React awareness
- highly testable
- stable over time

---

## Layer 2 — Stores

Stores own durable state access and normalization.

They should mediate access to:

- backlog state
- heartbeat state
- runtime worker state
- mailbox state
- lock state
- manager console state
- provider stats state

### Stores properties

- hide file-format details from business logic
- normalize raw data into stable contract shapes
- support patch/update semantics
- remain replaceable if storage moves beyond YAML later

---

## Layer 3 — Domain Services

Domain services combine contracts and stores into reusable behavior.

Examples:

- task policy resolver
- worker plan resolver
- provider scoring service
- workflow patch service
- cleanup evaluator
- dashboard assembly service
- report service
- prompt assembly service
- worker runtime service

### Domain services properties

- domain-rich
- reusable across CLI/API/background runtime
- independent from presentation concerns
- easier to test than giant service methods

---

## Layer 4 — Surfaces

Surfaces are external entrypoints only.

These include:

- HTTP API
- CLI
- detached runtime process management
- future local control interfaces

### Surface properties

- thin
- validation and argument parsing only
- delegate to domain services
- not responsible for core logic

---

## Layer 5 — Console

The web console is the presentation layer.

It should:

- consume stable API models
- use frontend view-model derivation where necessary
- remain isolated from YAML/storage semantics
- remain isolated from provider/runtime implementation details

---

## Target Repository Shape

This is the recommended target shape for the control-plane runtime package.

```text
runtime/
├── control_plane.py
├── cp/
│   ├── __init__.py
│   ├── app.py
│   ├── cli.py
│   ├── api.py
│   ├── contracts.py
│   ├── api_models.py
│   ├── constants.py
│   ├── stores/
│   │   ├── backlog_store.py
│   │   ├── heartbeat_store.py
│   │   ├── runtime_store.py
│   │   ├── mailbox_store.py
│   │   ├── lock_store.py
│   │   ├── manager_console_store.py
│   │   └── provider_stats_store.py
│   ├── domain/
│   │   ├── task_policy.py
│   │   ├── worker_plan.py
│   │   ├── provider_scoring.py
│   │   ├── workflow_patch.py
│   │   ├── cleanup.py
│   │   ├── merge_queue.py
│   │   └── mailbox.py
│   ├── services/
│   │   ├── config_service.py
│   │   ├── prompt_service.py
│   │   ├── launch_service.py
│   │   ├── worker_service.py
│   │   ├── dashboard_service.py
│   │   └── report_service.py
│   ├── providers/
│   │   ├── base.py
│   │   ├── copilot.py
│   │   ├── claude_code.py
│   │   ├── ducc.py
│   │   └── opencode.py
│   ├── runtime/
│   │   ├── paths.py
│   │   ├── session.py
│   │   ├── process.py
│   │   ├── worktree.py
│   │   └── telemetry.py
│   ├── prompting/
│   │   ├── context.py
│   │   ├── render.py
│   │   └── transports.py
│   └── utils/
│       ├── yaml_io.py
│       ├── shell.py
│       ├── text.py
│       └── markdown.py
└── web/
    ├── src/
    └── static/
```

This does **not** need to be implemented all at once. It is the directional architecture.

---

## Blueprint by Subsystem

## 1. Contracts Layer Blueprint

### Objective

Create one canonical schema layer for control-plane structures.

### Proposed file

- `runtime/cp/contracts.py`

### It should define

#### Core state entities

- `BacklogItem`
- `BacklogState`
- `GateItem`
- `HeartbeatAgent`
- `RuntimeWorkerEntry`
- `ProcessSnapshot`
- `ResolvedWorkerPlan`
- `ProviderQueueItem`
- `MergeQueueItem`
- `TeamMailboxMessage`
- `TeamMailboxState`
- `CleanupWorkerState`
- `CleanupState`
- `ManagerConsoleState`

#### Config entities

- `ProjectConfig`
- `ProviderConfig`
- `ResourcePoolConfig`
- `WorkerDefaultsConfig`
- `WorkerConfig`
- `ConfigShape`

#### Enums / state constants

- backlog statuses
- claim states
- plan states
- mailbox ack states
- launch strategies
- provider auth modes

### Design requirement

Every stable API payload should map back to one or more canonical contract objects.

---

## 2. Store Layer Blueprint

### Objective

Separate state persistence from business semantics.

### Proposed store modules

- `stores/backlog_store.py`
- `stores/heartbeat_store.py`
- `stores/runtime_store.py`
- `stores/mailbox_store.py`
- `stores/lock_store.py`
- `stores/provider_stats_store.py`
- `stores/manager_console_store.py`

### Responsibilities

#### backlog_store

- load backlog state
- normalize backlog items
- update/persist workflow state
- item lookup and patching support

#### heartbeat_store

- load/persist heartbeats
- normalize heartbeat entries
- stale/offline semantics support

#### runtime_store

- load/persist runtime worker state
- process snapshot support
- session worker state persistence

#### mailbox_store

- load/persist mailbox state
- append / acknowledge / resolve message records

#### lock_store

- load/persist edit locks
- ownership update/release semantics

#### provider_stats_store

- load/persist provider probe and usage stats

#### manager_console_store

- load/persist A0 console state and user messages

### Design requirement

Stores may know YAML and file paths.

Domain logic should not.

---

## 3. Domain Layer Blueprint

### Objective

Move the system's real business logic out of mixin methods and into reusable domain objects.

### Proposed domain modules

- `domain/task_policy.py`
- `domain/worker_plan.py`
- `domain/provider_scoring.py`
- `domain/workflow_patch.py`
- `domain/cleanup.py`
- `domain/merge_queue.py`
- `domain/mailbox.py`

### Responsibilities

#### task_policy.py

- resolve task policy defaults
- apply task type rules
- calculate preferred providers
- derive suggested test commands

#### worker_plan.py

- derive worker plan from config + backlog + task policy
- derive branch naming
- derive worktree path
- merge worker overrides with defaults

#### provider_scoring.py

- rank pools
- resolve launch pool for worker
- evaluate queue order
- score resource-pool candidates

#### workflow_patch.py

- validate state transitions
- apply task action semantics
- summarize patch intent

#### cleanup.py

- compute cleanup blockers
- compute worker readiness
- compute global cleanup readiness

#### merge_queue.py

- compute merge queue items
- summarize worker handoff state
- recommend manager action

#### mailbox.py

- compute catalog summaries
- compute pending counts
- compute A0-specific message views

### Design requirement

The domain layer should be the main test target for control-plane logic.

---

## 4. Service Layer Blueprint

### Objective

Compose stores and domain logic into application capabilities.

### Proposed service modules

- `services/config_service.py`
- `services/prompt_service.py`
- `services/launch_service.py`
- `services/worker_service.py`
- `services/dashboard_service.py`
- `services/report_service.py`

### Responsibilities

#### config_service

- config load/hydration/repair/validation coordination

#### prompt_service

- context selection
- prompt assembly
- transport adaptation by provider mode

#### launch_service

- environment setup
- worktree preparation
- git identity configuration
- worker launch orchestration

#### worker_service

- process lifecycle
- runtime state update
- telemetry aggregation

#### dashboard_service

- build `DashboardState`
- assemble provider queue, merge queue, mailbox, cleanup, runtime, heartbeats

#### report_service

- render manager report
- render operational summaries and delivery-facing synthesis

### Design requirement

HTTP and CLI must call services instead of embedding business logic directly.

---

## 5. Provider Layer Blueprint

### Objective

Prepare for provider-specific evolution without central conditional explosion.

### Proposed modules

- `providers/base.py`
- `providers/copilot.py`
- `providers/claude_code.py`
- `providers/ducc.py`
- `providers/opencode.py`

### Shared provider contract

Each provider adapter should expose capabilities such as:

- auth probing
- command construction
- prompt transport mode
- wrapper requirements
- recursion guard strategy
- provider-specific environment injection

### Design requirement

Adding a new provider should not require touching a dozen central branches.

---

## 6. Runtime Infrastructure Blueprint

### Objective

Split low-level runtime mechanics from orchestration logic.

### Proposed modules

- `runtime/paths.py`
- `runtime/session.py`
- `runtime/process.py`
- `runtime/worktree.py`
- `runtime/telemetry.py`

### Responsibilities

#### paths.py

- config path resolution
- log path resolution
- prompt/wrapper path resolution
- worktree root resolution
- session path resolution

#### session.py

- detached session state
- session selection
- listener/session metadata

#### process.py

- process start/stop
- terminate tree
- wait semantics
- pid liveness support

#### worktree.py

- branch existence checks
- ensure worktree behavior
- path derivation helpers

#### telemetry.py

- token usage parsing
- progress parsing
- last-activity parsing
- agent feed/peek extraction

### Design requirement

Runtime plumbing should remain reusable and presentation-agnostic.

---

## 7. Prompting Blueprint

### Objective

Turn prompt rendering into a subsystem rather than an incidental launch helper.

### Proposed modules

- `prompting/context.py`
- `prompting/render.py`
- `prompting/transports.py`

### Responsibilities

#### context.py

- scoped backlog brief
- scoped gates brief
- scoped runtime brief
- context file selection
- future executable dynamic-context hooks if ever needed

#### render.py

- prompt skeleton composition
- inline state context rendering
- stable section ordering and prompt formatting

#### transports.py

- prompt file path transport
- stdin prompt transport
- future provider-specific delivery adaptation

### Design requirement

Prompt assembly should be testable independently from worker launch.

---

## 8. Frontend Blueprint

### Current reality

The frontend has already made the right first move.

### Recommended next move

Do **not** do another large front-end structural rewrite now.

Instead:

1. keep the current component/lib split
2. strengthen the API contract boundary
3. keep view-model derivation in `lib/`
4. prevent storage and runtime internals from leaking into UI logic

### Frontend priorities

- mirror backend API models more explicitly
- keep `App.tsx` orchestration-only
- keep derived UI logic in `lib/data.ts`, `lib/config.ts`, and `lib/workflow.ts`
- avoid introducing YAML-shaped assumptions into UI code

---

## 9. CLI and Product Surface Blueprint

### Objective

Turn the runtime CLI from a thin launch wrapper into a product-grade control-plane command surface.

### Current commands

Already present:

- `serve`
- `up`
- `silent`
- `stop-agents`
- `stop-listener`
- `stop-all`

### Recommended additions

- `warp validate`
- `warp doctor`
- `warp scaffold`
- `warp status`
- optional future: `warp wake <agent>`
- optional future: `warp stop <agent>`

### Most important addition

#### `warp scaffold`

This command should:

- initialize `runtime/local_config.yaml`
- initialize missing state files in `state/`
- initialize `status/agents/`
- initialize `checkpoints/agents/`
- initialize worktree layout
- validate local repo root
- validate environment path assumptions
- validate provider binaries and basic launch readiness
- print launch blockers clearly

### Design requirement

Cold start should be a command path, not only a documentation path.

---

## 10. Testing Blueprint

### Objective

Align tests to architectural boundaries, not just feature endpoints.

### Recommended test layers

#### Layer 1 — Contracts / pure logic

Test:

- normalization
- enum/state semantics
- state transitions
- contract defaults

#### Layer 2 — Stores

Test:

- load/save behavior
- malformed state handling
- patch semantics
- persistence invariants

#### Layer 3 — Domain services

Test:

- task policy resolution
- worker plan resolution
- provider ranking
- cleanup readiness
- workflow patch semantics
- dashboard assembly

#### Layer 4 — API integration

Test:

- `/api/state`
- `/api/config`
- `/api/launch`
- `/api/workflow/update`
- `/api/team-mail/send`

#### Layer 5 — UI smoke

Test:

- tab routing
- settings hydration
- operations action surfaces
- A0 console action flow

### Highest-priority test targets

These are the first high-signal seams worth locking down:

- task policy resolution
- provider queue / pool scoring
- resolved worker planning
- cleanup status computation
- workflow patch semantics
- dashboard state assembly

---

## Out-of-Scope for the Near Term

The following should **not** be early priorities.

### 1. Role-tree redesign

`marrow-core`'s orchestrator/director/leader/specialist hierarchy is not the right first abstraction for `warp`.

`warp` is currently task/worker/pool/queue/console centric. Introducing a second role topology too early would add abstraction collision instead of clarity.

### 2. Heavy prompt casting runtime

A role-forge style casting pipeline is not the right next move for `warp` right now.

The control plane needs stronger contracts and state architecture before it needs a more elaborate prompt-runtime abstraction.

### 3. Extreme repo-external runtime relocation

`warp` is itself a control-plane repository. Its `state/`, `governance/`, `strategy/`, and `reports/` are part of the product surface and audit trail.

It should learn from workspace separation concepts without erasing the value of repo-local state and documentation.

---

## Implementation Todo

This section is the actionable roadmap.

---

## Phase 1 — Contracts First

### Goal

Establish one stable source of truth for control-plane structures.

### Todo

- [ ] Create `runtime/cp/contracts.py`
- [ ] Define canonical backlog item structure
- [ ] Define canonical runtime worker structure
- [ ] Define canonical heartbeat entry structure
- [ ] Define canonical mailbox message structure
- [ ] Define canonical cleanup state structure
- [ ] Define canonical merge queue item structure
- [ ] Define canonical resolved worker plan structure
- [ ] Define canonical config structures
- [ ] Move state/status enum sets into the contracts layer where appropriate
- [ ] Add tests for contract normalization and invariants

### Exit criteria

- every major runtime/API structure has one canonical definition
- core state transitions and required fields are testable against a contract layer

---

## Phase 2 — Durable Stores

### Goal

Separate persistence mechanics from business logic.

### Todo

- [ ] Create `runtime/cp/stores/`
- [ ] Implement `BacklogStore`
- [ ] Implement `HeartbeatStore`
- [ ] Implement `RuntimeStore`
- [ ] Implement `MailboxStore`
- [ ] Implement `LockStore`
- [ ] Implement `ProviderStatsStore`
- [ ] Implement `ManagerConsoleStore`
- [ ] Move YAML load/save/normalize logic from mixins into stores
- [ ] Add store tests for malformed state, normalization, and patch behavior

### Exit criteria

- mixins no longer directly own file-format-heavy state logic
- persistence logic is isolated and testable

---

## Phase 3 — Domain Extraction

### Goal

Move core control-plane reasoning into reusable domain services.

### Todo

- [ ] Create `runtime/cp/domain/`
- [ ] Extract task policy resolution from `routing_mixin.py`
- [ ] Extract worker plan derivation from `routing_mixin.py`
- [ ] Extract provider scoring/ranking from `provider_mixin.py`
- [ ] Extract cleanup evaluation from `state_mixin.py`
- [ ] Extract merge queue computation from `dashboard_mixin.py`
- [ ] Extract workflow patch semantics from `backlog_mixin.py`
- [ ] Extract mailbox catalog logic from `mailbox_mixin.py`
- [ ] Add domain tests for planning/routing/cleanup transitions

### Exit criteria

- core logic is no longer primarily encoded as mixin methods on one assembled service object
- domain behavior is reusable and independently testable

---

## Phase 4 — Services and API Models

### Goal

Stabilize application-facing orchestration and payload boundaries.

### Todo

- [ ] Create `runtime/cp/services/`
- [ ] Create `runtime/cp/api_models.py`
- [ ] Build `DashboardService`
- [ ] Build `LaunchService`
- [ ] Build `PromptService`
- [ ] Build `ReportService`
- [ ] Build `ConfigService`
- [ ] Build `WorkerService`
- [ ] Switch API assembly to use API models instead of ad hoc dict payloads where practical
- [ ] Add tests for dashboard assembly and launch/report services

### Exit criteria

- HTTP and CLI surfaces mainly orchestrate services
- API payloads become more stable and easier to mirror in frontend types

---

## Phase 5 — Product Surface Completion

### Goal

Make `warp` behave like a complete control-plane product, not just a runtime script set.

### Todo

- [ ] Add `warp validate`
- [ ] Add `warp doctor`
- [ ] Add `warp scaffold`
- [ ] Add `warp status`
- [ ] Standardize launch blocker output for humans and automation
- [ ] Improve cold-start flow so a user can stand up a fresh repo with commands instead of only docs
- [ ] Evaluate service install support for launchd/systemd generation

### Exit criteria

- a new machine or new repo user can bootstrap `warp` through commands with clear diagnostics

---

## Phase 6 — Provider and Runtime Maturation

### Goal

Reduce future complexity growth in provider handling and long-running runtime behavior.

### Todo

- [ ] Create `runtime/cp/providers/`
- [ ] Define provider adapter interface
- [ ] Migrate current provider-specific logic behind adapter objects
- [ ] Create `runtime/cp/runtime/paths.py`
- [ ] Create `runtime/cp/runtime/process.py`
- [ ] Create `runtime/cp/runtime/session.py`
- [ ] Create `runtime/cp/runtime/worktree.py`
- [ ] Move path/process/session/worktree logic into focused runtime helpers
- [ ] Strengthen detached-session and status handling tests

### Exit criteria

- adding providers becomes lower risk
- runtime/session/worktree logic is no longer scattered across unrelated modules

---

## Recommended Execution Order

If implementation capacity is limited, use this strict order:

1. contracts
2. stores
3. domain extraction
4. services + API models
5. scaffold / validate / doctor / status
6. provider/runtime pluginization

Do not start with role-topology redesign or heavy prompt-runtime abstraction.

---

## Architectural Acceptance Criteria

The blueprint should be considered meaningfully implemented only when all of the following are true:

- `warp` has a canonical contracts layer
- durable state is mediated through stores
- control-plane logic is no longer primarily encoded inside mixin-heavy service methods
- API payloads are shaped by explicit models/contracts
- CLI supports validation, diagnosis, and cold-start scaffold flows
- provider/runtime logic has clearer extension seams
- high-signal tests exist for planning, routing, cleanup, and dashboard assembly

---

## Final Recommendation

The next architectural move for `warp` is:

> **Contracts + Stores + Domain Extraction**

That is the correct successor to the already-completed modularization work.

Everything else becomes easier once those three are in place.
