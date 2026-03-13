export type TabKey = 'overview' | 'operations' | 'settings';

export type ConfigSection = 'project' | 'merge_policy' | 'resource_pools' | 'worker_defaults' | 'workers';

export type CommandMap = {
  serve: string;
  up: string;
};

export type LaunchStrategy = 'initial_provider' | 'selected_model' | 'elastic';

export type LaunchPolicyState = {
  default_strategy: LaunchStrategy;
  default_provider?: string | null;
  default_model?: string | null;
  available_strategies: LaunchStrategy[];
  available_providers: string[];
  initial_provider: string;
  has_launch_history: boolean;
};

export type DashboardMode = {
  state: string;
  cold_start: boolean;
  listener_active: boolean;
  reason: string;
  config_path: string;
  persist_config_path: string;
};

export type ProviderQueueItem = {
  resource_pool: string;
  provider: string;
  model: string;
  priority: number;
  binary: string;
  binary_found: boolean;
  recursion_guard: string;
  launch_wrapper: string;
  auth_mode: string;
  auth_ready: boolean;
  auth_detail: string;
  api_key_present: boolean;
  launch_ready: boolean;
  connection_quality: number;
  work_quality: number;
  score: number;
  latency_ms: number | null;
  active_workers: number;
  running_agents: Array<{ agent: string; progress_pct?: number | null; phase?: string; total_tokens?: number }>;
  usage: { input_tokens?: number; output_tokens?: number; total_tokens?: number };
  progress_pct?: number | null;
  last_activity_at?: string;
  last_failure: string;
};

export type MergeQueueItem = {
  agent: string;
  branch: string;
  submit_strategy: string;
  merge_target: string;
  worker_identity: string;
  manager_identity: string;
  status: string;
  checkpoint_status?: string;
  attention_summary?: string;
  blockers?: string[];
  pending_work?: string[];
  requested_unlocks?: string[];
  dependencies?: string[];
  resume_instruction?: string;
  next_checkin?: string;
  manager_action: string;
};

export type RuntimeWorker = {
  agent: string;
  task_id?: string;
  repository_name?: string;
  resource_pool: string;
  provider: string;
  model: string;
  recursion_guard?: string;
  launch_wrapper?: string;
  local_workspace_root?: string;
  repository_root?: string;
  worktree_path?: string;
  branch: string;
  environment_type?: string;
  environment_path?: string;
  sync_command?: string;
  test_command?: string;
  submit_strategy?: string;
  status: string;
};

export type ResolvedWorkerPlan = {
  agent: string;
  task_id: string;
  task_title: string;
  task_type: string;
  task_category: string;
  preferred_providers: string[];
  branch: string;
  worktree_path: string;
  resource_pool: string;
  resource_pool_queue: string[];
  recommended_pool: string;
  locked_pool: string;
  pool_reason: string;
  test_command: string;
  suggested_test_command: string;
};

export type HeartbeatAgent = {
  agent: string;
  role: string;
  state: string;
  last_seen: string;
  evidence: string;
  expected_next_checkin: string;
  escalation: string;
};

export type ProcessSnapshot = {
  resource_pool: string;
  provider: string;
  model: string;
  pid: number;
  alive: boolean;
  returncode: number | null;
  wrapper_path: string;
  recursion_guard: string;
  worktree_path: string;
  log_path: string;
  command: string[];
  phase?: string;
  progress_pct?: number | null;
  last_activity_at?: string;
  last_log_line?: string;
  usage?: { input_tokens?: number; output_tokens?: number; total_tokens?: number };
};

export type A0ConsoleRequest = {
  id: string;
  agent: string;
  task_id?: string;
  request_type?: string;
  status: string;
  title: string;
  body: string;
  requested_unlocks?: string[];
  blockers?: string[];
  resume_instruction?: string;
  next_checkin?: string;
  response_state?: string;
  response_note?: string;
  response_at?: string;
  created_at?: string;
};

export type A0ConsoleMessage = {
  id: string;
  direction: string;
  request_id?: string;
  action?: string;
  body: string;
  created_at: string;
};

export type A0ConsoleState = {
  requests: A0ConsoleRequest[];
  messages: A0ConsoleMessage[];
  inbox: TeamMailboxMessage[];
  pending_count: number;
  last_updated: string;
};

export type BacklogItem = {
  id: string;
  owner: string;
  status: string;
  gate: string;
  title: string;
  task_type?: string;
  priority?: string;
  dependencies?: string[];
  claim_state?: string;
  claimed_by?: string;
  claimed_at?: string;
  claim_note?: string;
  plan_required?: boolean;
  plan_state?: string;
  plan_summary?: string;
  plan_review_note?: string;
  review_requested_at?: string;
  review_note?: string;
  completed_at?: string;
  completed_by?: string;
  updated_at?: string;
};

export type TeamMailboxMessage = {
  id: string;
  from: string;
  to: string;
  scope: string;
  topic: string;
  body: string;
  related_task_ids?: string[];
  created_at: string;
  ack_state: string;
  resolution_note?: string;
  acked_at?: string;
};

export type TeamMailboxState = {
  messages: TeamMailboxMessage[];
  pending_count: number;
  a0_pending_count: number;
  last_updated: string;
};

export type CleanupWorkerState = {
  agent: string;
  ready: boolean;
  active: boolean;
  runtime_status: string;
  heartbeat_state: string;
  pending_plan_reviews: string[];
  pending_task_reviews: string[];
  locked_files: string[];
  blockers: string[];
};

