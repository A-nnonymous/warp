"""Curated control-plane service exports.

This barrel keeps `runtime.cp.services` as the stable import surface for pure
helpers extracted from mixins. Keep it explicit and reasonably ordered so the
service layer stays easy to scan during future refactors.
"""

from .backlog_notifications import mailbox_notification, task_action_notification, workflow_patch_notifications
from .cleanup_views import cleanup_locked_files, cleanup_review_maps, cleanup_status_view, cleanup_worker_row
from .dashboard_queue import build_a0_request_catalog, build_merge_queue
from .dashboard_summary import compute_manager_control_state, summarize_worker_handoff
from .mailbox_views import build_team_mailbox_catalog, manager_inbox, pending_mailbox_messages
from .pool_selection import (
    best_pool_for_provider,
    best_pool_for_worker,
    configured_pool_candidates,
    pool_rank_tuple,
    queue_pool_candidates,
    rank_pool_candidates,
    recommended_pool_plan,
)
from .provider_auth import configured_api_key, provider_auth_mode, provider_auth_status, provider_probe_timeout, provider_probe_values
from .provider_queue import provider_connection_quality, provider_failure_detail, provider_queue_item
from .task_routing import (
    build_task_profile,
    initial_provider_name,
    provider_preference_default,
    select_task_record_for_worker,
    suggested_branch_name,
    suggested_task_id,
    task_policy_config,
    task_policy_defaults,
    task_policy_rule_matches,
    task_policy_rules,
    task_policy_types,
)
from .telemetry_views import (
    command_contract,
    normalize_usage,
    process_launch_metadata,
    process_runtime_metadata,
    process_snapshot_entry,
    running_agent_telemetry,
    summarize_pool_usage,
)
from .workflow_patch import apply_task_action, apply_workflow_patch, summarize_workflow_patch, validate_workflow_updates

__all__ = [
    "apply_task_action",
    "apply_workflow_patch",
    "best_pool_for_provider",
    "best_pool_for_worker",
    "build_a0_request_catalog",
    "build_merge_queue",
    "build_task_profile",
    "build_team_mailbox_catalog",
    "cleanup_locked_files",
    "cleanup_review_maps",
    "cleanup_status_view",
    "cleanup_worker_row",
    "command_contract",
    "compute_manager_control_state",
    "configured_api_key",
    "configured_pool_candidates",
    "initial_provider_name",
    "mailbox_notification",
    "manager_inbox",
    "normalize_usage",
    "pending_mailbox_messages",
    "pool_rank_tuple",
    "process_launch_metadata",
    "process_runtime_metadata",
    "process_snapshot_entry",
    "provider_auth_mode",
    "provider_auth_status",
    "provider_connection_quality",
    "provider_failure_detail",
    "provider_preference_default",
    "provider_probe_timeout",
    "provider_probe_values",
    "provider_queue_item",
    "queue_pool_candidates",
    "rank_pool_candidates",
    "recommended_pool_plan",
    "running_agent_telemetry",
    "select_task_record_for_worker",
    "suggested_branch_name",
    "suggested_task_id",
    "summarize_pool_usage",
    "summarize_worker_handoff",
    "summarize_workflow_patch",
    "task_action_notification",
    "task_policy_config",
    "task_policy_defaults",
    "task_policy_rule_matches",
    "task_policy_rules",
    "task_policy_types",
    "validate_workflow_updates",
    "workflow_patch_notifications",
]
