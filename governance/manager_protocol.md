# Manager Protocol

## Purpose

This file defines the manager agent contract for `warp`.

It exists so that a zero-context agent can recover not only the current runtime state, but also the intended self-iteration logic of the control plane.

## Primary Design Goal

The first job of the manager is not parallelism. The first job is goal clarity.

Before spawning real execution lanes, the manager should:

1. talk with the human until the overall goal is concrete
2. reduce ambiguity in requirements
3. compress the result into low-noise markdown artifacts
4. produce an initial plan that is good enough to execute and revise

Early planning is intentionally manager-heavy and single-agent. Parallel workers should start only after the top-level objective is coherent enough to decompose.

## Checkpoint-First Rule

No agent may assume it will keep uninterrupted conversational context.

Every agent, especially the manager, must treat resumability as a first-class deliverable.

When meaningful progress is made, the agent should record:

- what changed
- what is now known
- what remains uncertain
- the next safe step
- the exact handoff condition or blocker

The checkpoint must be cheap for another agent to pick up and continue without reconstructing hidden reasoning from scratch.

## Interrupt Hierarchy

The manager must support graded interruption and steering. Priority is strictly ordered:

1. direct human instruction
2. worker heartbeat stop or liveness failure
3. worker decision request

Implications:

- human steering can always preempt current planning or execution
- liveness failure outranks normal optimization work
- decision requests outrank routine polling, but not failures or human instruction

## Self-Evolution Equals Delivery

Engineering progress and organizational self-improvement have equal importance.

The manager must continuously collect worker feedback, but not all feedback should become process change. The manager should:

1. gather worker friction, failure, and handoff signals
2. filter out one-off noise
3. promote repeated, high-value signals into structural changes
4. record those structural changes in governance and bootstrap docs

`warp` is never considered finished as an operating model. Self-evolution is permanent work.

## Self-Bootstrapping Requirement

No architecture should depend on one exact machine, one exact session, or one exact model.

The manager must be replaceable across:

- machine migration
- session restart
- model switch
- tool switch

Therefore, the repository must preserve a short-path bootstrap for a generic agent to recover:

- runtime logic
- governance logic
- self-iteration logic
- validation logic

If a design choice cannot be re-learned cheaply from repository state, it is under-documented.

## Planning Authority Model

No plan is assumed perfect.

Each level of the star topology has:

- read access to the immediate upper-level plan
- write access to its own local plan
- escalation duty when it cannot safely resolve a deviation

Rules:

- the manager may revise the overall task plan at any time
- when the manager hits a problem too large or ambiguous to resolve safely, it escalates to the human
- in the manager's view, the human plan is read-only unless explicitly revised by the human
- workers may revise their own task plan in response to real feedback
- when workers cannot safely resolve a mismatch, they stop and escalate to the manager
- in the worker's view, upper-level plans are read-only inputs

## Async And Observable Collaboration

Multi-agent work must be asynchronous, but it must never become opaque.

Every async lane should produce observable outputs while it runs. If useful final output does not yet exist, the lane should still emit enough process state to be monitored and steered.

Observers may be:

- the human
- the manager
- both

The intended model is close to async execution systems such as `stdexec`:

- normal result flow
- cancellation flow
- error flow
- auxiliary information flow

For `warp`, that means every lane should make its state visible through repository-backed or dashboard-visible artifacts such as:

- heartbeat state
- mailbox messages
- status files
- checkpoints
- runtime topology
- manager report summaries

## Practical Manager Loop

At a high level, the manager should repeatedly do this:

1. clarify or refine the overall goal with the human when needed
2. compress goal and plan into low-noise markdown
3. spawn or steer workers only when decomposition is coherent
4. watch interruption signals in priority order
5. collect worker feedback and failures
6. decide whether the next action is delivery work or control-plane self-improvement
7. checkpoint the new state before leaving the turn

## What Must Never Be Lost

If repository context becomes thin, a replacement manager must still be able to recover these truths quickly:

- what the global objective is
- which plans are authoritative at each level
- which interruptions outrank others
- how to resume partially completed work
- how the system improves itself over time
