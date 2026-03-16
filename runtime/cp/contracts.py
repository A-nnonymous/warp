from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class GitIdentity(TypedDict, total=False):
    name: str
    email: str


class ProjectConfig(TypedDict, total=False):
    repository_name: str
    local_repo_root: str
    reference_workspace_root: str
    reference_inputs: list[str]
    prompt_context_files: list[str]
    base_branch: str
    integration_branch: str
    initial_provider: str
    manager_git_identity: GitIdentity
    dashboard: dict[str, Any]


class ProviderConfig(TypedDict, total=False):
    api_key_env_name: str
    auth_mode: str
    prompt_transport: str
    command_template: list[str]
    probe_timeout_seconds: int


class ResourcePoolConfig(TypedDict, total=False):
    priority: int
    provider: str
    model: str
    api_key: str
    extra_env: dict[str, str]


class WorkerDefaultsConfig(TypedDict, total=False):
    resource_pool: str
    resource_pool_queue: list[str]
    environment_type: str
    environment_path: str
    sync_command: str
    submit_strategy: str
    test_command: str
    git_identity: GitIdentity


class WorkerConfig(TypedDict, total=False):
    agent: str
    task_id: str
    resource_pool: str
    resource_pool_queue: list[str]
    worktree_path: str
    branch: str
    environment_type: str
    environment_path: str
    sync_command: str
    git_identity: GitIdentity
    submit_strategy: str
    test_command: str
    launch_owner: str
    provider: str
    model: str


class ConfigShape(TypedDict, total=False):
    project: ProjectConfig
    providers: dict[str, ProviderConfig]
    resource_pools: dict[str, ResourcePoolConfig]
    worker_defaults: WorkerDefaultsConfig
    workers: list[WorkerConfig]
    task_policies: dict[str, Any]


class BacklogItem(TypedDict, total=False):
    id: str
    title: str
    task_type: str
    owner: str
    status: str
    gate: str
    priority: str
    dependencies: list[str]
    outputs: list[str]
    done_when: list[str]
    claim_state: str
    claimed_by: str
    claimed_at: str
    claim_note: str
    plan_required: bool
    plan_state: str
    plan_summary: str
    plan_review_note: str
    plan_reviewed_at: str
    review_requested_at: str
    review_note: str
    completed_at: str
    completed_by: str
    updated_at: str


class BacklogState(TypedDict, total=False):
    project: str
    last_updated: str
    manager: str
    phase: str
    items: list[BacklogItem]


class GateItem(TypedDict, total=False):
    id: str
    name: str
    status: str
    owner: str


class GateState(TypedDict, total=False):
    gates: list[GateItem]


class RuntimeWorkerEntry(TypedDict, total=False):
    agent: str
    task_id: str
    repository_name: str
    resource_pool: str
    provider: str
    model: str
    recursion_guard: str
    launch_wrapper: str
    launch_owner: str
    local_workspace_root: str
    repository_root: str
    worktree_path: str
    branch: str
    merge_target: str
    environment_type: str
    environment_path: str
    sync_command: str
    test_command: str
    submit_strategy: str
    git_author_name: str
    git_author_email: str
    status: str


class RuntimeState(TypedDict, total=False):
    project: str
    last_updated: str
    schema: dict[str, Any]
    workers: list[RuntimeWorkerEntry]


class HeartbeatAgent(TypedDict, total=False):
    agent: str
    role: str
    state: str
    last_seen: str
    evidence: str
    expected_next_checkin: str
    escalation: str


class HeartbeatState(TypedDict, total=False):
    project: str
    last_updated: str
    agents: list[HeartbeatAgent]


class TelemetryUsage(TypedDict, total=False):
    input_tokens: int
    output_tokens: int
    total_tokens: int


class ProcessCommand(TypedDict, total=False):
    argv: list[str]
    binary: str
    display: str
    uses_wrapper: bool


class RunningAgentTelemetry(TypedDict, total=False):
    agent: str
    progress_pct: int | None
    phase: str
    usage: TelemetryUsage


class PoolUsageSummary(TypedDict, total=False):
    running_agents: list[RunningAgentTelemetry]
    usage: TelemetryUsage
    progress_pct: int | None
    last_activity_at: str


class ProcessLaunchMetadata(TypedDict, total=False):
    wrapper_path: str
    recursion_guard: str
    command: ProcessCommand


class ProcessRuntimeMetadata(TypedDict, total=False):
    pid: int
    alive: bool
    returncode: int | None
    worktree_path: str
    log_path: str


class ProcessSnapshot(TypedDict, total=False):
    resource_pool: str
    provider: str
    model: str
    pid: int
    alive: bool
    returncode: int | None
    wrapper_path: str
    recursion_guard: str
    worktree_path: str
    log_path: str
    command: ProcessCommand
    launch: ProcessLaunchMetadata
    runtime: ProcessRuntimeMetadata
    phase: str
    progress_pct: int | None
    last_activity_at: str
    last_log_line: str
    usage: TelemetryUsage


class ResolvedWorkerPlan(TypedDict, total=False):
    agent: str
    task_id: str
    task_title: str
    task_type: str
    task_category: str
    preferred_providers: list[str]
    branch: str
    worktree_path: str
    resource_pool: str
    resource_pool_queue: list[str]
    recommended_pool: str
    locked_pool: str
    pool_reason: str
    test_command: str
    suggested_test_command: str