export type CleanupState = {
  ready: boolean;
  blockers: string[];
  listener_active: boolean;
  active_workers: string[];
  pending_plan_reviews: string[];
  pending_task_reviews: string[];
  locked_files: Array<{ path: string; owner: string; state: string }>;
  workers: CleanupWorkerState[];
  last_updated: string;
};

export type WorkflowPatch = {
  title?: string;
  task_type?: string;
  owner?: string;
  status?: string;
  gate?: string;
  priority?: string;
  claim_state?: string;
  claimed_by?: string;
  claim_note?: string;
  plan_required?: boolean;
  plan_state?: string;
  plan_summary?: string;
  plan_review_note?: string;
  review_note?: string;
  dependencies?: string[];
  outputs?: string[];
  done_when?: string[];
};

export type GateItem = {
  id: string;
  name: string;
  status: string;
  owner: string;
};

export type ConfigProject = {
  repository_name?: string;
  local_repo_root?: string;
  reference_workspace_root?: string;
  paddle_repo_path?: string;
  integration_branch?: string;
  base_branch?: string;
  manager_git_identity?: {
    name?: string;
    email?: string;
  };
  dashboard?: {
    host?: string;
    port?: number;
  };
};

export type ConfigWorker = {
  agent: string;
  task_id?: string;
  resource_pool?: string;
  resource_pool_queue?: string[];
  worktree_path?: string;
  branch?: string;
  environment_type?: string;
  environment_path?: string;
  sync_command?: string;
  git_identity?: {
    name?: string;
    email?: string;
  };
  submit_strategy?: string;
  test_command?: string;
};

export type ConfigWorkerDefaults = {
  resource_pool?: string;
  resource_pool_queue?: string[];
  environment_type?: string;
  environment_path?: string;
  sync_command?: string;
  submit_strategy?: string;
  test_command?: string;
  git_identity?: {
    name?: string;
    email?: string;
  };
};

export type ConfigProvider = {
  api_key_env_name?: string;
  command_template?: string[];
};

export type ConfigResourcePool = {
  priority?: number;
  provider?: string;
  model?: string;
  api_key?: string;
  extra_env?: Record<string, string>;
};

export type ConfigShape = {
  project?: ConfigProject;
  providers?: Record<string, ConfigProvider>;
  resource_pools?: Record<string, ConfigResourcePool>;
  worker_defaults?: ConfigWorkerDefaults;
  workers?: ConfigWorker[];
};

export type ValidationIssue = {
  field: string;
  message: string;
};

export type DashboardState = {
  updated_at: string;
  last_event: string;
  mode: DashboardMode;
  project: ConfigProject;
  commands: CommandMap;
  launch_policy: LaunchPolicyState;
  manager_report: string;
  runtime: { workers?: RuntimeWorker[] };
  heartbeats: { agents?: HeartbeatAgent[] };
  backlog: { items?: BacklogItem[] };
  gates: { gates?: GateItem[] };
  processes: Record<string, ProcessSnapshot>;
  provider_queue: ProviderQueueItem[];
  resolved_workers: ResolvedWorkerPlan[];
  merge_queue: MergeQueueItem[];
  a0_console: A0ConsoleState;
  team_mailbox: TeamMailboxState;
  cleanup: CleanupState;
  config: ConfigShape;
  config_text: string;
  validation_errors: string[];
  launch_blockers: string[];
  peek: Record<string, string[]>;
};

export type ConfigSaveResponse = {
  ok: boolean;
  validation_issues: ValidationIssue[];
  validation_errors: string[];
  launch_blockers: string[];
  cold_start: boolean;
};

export type ConfigValidationResponse = {
  ok: boolean;
  validation_issues: ValidationIssue[];
  validation_errors: string[];
  launch_blockers: string[];
};

export type LaunchResponse = {
  ok: boolean;
  launch_policy?: {
    strategy: LaunchStrategy;
    provider?: string | null;
    model?: string | null;
  };
  launched?: Array<Record<string, unknown>>;
  failures?: Array<{ agent: string; error: string }>;
  errors?: string[];
};

export type StopWorkersResponse = {
  ok: boolean;
  stopped: string[];
};

export type StopAllResponse = {
  ok: boolean;
  stop_agents: boolean;
  listener_port?: number;
  listener_released?: boolean;
  stopped_workers?: string[];
  warning?: string;
};

export type SilentModeResponse = {
  ok: boolean;
  listener_port?: number;
  listener_active: boolean;
  stop_agents: boolean;
};

export type A0ConsoleResponse = {
  ok: boolean;
  a0_console: A0ConsoleState;
};

export type TaskActionResponse = {
  ok: boolean;
  task: BacklogItem;
  backlog: { items?: BacklogItem[] };
  a0_console: A0ConsoleState;
};

export type TeamMailboxResponse = {
  ok: boolean;
  message: TeamMailboxMessage;
  team_mailbox: TeamMailboxState;
};

export type StopWorkerResponse = {
  ok: boolean;
  agent: string;
  stopped: boolean;
  already_stopped: boolean;
  cleanup: CleanupState;
};

export type WorkflowUpdateResponse = {
  ok: boolean;
  task: BacklogItem;
  backlog: { items?: BacklogItem[] };
  a0_console: A0ConsoleState;
  cleanup: CleanupState;
};

export type TeamCleanupResponse = {
  ok: boolean;
  cleanup: CleanupState;
  listener_active: boolean;
  listener_port?: number;
  listener_release_requested: boolean;
  listener_released: boolean;
};
