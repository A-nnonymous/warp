import type { BacklogItem, GateItem, TeamMailboxMessage, ConfigWorkerDefaults } from '../types';

export const AUTO_REFRESH_MS = 4000;
export const A0_CONSOLE_VIEW = 'a0-console';

export type AgentRow = {
  agent: string;
  role: string;
  provider: string;
  model: string;
  resource_pool: string;
  branch: string;
  heartbeat_state?: string;
  runtime_status?: string;
  process_alive?: boolean;
  pid?: number;
  evidence?: string;
  escalation?: string;
  expected_next_checkin?: string;
  last_seen?: string;
  phase?: string;
  progress_pct?: number | null;
  total_tokens?: number;
  last_activity_at?: string;
  last_log_line?: string;
  display_state: string;
};

export type ProgressModel = {
  progress: number;
  passedGates: number;
  totalGates: number;
  completedItems: number;
  totalItems: number;
  blockedItems: number;
  claimedItems: number;
  reviewItems: number;
  planPending: number;
  mailboxPending: number;
  activeAgents: number;
  attentionAgents: number;
  openGate?: GateItem;
};

export type IssueMap = Record<string, string[]>;
export type SectionStatusMap = Partial<Record<import('../types').ConfigSection, { message: string; error: boolean }>>;
export type PlannedWorker = {
  agent: string;
  task_id: string;
  title: string;
  branch: string;
  worktree_path: string;
};

export type WorkerPlanView = {
  agent: string;
  taskId: string;
  taskTitle: string;
  taskType: string;
  branch: string;
  worktreePath: string;
  poolOverride: string;
  queueOverride: string[];
  recommendedPool: string;
  lockedPool: string;
  poolReason: string;
  testCommand: string;
  suggestedTestCommand: string;
};

export type WorkerResetScope = 'all' | 'routing' | 'runtime';

export type MailboxDraft = {
  from: string;
  to: string;
  topic: string;
  scope: string;
  relatedTaskIds: string;
  body: string;
};

export type WorkflowDraft = {
  taskId: string;
  title: string;
  owner: string;
  claimedBy: string;
  status: string;
  claimState: string;
  gate: string;
  priority: string;
  dependencies: string;
  planRequired: string;
  planState: string;
  planSummary: string;
  claimNote: string;
  reviewNote: string;
  managerNote: string;
};

export type WorkflowPresetAction = 'replan' | 'reassign' | 'reopen';

export const DEFAULT_MAILBOX_DRAFT: MailboxDraft = {
  from: 'A0',
  to: 'all',
  topic: 'status_note',
  scope: 'broadcast',
  relatedTaskIds: '',
  body: '',
};

export const DEFAULT_WORKFLOW_DRAFT: WorkflowDraft = {
  taskId: '',
  title: '',
  owner: '',
  claimedBy: '',
  status: 'pending',
  claimState: 'unclaimed',
  gate: '',
  priority: '',
  dependencies: '',
  planRequired: 'no',
  planState: 'none',
  planSummary: '',
  claimNote: '',
  reviewNote: '',
  managerNote: '',
};
