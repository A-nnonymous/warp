# Agent-Team Pattern Adaptation

## Goal

Borrow the useful coordination patterns from Claude agent teams without forcing warp to depend on any one vendor's runtime model.

The target outcome is not "make warp behave exactly like Claude Code." The target outcome is:

- keep A0 as the lead agent
- keep workers isolated by worktree, branch, and environment
- let agents coordinate through durable shared state instead of chat history
- reduce idle workers, duplicate investigation, and ambiguous handoffs

## What Claude Agent Teams Get Right

Claude's official agent-team model adds a few collaboration primitives that are stronger than simple multi-session spawning:

1. shared task list with claim semantics
2. explicit task dependencies that unblock automatically
3. direct teammate communication instead of manager-only relay
4. plan approval for risky work before edits begin
5. completion hooks that can reject premature task completion
6. explicit teammate shutdown and team cleanup lifecycle

These are process primitives, not UI details. Warp should copy the primitives, not the exact product surface.

## What Warp Already Has

Warp already implements several pieces of the same model.

### Present today

- shared task inventory in `state/backlog.yaml`
- dependency fields in backlog items
- worker runtime registry in `state/agent_runtime.yaml`
- heartbeat and stale-agent detection in `state/heartbeats.yaml`
- single-writer lock discipline in `state/edit_locks.yaml`
- resumable worker and manager checkpoints in `checkpoints/`
- A0 review and response surface through `state/manager_console.yaml` and the A0 Console UI

### Current gap

Warp has the storage pieces, but some team behaviors are still implicit or manager-only.

The main missing collaboration primitives are:

- explicit task claim and release state
- durable worker-to-worker mailbox
- formal plan-review state before implementation
- task completion gates that can reject a bad handoff
- explicit shutdown and cleanup protocol for finished workers

## Recommended Adaptation

### 1. Make task claiming first-class

Claude teams treat the task list as a live coordination surface. Warp should do the same.

Recommended backlog additions per item:

- `claim_state`: unclaimed, claimed, in_progress, review, completed
- `claimed_by`: agent id or empty
- `claimed_at`: ISO timestamp
- `claim_note`: short purpose or current angle
- `plan_required`: boolean
- `plan_state`: none, pending_review, approved, rejected

Why this matters:

- avoids two workers drifting onto the same task
- distinguishes planning from coding
- gives A0 a stable way to see which work is actually active

Important rule:

- `owner` stays as the default responsible lane
- `claimed_by` is the live executor

That mirrors Claude's lead-assigned versus self-claimed distinction without losing warp's role mapping.

### 2. Add a durable team mailbox

Claude teammates can message each other directly. Warp should support the same idea, but through files and the dashboard API rather than provider-native chat.

Recommended new state file:

- `state/team_mailbox.yaml`

Suggested message schema:

- `id`
- `from`
- `to`
- `scope`: direct, broadcast, manager
- `topic`: blocker, handoff, review_request, design_question, status_note
- `body`
- `related_task_ids`
- `created_at`
- `ack_state`: pending, seen, resolved
- `resolution_note`

Why file-backed mailbox instead of provider chat:

- works across Copilot, Claude, ducc, and OpenCode
- remains resumable after a crashed session
- becomes visible in dashboard state and reports
- preserves the repository-first operating model

The existing A0 Console should become one view over that mailbox, not a special-case side channel.

### 3. Separate planning from implementation

Claude's plan-approval mode is especially useful for risky or high-conflict changes. Warp should adopt the same control point for tasks that touch shared control files, protocol contracts, or merge-critical code.

Recommended policy:

- tasks that touch protocol, shared config, merge rules, or single-writer files start in planning mode
- worker writes plan to its checkpoint and optionally status file
- A0 approves or rejects through the review queue
- implementation begins only after approval

Recommended trigger sources:

- backlog `task_type`
- gate sensitivity
- declared editable files
- whether the task requests a single-writer lock

This fits warp well because the project already depends on checkpoints and edit locks.

### 4. Turn completion into a gate, not a note

Claude teams use completion hooks to stop a teammate from marking work done too early. Warp should add an equivalent manager-side rule before a task can become completed.

Recommended completion checklist:

- runtime entry is valid for the worker
- latest checkpoint is fresh
- latest status includes blockers and next step or handoff note
- required test command is recorded and last result is attached
- requested unlocks are either cleared or escalated
- merge or submit path is explicit

Recommended backlog states:

- `review` means worker believes the task is done but A0 has not accepted it yet
- `completed` means manager accepted the handoff
- `merged` remains a separate integration state if needed

This reduces false progress and makes backlog dependency unblocking more trustworthy.

### 5. Introduce explicit cleanup semantics

Claude's team cleanup model is worth copying almost exactly.

Warp should define two manager-only actions:

- worker shutdown: stop one worker cleanly, update heartbeat, runtime status, and mailbox
- team cleanup: refuse cleanup while any worker is still active or has unresolved review state

Recommended cleanup preconditions:

- no active worker process
- no pending plan approvals
- no pending review handoffs
- no outstanding single-writer lock owned by the worker

This would prevent the current class of "runtime looks quiet but state is still half-open" failure.

## What Not To Copy Blindly

Some Claude guidance should be adapted, not duplicated.

### Do not over-spawn workers

Claude recommends small teams because coordination cost scales fast. Warp should preserve the same discipline.

Default recommendation:

- 3 to 5 active workers for most delivery phases
- only expand when task dependencies show genuine parallel slack

### Do not allow same-file parallel editing

Warp already has a stronger answer than Claude here: single-writer lock files. Keep that rule.

### Do not rely on transient terminal context

Claude teams assume live sessions. Warp must keep preferring durable repo state because its main value is resumability across tools and providers.

## Implementation Order

### Phase 1: low-risk governance and state changes

- extend backlog schema with claim and plan-review fields
- add `state/team_mailbox.yaml`
- define allowed message topics and ack states
- define manager-only completion acceptance rules

This phase is mostly schema and playbook work.

### Phase 2: runtime and API changes

- add API endpoints for claim, release, message, approve, reject, and complete
- generalize A0 Console to consume mailbox plus review queue
- expose backlog review state and mailbox state in dashboard payloads

### Phase 3: UI changes

- show task claim state directly in Overview
- add mailbox or inbox views per agent and for A0
- show planning-mode tasks distinctly from coding tasks
- add explicit cleanup readiness indicator

## Success Criteria

Warp can claim it has absorbed the best parts of agent teams when all of the following are true:

- every active task has one clear live claimant
- blocked tasks stay blocked until dependencies are manager-accepted
- workers can ask each other or A0 questions without leaving hidden context
- risky work can be forced through plan approval
- completed means accepted, not merely claimed as finished
- shutdown and cleanup leave no ambiguous runtime state behind

## Short Recommendation

The highest-value adaptation is:

1. first-class task claiming
2. file-backed mailbox
3. plan approval for risky tasks
4. review state before completion

Those four changes align almost exactly with Claude's strongest agent-team patterns while staying faithful to warp's repo-backed control-plane model.
