# CODE_INDEX — runtime/cp/

Backend control-plane package. `ControlPlaneService` is assembled via mixin-based multiple inheritance; each mixin owns a single domain.

| Module | Responsibility | Key exports |
|---|---|---|
| `__init__.py` | Assembles `ControlPlaneService`, ensures generated runtime directories exist, re-exports CLI entrypoint | `ControlPlaneService`, `main` |
| `constants.py` | Canonical path constants, runtime-generated directory layout, status sets, env-var names | `GENERATED_DIR`, `PROMPT_DIR`, `WRAPPER_DIR`, `SESSION_DIR`, `LOG_DIR`, `CONTROL_PLANE_LOG`, `SESSION_STATE`, status/env constants |
| `contracts.py` | Typed dict contracts for config, runtime state, queue rows, mailbox, workflow patch, dashboard payloads | Dashboard and config typed dict exports |
| `stores/` | Durable-state access layer for backlog, mailbox, runtime, heartbeats, locks, manager console, provider stats | Store classes |
| `services/` | Pure domain/service layer for routing, queue shaping, cleanup views, mailbox views, workflow patches, telemetry, auth, notifications | Barrel exports in `services/__init__.py` |
| `utils.py` | YAML, shell, process, and text helpers | `now_iso`, `yaml_text`, `format_command`, `slugify`, `terminate_process_tree`, ... |
| `telemetry.py` | Log-based usage/progress parsing | `read_log_telemetry`, normalization helpers |
| `markdown.py` | Markdown section/list/paragraph parsing | `parse_markdown_sections`, `parse_markdown_list`, `parse_markdown_paragraph` |
| `network.py` | HTTP server binding, process lifecycle helpers, session-state lookup under `runtime/generated/sessions/` | `WorkerProcess`, `LaunchPolicy`, `create_http_servers`, `session_state_path_for_port`, `post_control_plane` |
| `config_mixin.py` | Config loading, validation, persistence, section save behavior | `ConfigMixin` |
| `backlog_mixin.py` | Backlog/task state and workflow patch orchestration | `BacklogMixin` |
| `mailbox_mixin.py` | Team mailbox CRUD and A0-console user-message handling | `MailboxMixin` |
| `routing_mixin.py` | Task policy, pool routing, branch/worktree derivation | `RoutingMixin` |
| `context_mixin.py` | Agent-scoped prompt context shaping | `ContextMixin` |
| `provider_mixin.py` | Provider wrapper generation, auth/pool orchestration, launch-policy evaluation | `ProviderMixin` |
| `launch_mixin.py` | Prompt rendering, worktree/bootstrap setup, worker lifecycle, checkpoint launch flow | `LaunchMixin` |
| `state_mixin.py` | Runtime state, heartbeats, provider stats, session-state persistence, telemetry snapshots | `StateMixin` |
| `peek_mixin.py` | Live peek ring buffer and persistence | `PeekMixin` |
| `dashboard_mixin.py` | Dashboard payload assembly, manager report generation, merge queue, A0 request catalog | `DashboardMixin` |
| `api_mixin.py` | HTTP request handlers and dashboard lifecycle | `ApiMixin` |
| `cli.py` | CLI parsing, detach flow, stop commands, runtime config resolution | `parse_args`, `main` |

## Runtime-generated outputs

- Worker prompts: `runtime/generated/prompts/`
- Provider wrappers: `runtime/generated/wrappers/`
- Session-state snapshots: `runtime/generated/sessions/`
- Logs: `runtime/generated/logs/`
