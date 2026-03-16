from __future__ import annotations

from pathlib import Path

CONTROL_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = CONTROL_ROOT
STATE_DIR = CONTROL_ROOT / "state"
RUNTIME_DIR = CONTROL_ROOT / "runtime"
GENERATED_DIR = RUNTIME_DIR / "generated"
CONFIG_TEMPLATE_PATH = RUNTIME_DIR / "config_template.yaml"
DEFAULT_DASHBOARD_HOST = "0.0.0.0"
DEFAULT_DASHBOARD_PORT = 8233
DEFAULT_WORKTREE_DIR = CONTROL_ROOT / "worktrees"
PROMPT_DIR = GENERATED_DIR / "prompts"
WRAPPER_DIR = GENERATED_DIR / "wrappers"
SESSION_DIR = GENERATED_DIR / "sessions"
LOG_DIR = GENERATED_DIR / "logs"
CONTROL_PLANE_LOG = LOG_DIR / "control_plane.log"
MANAGER_REPORT = CONTROL_ROOT / "reports" / "manager_report.md"
MANAGER_CONSOLE_PATH = STATE_DIR / "manager_console.yaml"
TEAM_MAILBOX_PATH = STATE_DIR / "team_mailbox.yaml"
STATUS_DIR = CONTROL_ROOT / "status" / "agents"
CHECKPOINT_DIR = CONTROL_ROOT / "checkpoints" / "agents"
SESSION_STATE = SESSION_DIR / "session_state.json"
PROVIDER_STATS_PATH = STATE_DIR / "provider_stats.yaml"
CONTROL_PLANE_RUNTIME = "uv run --no-project --with 'PyYAML>=6.0.2' python"
WEB_STATIC_DIR = RUNTIME_DIR / "web" / "static"
WEB_INDEX_FILE = WEB_STATIC_DIR / "index.html"
DEFAULT_INITIAL_PROVIDER = "ducc"
LAUNCH_STRATEGIES = {"initial_provider", "selected_model", "elastic"}
CONFIG_SECTIONS = {"project", "merge_policy", "resource_pools", "worker_defaults", "workers"}
PROVIDER_AUTH_MODES = {"api_key", "session"}
CONTROL_PLANE_WORKER_CONTEXT_ENV = "CONTROL_PLANE_WORKER_CONTEXT"
CONTROL_PLANE_WORKER_AGENT_ENV = "CONTROL_PLANE_WORKER_AGENT"
CONTROL_PLANE_RECURSION_POLICY_ENV = "CONTROL_PLANE_RECURSION_POLICY"
CONTROL_PLANE_ALLOW_NESTED_ENV = "CONTROL_PLANE_ALLOW_NESTED"
CONTROL_PLANE_WRAPPED_PROVIDER_ENV = "CONTROL_PLANE_WRAPPED_PROVIDER"
CONTROL_PLANE_GUARD_MODE_ENV = "CONTROL_PLANE_GUARD_MODE"
BACKLOG_COMPLETED_STATUSES = {"done", "completed", "closed", "merged"}
BACKLOG_ACTIVE_STATUSES = {"active", "in_progress", "in-progress"}
BACKLOG_PENDING_STATUSES = {"", "pending", "queued", "not-started", "not_started"}
BACKLOG_CLAIM_STATES = {"unclaimed", "claimed", "in_progress", "review", "completed"}
BACKLOG_PLAN_STATES = {"none", "pending_review", "approved", "rejected"}
MAILBOX_ACK_STATES = {"pending", "seen", "resolved"}
