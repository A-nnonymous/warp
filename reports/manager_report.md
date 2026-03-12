# Manager Report

Last updated: 2026-03-13T00:02:47

## Production View

- Stage: live manager polling
- Delivery mode: listener active
- Current gate: G0 Protocol Freeze
- Current manager: A0
- Poll loop: every 5 seconds

## Real Liveness

- A0: healthy
- A1: launching
- A2: launching
- A3: launching
- A4: not-started
- A5: not-started
- A6: not-started
- A7: not-started

## Control Snapshot

- Active agents: A1, A2, A3
- Attention agents: none
- Runnable agents: A6
- Blocked agents: A4, A5, A7

## Active Blockers

- blocked by dependency or gate: A4, A5, A7

## Immediate Action

1. Review attention agents first and clear launch or runtime faults.
2. Launch the next runnable set when provider readiness is green.
3. Keep gate ordering aligned with backlog dependencies before widening scope.
