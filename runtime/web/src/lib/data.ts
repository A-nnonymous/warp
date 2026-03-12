import type {
  AgentRow,
  IssueMap,
  ProgressModel,
} from './local-types';
import type {
  ConfigShape,
  ConfigWorker,
  DashboardState,
  GateItem,
  HeartbeatAgent,
  ProcessSnapshot,
  RuntimeWorker,
  ValidationIssue,
} from '../types';
import { normalizeConfig, formatTokenCount, classNames } from './utils';
import { hydrateConfigForA0, mergeWorkerWithDefaults, collectSectionIssues } from './config';
import { projectReferenceWorkspace } from './utils';

function sortAgents(rows: AgentRow[]): AgentRow[] {
  return [...rows].sort((left, right) => {
    const leftNum = Number(String(left.agent || '').replace(/[^0-9]/g, ''));
    const rightNum = Number(String(right.agent || '').replace(/[^0-9]/g, ''));
    return leftNum - rightNum;
  });
}

export function buildAgentRows(data: DashboardState | null): AgentRow[] {
  if (!data) {
    return [];
  }
  const byAgent = new Map<string, Partial<AgentRow>>();
  const remember = (agent: string | undefined, values: Partial<AgentRow>) => {
    if (!agent) {
      return;
    }
    byAgent.set(agent, { ...(byAgent.get(agent) || { agent }), ...values, agent });
  };

  (data.runtime?.workers || []).forEach((item: RuntimeWorker) => {
    remember(item.agent, {
      provider: item.provider,
      model: item.model,
      resource_pool: item.resource_pool,
      branch: item.branch,
      runtime_status: item.status,
    });
  });

  (data.config?.workers || []).forEach((item: ConfigWorker) => {
    remember(item.agent, { branch: item.branch });
  });

  (data.heartbeats?.agents || []).forEach((item: HeartbeatAgent) => {
    remember(item.agent, {
      role: item.role,
      heartbeat_state: item.state,
      last_seen: item.last_seen,
      evidence: item.evidence,
      escalation: item.escalation,
      expected_next_checkin: item.expected_next_checkin,
    });
  });

  Object.entries(data.processes || {}).forEach(([agent, item]: [string, ProcessSnapshot]) => {
    remember(agent, {
      process_alive: item.alive,
      pid: item.pid,
      provider: item.provider,
      model: item.model,
      resource_pool: item.resource_pool,
      phase: item.phase,
      progress_pct: item.progress_pct,
      total_tokens: item.usage?.total_tokens,
      last_activity_at: item.last_activity_at,
      last_log_line: item.last_log_line,
    });
  });

  return sortAgents(
    Array.from(byAgent.values()).map((item) => {
      const state = item.process_alive ? 'active' : item.heartbeat_state || item.runtime_status || 'not_started';
      return {
        agent: item.agent || 'unknown',
        role: item.role || 'worker',
        provider: item.provider || 'unassigned',
        model: item.model || 'unassigned',
        resource_pool: item.resource_pool || 'unassigned',
        branch: item.branch || 'unassigned',
        heartbeat_state: item.heartbeat_state,
        runtime_status: item.runtime_status,
        process_alive: item.process_alive,
        pid: item.pid,
        evidence: item.evidence,
        escalation: item.escalation,
        expected_next_checkin: item.expected_next_checkin,
        last_seen: item.last_seen,
        phase: item.phase,
        progress_pct: item.progress_pct,
        total_tokens: item.total_tokens,
        last_activity_at: item.last_activity_at,
        last_log_line: item.last_log_line,
        display_state: state,
      };
    }),
  );
}

export function buildProgressModel(data: DashboardState | null, agentRows: AgentRow[]): ProgressModel {
  const gates = data?.gates?.gates || [];
  const backlog = data?.backlog?.items || [];
  const passedGates = gates.filter((item) => item.status === 'passed').length;
  const progress = gates.length ? Math.round((passedGates / gates.length) * 100) : 0;
  const completedItems = backlog.filter((item) => ['done', 'completed', 'closed'].includes(String(item.status))).length;
  const blockedItems = backlog.filter((item) => String(item.status) === 'blocked').length;
  const claimedItems = backlog.filter((item) => ['claimed', 'in_progress', 'review'].includes(String(item.claim_state))).length;
  const reviewItems = backlog.filter((item) => String(item.status) === 'review' || String(item.claim_state) === 'review').length;
  const planPending = backlog.filter((item) => String(item.plan_state) === 'pending_review').length;
  const mailboxPending = data?.team_mailbox?.pending_count || 0;
  const activeAgents = agentRows.filter((item) => item.display_state === 'active' || item.display_state === 'healthy').length;
  const attentionAgents = agentRows.filter((item) => item.display_state === 'stale' || item.display_state.startsWith('launch_failed')).length;
  const openGate = gates.find((item) => item.status !== 'passed');
  return { progress, passedGates, totalGates: gates.length, completedItems, totalItems: backlog.length, blockedItems, claimedItems, reviewItems, planPending, mailboxPending, activeAgents, attentionAgents, openGate };
}

