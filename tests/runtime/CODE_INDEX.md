# CODE_INDEX — tests/runtime/

Python tests for the WARP control plane.

| Module | Responsibility |
|---|---|
| `test_control_plane_integration.py` | End-to-end control-plane integration, CLI/API flows, prompt generation, shutdown semantics |
| `test_control_plane_architecture.py` | Import-surface and architecture guardrails |
| `test_control_plane_runtime_edges.py` | Runtime-path and mixin edge-case coverage |
| `test_dashboard_queue_service.py` | Merge queue and A0 request shaping |
| `test_dashboard_service.py` | Manager-control summary and handoff classification |
| `test_cleanup_view_service.py` | Cleanup blockers and review aggregation |
| `test_mailbox_view_service.py` | Team mailbox catalog shaping |
| `test_backlog_notification_service.py` | Mailbox fanout and workflow notifications |
| `test_workflow_patch_service.py` | Workflow patch and task action semantics |
| `test_task_routing_service.py` | Task policy matching, provider preference, branch/test command shaping |
| `test_pool_selection_service.py` | Pool recommendation and candidate ranking |
| `test_provider_auth_service.py` | Provider auth readiness and probe semantics |
| `test_provider_queue_service.py` | Provider queue scoring and failure detail |
| `test_telemetry_view_service.py` | Usage normalization and telemetry view shaping |
| `test_store_normalization.py` | Durable store normalization rules |
