# Documentation Architecture

## Purpose

This file defines the markdown architecture of `warp` so the repository does not drift into overlapping, noisy instructions.

Each markdown file should have one primary responsibility.

## Top-Level Layers

### 1. Entry Documents

- `README.md`: operator-facing overview and shortest reliable paths
- `RESUME.md`: restore an interrupted live control session
- `new_machine_prompt.md`: rebuild control state on a new machine
- `bootstrap/BOOTSTRAP.md`: zero-context takeover for ongoing `warp` development

### 2. Governance Documents

- `governance/axioms.md`: foundational axioms, human-write-only, all other governance derives from these
- `governance/manager_protocol.md`: manager responsibilities, interruption priority, self-evolution model, planning authority
- `governance/operating_model.md`: durable multi-agent operating semantics
- `governance/control_plane_playbook.md`: how to change `warp` without regressing the operator path
- `governance/worker_launch_playbook.md`: worker launch and runtime execution semantics
- `governance/agent_team_patterns.md`: rationale behind current coordination primitives
- `governance/documentation_architecture.md`: this file, which assigns markdown responsibilities

### 3. Strategy Documents

- `strategy/integration_plan.md`: current product or engineering plan
- `strategy/baseline_trace.md`: baseline mapping and reference semantics

### 4. Live State Documents

- `state/*.yaml`: machine-readable durable control state
- `status/agents/*.md`: current worker progress views
- `checkpoints/**/*.md`: resumable handoff state

### 5. Reports

- `reports/manager_report.md`: current manager-facing operational synthesis
- other `reports/*.md`: delivery or engineering outputs, not core governance law

## Authoritative Boundaries

To reduce duplication, use these boundaries:

- put stable workflow law in `governance/`
- put current plan and scope in `strategy/`
- put current runtime truth in `state/`, `status/`, and `checkpoints/`
- put the shortest entry instructions in top-level files
- put zero-context takeover guidance in `bootstrap/`

## Noise Control Rules

- Do not repeat the full startup sequence in every file.
- Do not repeat the same invariants across README, bootstrap, and governance unless each copy serves a distinct entry role.
- Prefer linking to the authoritative file over copying long passages.
- When adding a new markdown file, define what existing file it prevents from growing noisier.

## What Belongs Where

### Put It In README

- shortest commands
- top-level architecture summary
- where to go next

### Put It In bootstrap

- low-token takeover instructions for a generic agent
- repo map
- settled invariants
- recent decisions that are expensive to rediscover

### Put It In governance

- foundational axioms (human-write-only)
- stable collaboration law
- planning authority
- escalation rules
- manager and worker responsibilities
- control-plane change checklists

### Put It In strategy

- current project objective
- decomposition and sequencing
- baseline mapping

### Put It In checkpoints or status

- incremental progress
- open blockers
- immediate next step
- handoff notes

## Review Standard For Markdown Changes

Before adding or expanding a markdown file, ask:

1. Is this stable law, current plan, or live state?
2. Which existing file should be authoritative for it?
3. Does the new text reduce ambiguity, or just copy existing guidance?
4. Can a zero-context agent find the same answer faster after this change?

If the answer to the last question is no, the markdown architecture is getting worse.
