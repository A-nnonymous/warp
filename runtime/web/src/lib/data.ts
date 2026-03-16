import type {
  AgentRow,
  IssueMap,
  ProgressModel,
} from './local-types';
import type {
  ConfigShape,
  ConfigWorker,
  DashboardState,
  HeartbeatAgent,
  ProcessSnapshot,
  RuntimeWorker,
  ValidationIssue,
} from '../types';
import { normalizeConfig, formatTokenCount, translateUiText } from './utils';
import { hydrateConfigForA0, mergeWorkerWithDefaults } from './config';
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
    add('project.repository_name', '仓库名不能为空');
  }
  if (!String(project.local_repo_root || '').trim()) {
    add('project.local_repo_root', '本地仓库根目录不能为空');
  }
  const referenceWorkspace = projectReferenceWorkspace(project);
  if (referenceWorkspace && referenceWorkspace.startsWith('/absolute/path/')) {
    add('project.reference_workspace_root', '参考工作区必须替换为真实路径');
  }
  if (!String(dashboard.host || '').trim()) {
    add('project.dashboard.host', 'Dashboard Host 不能为空');
  }
  if (!Number.isInteger(Number(dashboard.port)) || Number(dashboard.port) < 1 || Number(dashboard.port) > 65535) {
    add('project.dashboard.port', 'Dashboard Port 必须在 1 到 65535 之间');
  }
  if (!String(project.integration_branch || project.base_branch || '').trim()) {
    add('project.integration_branch', '集成分支不能为空');
  }

  const seenAgents = new Set<string>();
  const seenBranches = new Set<string>();
  const seenWorktrees = new Set<string>();

  Object.entries(pools).forEach(([poolName, pool]) => {
    if (!String(pool.provider || '').trim()) {
      add(`resource_pools.${poolName}.provider`, 'Provider 不能为空');
    }
    if (!String(pool.model || '').trim()) {
      add(`resource_pools.${poolName}.model`, '模型不能为空');
    }
    if (!Number.isInteger(Number(pool.priority ?? 100))) {
      add(`resource_pools.${poolName}.priority`, '优先级必须是整数');
    }
  });

  if (workerDefaults.resource_pool && !pools[workerDefaults.resource_pool]) {
    add('worker_defaults.resource_pool', '默认资源池必须引用已存在的池');
  }
  if (workerDefaults.resource_pool_queue && workerDefaults.resource_pool_queue.some((poolName) => !pools[poolName])) {
    add('worker_defaults.resource_pool_queue', '默认队列只能包含已存在的资源池');
  }
  if (workerDefaults.git_identity?.name && !workerDefaults.git_identity?.email) {
    add('worker_defaults.git_identity.email', '设置默认 Git 名称时必须同时填写邮箱');
  }
  if (workerDefaults.git_identity?.email && !workerDefaults.git_identity?.name) {
    add('worker_defaults.git_identity.name', '设置默认 Git 邮箱时必须同时填写名称');
  }

  workers.forEach((worker, index) => {
    const effectiveWorker = mergeWorkerWithDefaults(worker, workerDefaults);
    const root = `workers[${index}]`;
    const agent = String(worker.agent || '').trim();
    const branch = String(effectiveWorker.branch || '').trim();
    const worktreePath = String(effectiveWorker.worktree_path || '').trim();
    if (!agent) {
      add(`${root}.agent`, 'Agent 不能为空');
    } else if (seenAgents.has(agent)) {
      add(`${root}.agent`, 'Agent 必须唯一');
    } else {
      seenAgents.add(agent);
    }
    if (!branch) {
      add(`${root}.branch`, '分支不能为空');
    } else if (seenBranches.has(branch)) {
      add(`${root}.branch`, '分支必须唯一');
    } else {
      seenBranches.add(branch);
    }
    if (!worktreePath) {
      add(`${root}.worktree_path`, 'worktree 路径不能为空');
    } else if (seenWorktrees.has(worktreePath)) {
      add(`${root}.worktree_path`, 'worktree 路径必须唯一');
    } else {
      seenWorktrees.add(worktreePath);
    }
    const poolName = String(effectiveWorker.resource_pool || '').trim();
    const queue = effectiveWorker.resource_pool_queue || [];
    if (!poolName && !queue.length) {
      add(`${root}.resource_pool`, '必须设置资源池或资源池队列');
    }
    if (!String(effectiveWorker.test_command || '').trim()) {
      add(`${root}.test_command`, '测试命令不能为空');
    }
    if (!String(effectiveWorker.submit_strategy || '').trim()) {
      add(`${root}.submit_strategy`, '提交策略不能为空');
    }
    if (String(effectiveWorker.environment_type || 'uv') === 'venv' && !String(effectiveWorker.environment_path || '').trim()) {
      add(`${root}.environment_path`, '环境类型为 venv 时必须填写环境路径');
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
    parts.push(`${issues.length} 个校验问题`);
  }
  if (blockers.length) {
    parts.push(`${blockers.length} 个启动阻塞项`);
  }
  return parts.join('，') || '未知校验失败';
}

export function formatLaunchErrorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  if (message.includes('status 4')) {
    return `启动请求被拒绝：${translateUiText(message)}`;
  }
  return `启动失败：${translateUiText(message)}`;
}

export function renderValidation(data: DashboardState): string {
  const launchBlockers = data.launch_blockers || [];
  const notes = data.validation_errors || [];
  const lines = [
    launchBlockers.length
      ? `启动阻塞项：\n- ${launchBlockers.map((item) => translateUiText(item)).join('\n- ')}`
      : '启动阻塞项：\n无',
    notes.length
      ? `\n配置提示：\n- ${notes.map((item) => translateUiText(item)).join('\n- ')}`
      : '\n配置提示：\n无',
  ];
  return lines.join('\n');
}
