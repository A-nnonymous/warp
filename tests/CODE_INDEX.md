# CODE_INDEX — tests/

Repository test entrypoint. Python control-plane tests live under `tests/runtime/` so they no longer mix with production code.

## Layout

| Path | Purpose |
|---|---|
| `runtime/` | Unit and integration tests for control-plane backend, services, and runtime behavior |

## Main commands

- Full integration suite: `python3 -m unittest tests.runtime.test_control_plane_integration -v`
- Targeted unittest module: `python3 -m unittest tests.runtime.test_dashboard_queue_service -v`
- Targeted pytest module: `pytest tests/runtime/test_task_routing_service.py -q`