export function getLocalValidationIssues(config: ConfigShape, data: DashboardState | null): ValidationIssue[] {
  const draft = hydrateConfigForA0(data, normalizeConfig(config));
  const issues: ValidationIssue[] = [];
  const add = (field: string, message: string) => issues.push({ field, message });
  const project = draft.project || {};
  const dashboard = project.dashboard || {};
  const pools = draft.resource_pools || {};
  const workerDefaults = draft.worker_defaults || {};
  const workers = draft.workers || [];

  if (!String(project.repository_name || '').trim()) {
    add('project.repository_name', 'repository name is required');
  }
  if (!String(project.local_repo_root || '').trim()) {
    add('project.local_repo_root', 'local repo root is required');
  }
  const referenceWorkspace = projectReferenceWorkspace(project);
  if (referenceWorkspace && referenceWorkspace.startsWith('/absolute/path/')) {
    add('project.reference_workspace_root', 'reference workspace must be replaced with a real path');
  }
  if (!String(dashboard.host || '').trim()) {
    add('project.dashboard.host', 'dashboard host is required');
  }
  if (!Number.isInteger(Number(dashboard.port)) || Number(dashboard.port) < 1 || Number(dashboard.port) > 65535) {
    add('project.dashboard.port', 'dashboard port must be between 1 and 65535');
  }
  if (!String(project.integration_branch || project.base_branch || '').trim()) {
    add('project.integration_branch', 'integration branch is required');
  }

  const seenAgents = new Set<string>();
  const seenBranches = new Set<string>();
  const seenWorktrees = new Set<string>();

  Object.entries(pools).forEach(([poolName, pool]) => {
    if (!String(pool.provider || '').trim()) {
      add(`resource_pools.${poolName}.provider`, 'provider is required');
    }
    if (!String(pool.model || '').trim()) {
      add(`resource_pools.${poolName}.model`, 'model is required');
    }
    if (!Number.isInteger(Number(pool.priority ?? 100))) {
      add(`resource_pools.${poolName}.priority`, 'priority must be an integer');
    }
  });

  if (workerDefaults.resource_pool && !pools[workerDefaults.resource_pool]) {
    add('worker_defaults.resource_pool', 'default resource pool must refer to an existing pool');
  }
  if (workerDefaults.resource_pool_queue && workerDefaults.resource_pool_queue.some((poolName) => !pools[poolName])) {
    add('worker_defaults.resource_pool_queue', 'default queue must contain only existing pools');
  }
  if (workerDefaults.git_identity?.name && !workerDefaults.git_identity?.email) {
    add('worker_defaults.git_identity.email', 'default git identity email is required when name is set');
  }
  if (workerDefaults.git_identity?.email && !workerDefaults.git_identity?.name) {
    add('worker_defaults.git_identity.name', 'default git identity name is required when email is set');
  }

  workers.forEach((worker, index) => {
    const effectiveWorker = mergeWorkerWithDefaults(worker, workerDefaults);
    const root = `workers[${index}]`;
    const agent = String(worker.agent || '').trim();
    const branch = String(effectiveWorker.branch || '').trim();
    const worktreePath = String(effectiveWorker.worktree_path || '').trim();
    if (!agent) {
      add(`${root}.agent`, 'agent is required');
    } else if (seenAgents.has(agent)) {
      add(`${root}.agent`, 'agent must be unique');
    } else {
      seenAgents.add(agent);
    }
    if (!branch) {
      add(`${root}.branch`, 'branch is required');
    } else if (seenBranches.has(branch)) {
      add(`${root}.branch`, 'branch must be unique');
    } else {
      seenBranches.add(branch);
    }
    if (!worktreePath) {
      add(`${root}.worktree_path`, 'worktree path is required');
    } else if (seenWorktrees.has(worktreePath)) {
      add(`${root}.worktree_path`, 'worktree path must be unique');
    } else {
      seenWorktrees.add(worktreePath);
    }
    const poolName = String(effectiveWorker.resource_pool || '').trim();
    const queue = effectiveWorker.resource_pool_queue || [];
    if (!poolName && !queue.length) {
      add(`${root}.resource_pool`, 'resource pool or queue is required');
    }
    if (!String(effectiveWorker.test_command || '').trim()) {
      add(`${root}.test_command`, 'test command is required');
    }
    if (!String(effectiveWorker.submit_strategy || '').trim()) {
      add(`${root}.submit_strategy`, 'submit strategy is required');
    }
    if (String(effectiveWorker.environment_type || 'uv') === 'venv' && !String(effectiveWorker.environment_path || '').trim()) {
      add(`${root}.environment_path`, 'environment path is required when environment type is venv');
    }
  });

  return issues;
}

export function buildIssueMap(issues: ValidationIssue[]): IssueMap {
  const map: IssueMap = {};
  issues.forEach((issue) => {
    if (!map[issue.field]) {
      map[issue.field] = [];
    }
    map[issue.field].push(issue.message);
  });
  return map;
}

export function summarizeValidationMessages(issues: ValidationIssue[], blockers: string[]): string {
  const parts: string[] = [];
  if (issues.length) {
    parts.push(`${issues.length} validation issue(s)`);
  }
  if (blockers.length) {
    parts.push(`${blockers.length} launch blocker(s)`);
  }
  return parts.join(', ') || 'unknown validation failure';
}

export function formatLaunchErrorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  if (message.includes('status 4')) {
    return `launch rejected: ${message}`;
  }
  return `launch failed: ${message}`;
}

export function renderValidation(data: DashboardState): string {
  const launchBlockers = data.launch_blockers || [];
  const notes = data.validation_errors || [];
  const lines = [
    launchBlockers.length ? `Launch blockers:\n- ${launchBlockers.join('\n- ')}` : 'Launch blockers:\nnone',
    notes.length ? `\nConfig notes:\n- ${notes.join('\n- ')}` : '\nConfig notes:\nnone',
  ];
  return lines.join('\n');
}