class ProviderQueueItem(TypedDict, total=False):
    resource_pool: str
    provider: str
    model: str
    priority: int
    binary: str
    binary_found: bool
    recursion_guard: str
    launch_wrapper: str
    auth_mode: str
    auth_ready: bool
    auth_detail: str
    api_key_present: bool
    launch_ready: bool
    connection_quality: int
    work_quality: int
    score: int
    latency_ms: int | None
    active_workers: int
    running_agents: list[RunningAgentTelemetry]
    usage: TelemetryUsage
    progress_pct: NotRequired[int | None]
    last_activity_at: NotRequired[str]
    last_failure: str


class MergeQueueItem(TypedDict, total=False):
    agent: str
    branch: str
    submit_strategy: str
    merge_target: str
    worker_identity: str
    manager_identity: str
    status: str
    checkpoint_status: str
    attention_summary: str
    blockers: list[str]
    pending_work: list[str]
    requested_unlocks: list[str]
    dependencies: list[str]
    resume_instruction: str
    next_checkin: str
    manager_action: str


class ManagerControlState(TypedDict, total=False):
    worker_count: int
    active_agents: list[str]
    attention_agents: list[str]
    runnable_agents: list[str]
    blocked_agents: list[str]


class WorkerHandoffSummary(TypedDict, total=False):
    checkpoint_status: str
    attention_summary: str
    blockers: list[str]
    pending_work: list[str]
    requested_unlocks: list[str]
    dependencies: list[str]
    resume_instruction: str
    next_checkin: str


class WorkflowPatch(TypedDict, total=False):
    title: str
    task_type: str
    owner: str
    status: str
    gate: str
    priority: str
    claim_state: str
    claimed_by: str
    claim_note: str
    plan_required: bool
    plan_state: str
    plan_summary: str
    plan_review_note: str
    review_note: str
    dependencies: list[str] | str
    outputs: list[str] | str
    done_when: list[str] | str


TeamMailboxMessage = TypedDict(
    "TeamMailboxMessage",
    {
        "id": str,
        "from": NotRequired[str],
        "to": str,
        "scope": str,
        "topic": str,
        "body": str,
        "related_task_ids": list[str],
        "created_at": str,
        "ack_state": str,
        "resolution_note": str,
        "acked_at": str,
    },
    total=False,
)


class TeamMailboxState(TypedDict, total=False):
    messages: list[TeamMailboxMessage]
    pending_count: int
    a0_pending_count: int
    a0_inbox: list[TeamMailboxMessage]
    last_updated: str


class CleanupWorkerState(TypedDict, total=False):
    agent: str
    ready: bool
    active: bool
    runtime_status: str
    heartbeat_state: str
    pending_plan_reviews: list[str]
    pending_task_reviews: list[str]
    locked_files: list[str]
    blockers: list[str]


class CleanupState(TypedDict, total=False):
    ready: bool
    blockers: list[str]
    listener_active: bool
    active_workers: list[str]
    pending_plan_reviews: list[str]
    pending_task_reviews: list[str]
    locked_files: list[dict[str, str]]
    workers: list[CleanupWorkerState]
    last_updated: str


class A0ConsoleRequest(TypedDict, total=False):
    id: str
    agent: str
    task_id: str
    request_type: str
    status: str
    title: str
    body: str
    requested_unlocks: list[str]
    blockers: list[str]
    resume_instruction: str
    next_checkin: str
    response_state: str
    response_note: str
    response_at: str
    created_at: str


class A0ConsoleMessage(TypedDict, total=False):
    id: str
    direction: str
    request_id: str
    action: str
    body: str
    created_at: str


class A0ConsoleState(TypedDict, total=False):
    requests: list[A0ConsoleRequest]
    messages: list[A0ConsoleMessage]
    inbox: list[TeamMailboxMessage]
    pending_count: int
    last_updated: str


class ManagerConsoleState(TypedDict, total=False):
    requests: dict[str, A0ConsoleRequest]
    messages: list[A0ConsoleMessage]


class CommandMap(TypedDict, total=False):
    serve: str
    up: str


class LaunchPolicyState(TypedDict, total=False):
    default_strategy: str
    default_provider: str | None
    default_model: str | None
    available_strategies: list[str]
    available_providers: list[str]
    initial_provider: str
    has_launch_history: bool


class DashboardMode(TypedDict, total=False):
    state: str
    cold_start: bool
    listener_active: bool
    reason: str
    config_path: str
    persist_config_path: str


class DashboardState(TypedDict, total=False):
    updated_at: str
    last_event: str
    mode: DashboardMode
    project: ProjectConfig
    commands: CommandMap
    launch_policy: LaunchPolicyState
    manager_report: str
    runtime: RuntimeState
    heartbeats: HeartbeatState
    backlog: BacklogState
    gates: GateState
    processes: dict[str, ProcessSnapshot]
    provider_queue: list[ProviderQueueItem]
    resolved_workers: list[ResolvedWorkerPlan]
    merge_queue: list[MergeQueueItem]
    a0_console: A0ConsoleState
    team_mailbox: TeamMailboxState
    cleanup: CleanupState
    config: ConfigShape
    config_text: str
    validation_errors: list[str]
    launch_blockers: list[str]
    peek: dict[str, list[str]]
