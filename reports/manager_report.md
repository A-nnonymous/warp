# Manager Report

Last updated: 2026-03-13T18:07:50

## Production View

- Stage: live manager polling
- Delivery mode: listener active
- Current gate: G0 Protocol Freeze
- Current manager: A0
- Poll loop: every 5 seconds

## Real Liveness

- A0: healthy
- A1: offline
- A2: offline
- A3: offline
- A4: offline
- A5: offline
- A6: offline
- A7: offline

## Control Snapshot

- Active agents: none
- Attention agents: none
- Runnable agents: A1, A6
- Blocked agents: A2, A3, A4, A5, A7

## Active Blockers

- blocked by dependency or gate: A2, A3, A4, A5, A7

## Immediate Action

1. Review attention agents first and clear launch or runtime faults.
2. Launch the next runnable set when provider readiness is green.
3. Keep gate ordering aligned with backlog dependencies before widening scope.
