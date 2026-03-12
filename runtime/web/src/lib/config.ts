import type {
  ConfigShape,
  ConfigSection,
  ConfigWorker,
  ConfigWorkerDefaults,
  ConfigResourcePool,
  DashboardState,
  ResolvedWorkerPlan,
  RuntimeWorker,
  ValidationIssue,
} from '../types';
import type { PlannedWorker, WorkerPlanView, WorkerResetScope } from './local-types';
import {
  normalizedText,
  isAutoManagedBlank,
  isPlaceholderPath,
  firstMeaningfulValue,
  firstMeaningfulCommand,
  firstMeaningfulPath,
  cloneConfig,
  normalizeConfig,
  slugify,
  projectReferenceWorkspace,
} from './utils';

export function mergeWorkerWithDefaults(worker: ConfigWorker, defaults: ConfigWorkerDefaults | undefined): ConfigWorker {
  const merged: ConfigWorker = { ...worker };
  const workerDefaults = defaults || {};
  const inheritableFields: Array<keyof ConfigWorkerDefaults> = [
    'resource_pool',
    'environment_type',
    'environment_path',
    'sync_command',
    'submit_strategy',
    'test_command',
  ];

  inheritableFields.forEach((field) => {
    const workerValue = merged[field as keyof ConfigWorker];
    const defaultValue = workerDefaults[field];
    if ((workerValue === undefined || workerValue === '') && defaultValue !== undefined && defaultValue !== '') {
      (merged as Record<string, unknown>)[field] = defaultValue;
    }
  });

  if ((!Array.isArray(merged.resource_pool_queue) || merged.resource_pool_queue.length === 0) && Array.isArray(workerDefaults.resource_pool_queue) && workerDefaults.resource_pool_queue.length > 0) {
    merged.resource_pool_queue = [...workerDefaults.resource_pool_queue];
  }

  const defaultIdentity = workerDefaults.git_identity || {};
  const workerIdentity = merged.git_identity || {};
  const mergedIdentity = {
    name: workerIdentity.name || defaultIdentity.name || '',
    email: workerIdentity.email || defaultIdentity.email || '',
  };
  if (mergedIdentity.name || mergedIdentity.email) {
    merged.git_identity = mergedIdentity;
  }

  return merged;
}

export function resetWorkerDefaultsToA0(defaults: ConfigWorkerDefaults | undefined): ConfigWorkerDefaults {
  return {};
}

export function resetWorkerOverridesToA0(worker: ConfigWorker, scope: WorkerResetScope = 'all'): ConfigWorker {
  const next: ConfigWorker = { agent: worker.agent };
  if (scope === 'routing') {
    return {
      ...worker,
      resource_pool: undefined,
      resource_pool_queue: undefined,
      task_id: undefined,
      branch: undefined,
      worktree_path: undefined,
    };
  }
  if (scope === 'runtime') {
    return {
      ...worker,
      environment_type: undefined,
      environment_path: undefined,
      sync_command: undefined,
      test_command: undefined,
      submit_strategy: undefined,
      git_identity: undefined,
    };
  }
  return next;
}

export function deriveWorktreePath(config: ConfigShape, agent: string): string {
  const normalizedAgent = normalizedText(agent).toLowerCase();
  if (!normalizedAgent) {
    return '';
  }
  const existingWorkers = config.workers || [];
  for (const worker of existingWorkers) {
    const workerAgent = normalizedText(worker.agent).toLowerCase();
    const worktreePath = normalizedText(worker.worktree_path);
    if (!workerAgent || !worktreePath || isPlaceholderPath(worktreePath)) {
      continue;
    }
    const suffix = `_${workerAgent}`;
    if (worktreePath.endsWith(suffix)) {
      return `${worktreePath.slice(0, -suffix.length)}_${normalizedAgent}`;
    }
  }
  return '';
}

export function deriveBranchName(agent: string, title: string, taskId: string): string {
  const branchSuffix = slugify(title || taskId || agent) || agent.toLowerCase();
  return `${agent.toLowerCase()}_${branchSuffix}`;
}

export function deriveDefaultEnvironmentPath(config: ConfigShape): string {
  const localRepoRoot = normalizedText(config.project?.local_repo_root);
  if (!localRepoRoot) {
    return '';
  }
  return `${localRepoRoot.replace(/\/$/, '')}/.venv`;
}

export function normalizeDerivedPaths(config: ConfigShape): ConfigShape {
  const next = normalizeConfig(cloneConfig(config));
  const nextAutoEnvPath = deriveDefaultEnvironmentPath(next);
  next.worker_defaults = next.worker_defaults || {};
  if (next.worker_defaults.environment_type !== 'none') {
    const currentEnvironmentPath = normalizedText(next.worker_defaults.environment_path);
    if (!currentEnvironmentPath || isPlaceholderPath(currentEnvironmentPath)) {
      next.worker_defaults.environment_path = nextAutoEnvPath;
    }
  }
  next.workers = (next.workers || []).map((worker) => {
    const worktreePath = normalizedText(worker.worktree_path);
    const environmentPath = normalizedText(worker.environment_path);
    const derivedWorktreePath = deriveWorktreePath(next, worker.agent);
    return {
      ...worker,
      worktree_path: !worktreePath || isPlaceholderPath(worktreePath) ? (derivedWorktreePath || undefined) : worker.worktree_path,
      environment_path: !environmentPath || isPlaceholderPath(environmentPath) ? undefined : worker.environment_path,
    };
  });
  return next;
}

export function mergeSavedSection(current: ConfigShape, server: ConfigShape, section: ConfigSection): ConfigShape {
  const next = normalizeConfig(cloneConfig(current));
  const serverConfig = normalizeConfig(cloneConfig(server));
  if (section === 'project') {
    next.project = {
      ...(next.project || {}),
      repository_name: serverConfig.project?.repository_name,
      local_repo_root: serverConfig.project?.local_repo_root,
      reference_workspace_root: serverConfig.project?.reference_workspace_root,
      paddle_repo_path: serverConfig.project?.paddle_repo_path,
      dashboard: serverConfig.project?.dashboard || {},
    };
    return next;
  }
  if (section === 'merge_policy') {
    next.project = {
      ...(next.project || {}),
      integration_branch: serverConfig.project?.integration_branch,
      base_branch: serverConfig.project?.base_branch,
      manager_git_identity: serverConfig.project?.manager_git_identity || {},
    };
    return next;
  }
  if (section === 'resource_pools') {
    next.resource_pools = serverConfig.resource_pools || {};
    return next;
  }
  if (section === 'worker_defaults') {
    next.worker_defaults = serverConfig.worker_defaults || {};
    return next;
  }
  next.workers = serverConfig.workers || [];
  return next;
}

export function buildSectionValue(config: ConfigShape, section: ConfigSection): unknown {
  if (section === 'project') {
    const project = config.project || {};
    return {
      repository_name: project.repository_name || '',
      local_repo_root: project.local_repo_root || '',
      reference_workspace_root: projectReferenceWorkspace(project),
      dashboard: project.dashboard || {},
    };
  }
  if (section === 'merge_policy') {
    const project = config.project || {};
    return {
      integration_branch: project.integration_branch || project.base_branch || '',
      manager_git_identity: project.manager_git_identity || {},
    };
  }
  if (section === 'resource_pools') {
    return config.resource_pools || {};
  }
  if (section === 'worker_defaults') {
    return config.worker_defaults || {};
  }
  return config.workers || [];
}

export function configForProjectSave(baseConfig: ConfigShape | undefined, draftConfig: ConfigShape): ConfigShape {
  const base = normalizeConfig(cloneConfig(baseConfig));
  const draft = normalizeConfig(cloneConfig(draftConfig));
  return normalizeDerivedPaths(mergeSavedSection(base, draft, 'project'));
}

export function buildRuntimeWorkerMap(data: DashboardState | null): Map<string, Record<string, unknown>> {
  return new Map((data?.runtime.workers || []).map((worker) => [worker.agent, worker as Record<string, unknown>]));
}

export function buildResolvedWorkerMap(data: DashboardState | null): Map<string, ResolvedWorkerPlan> {
  return new Map((data?.resolved_workers || []).map((worker) => [worker.agent, worker]));
}

export function deriveDefaultPoolQueue(config: ConfigShape, data: DashboardState | null): string[] {
  if (data?.provider_queue?.length) {
    return data.provider_queue.map((item) => item.resource_pool);
  }
  return Object.entries(config.resource_pools || {})
    .sort((left, right) => Number(right[1].priority ?? 100) - Number(left[1].priority ?? 100))
    .map(([poolName]) => poolName);
}

export function inferRuntimeWorkerValue(data: DashboardState | null, field: keyof RuntimeWorker, allowNone = false): string {
  const counts = new Map<string, number>();
  (data?.runtime.workers || []).forEach((worker) => {
    if (worker.agent === 'A0') {
      return;
    }
    const value = normalizedText((worker as Record<string, unknown>)[field as string]);
    const lowered = value.toLowerCase();
    if (!value || lowered === 'unassigned' || (!allowNone && lowered === 'none')) {
      return;
    }
    counts.set(value, (counts.get(value) || 0) + 1);
  });
  return Array.from(counts.entries())
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))[0]?.[0] || '';
}

export function buildPlannedWorkers(data: DashboardState | null, config: ConfigShape): PlannedWorker[] {
  if (!data) {
    return [];
  }

  const byAgent = new Map<string, PlannedWorker>();
  const configuredByAgent = new Map((config.workers || []).map((worker) => [normalizedText(worker.agent), worker]));
  (data.backlog.items || []).forEach((item) => {
    const agent = String(item.owner || '').trim();
    if (!agent || agent === 'A0') {
      return;
    }
    if (!byAgent.has(agent)) {
      byAgent.set(agent, {
        agent,
        task_id: item.id,
        title: item.title,
        branch: deriveBranchName(agent, item.title, item.id),
        worktree_path: firstMeaningfulPath(configuredByAgent.get(agent)?.worktree_path, deriveWorktreePath(config, agent)),
      });
    }
  });

  (data.runtime.workers || []).forEach((item) => {
    const agent = String(item.agent || '').trim();
    if (!agent || agent === 'A0' || byAgent.has(agent)) {
      return;
    }
    byAgent.set(agent, {
      agent,
      task_id: `${agent}-001`,
      title: item.branch || agent,
      branch: item.branch || deriveBranchName(agent, item.branch || agent, `${agent}-001`),
      worktree_path: firstMeaningfulPath(configuredByAgent.get(agent)?.worktree_path, deriveWorktreePath(config, agent)),
    });
  });

  return Array.from(byAgent.values()).sort((left, right) => left.agent.localeCompare(right.agent, undefined, { numeric: true }));
}

export function workerPlanView(
  worker: ConfigWorker,
  config: ConfigShape,
  data: DashboardState | null,
  plannedWorkers?: PlannedWorker[],
): WorkerPlanView {
  const plannedByAgent = new Map((plannedWorkers || buildPlannedWorkers(data, config)).map((item) => [item.agent, item]));
  const resolvedByAgent = buildResolvedWorkerMap(data);
  const planned = plannedByAgent.get(worker.agent || '');
  const resolved = resolvedByAgent.get(worker.agent || '');
  return {
    agent: worker.agent || '',
    taskId: firstMeaningfulValue(worker.task_id, resolved?.task_id, planned?.task_id),
    taskTitle: firstMeaningfulValue(resolved?.task_title, planned?.title),
    taskType: firstMeaningfulValue(resolved?.task_type, resolved?.task_category),
    branch: firstMeaningfulValue(worker.branch, resolved?.branch, planned?.branch),
    worktreePath: firstMeaningfulValue(worker.worktree_path, resolved?.worktree_path, planned?.worktree_path),
    poolOverride: normalizedText(worker.resource_pool),
    queueOverride: Array.isArray(worker.resource_pool_queue) ? worker.resource_pool_queue : [],
    recommendedPool: normalizedText(resolved?.recommended_pool),
    lockedPool: normalizedText(resolved?.locked_pool),
    poolReason: normalizedText(resolved?.pool_reason),
    testCommand: firstMeaningfulCommand(worker.test_command, resolved?.test_command),
    suggestedTestCommand: firstMeaningfulCommand(resolved?.suggested_test_command),
  };
}

export function hydrateConfigForA0(data: DashboardState | null, config: ConfigShape): ConfigShape {
  const next = normalizeConfig(cloneConfig(config));
  const runtimeByAgent = buildRuntimeWorkerMap(data);
  const resolvedByAgent = buildResolvedWorkerMap(data);
  const managerRuntime = runtimeByAgent.get('A0');

  next.project = next.project || {};
  next.project.repository_name = firstMeaningfulValue(next.project.repository_name, managerRuntime?.repository_name);
  next.project.local_repo_root = firstMeaningfulValue(
    next.project.local_repo_root,
    managerRuntime?.local_workspace_root,
    managerRuntime?.repository_root,
  );
  next.project.integration_branch = firstMeaningfulValue(next.project.integration_branch, next.project.base_branch, 'main');
  next.project.dashboard = next.project.dashboard || {};
  next.project.dashboard.host = firstMeaningfulValue(next.project.dashboard.host, '0.0.0.0');
  if (!Number.isInteger(Number(next.project.dashboard.port)) || Number(next.project.dashboard.port) <= 0) {
    next.project.dashboard.port = 8233;
  }

  next.worker_defaults = next.worker_defaults || {};
  if (!Array.isArray(next.worker_defaults.resource_pool_queue) || next.worker_defaults.resource_pool_queue.length === 0) {
    next.worker_defaults.resource_pool_queue = deriveDefaultPoolQueue(next, data);
  }
  next.worker_defaults.environment_type = firstMeaningfulValue(
    next.worker_defaults.environment_type,
    inferRuntimeWorkerValue(data, 'environment_type', true),
    'uv',
  );
  if (next.worker_defaults.environment_type !== 'none') {
    next.worker_defaults.environment_path = firstMeaningfulValue(
      next.worker_defaults.environment_path,
      inferRuntimeWorkerValue(data, 'environment_path'),
      deriveDefaultEnvironmentPath(next),
    );
  }
  next.worker_defaults.sync_command = firstMeaningfulCommand(
    next.worker_defaults.sync_command,
    inferRuntimeWorkerValue(data, 'sync_command'),
    next.worker_defaults.environment_type === 'uv' ? 'uv sync' : '',
  );
  next.worker_defaults.submit_strategy = firstMeaningfulCommand(
    next.worker_defaults.submit_strategy,
    inferRuntimeWorkerValue(data, 'submit_strategy'),
    'patch_handoff',
  );
  next.worker_defaults.test_command = firstMeaningfulCommand(
    next.worker_defaults.test_command,
    inferRuntimeWorkerValue(data, 'test_command'),
    'uv run pytest tests/moe_test.py',
  );

  const plannedWorkers = buildPlannedWorkers(data, next);
  const plannedAgents = new Set(plannedWorkers.map((worker) => worker.agent));
  const existingByAgent = new Map((next.workers || []).filter((worker) => normalizedText(worker.agent)).map((worker) => [worker.agent, worker]));

  const hydratedPlannedWorkers = plannedWorkers.map((plannedWorker) => {
    const existing = existingByAgent.get(plannedWorker.agent);
    const runtimeWorker = runtimeByAgent.get(plannedWorker.agent);
    const resolvedWorker = resolvedByAgent.get(plannedWorker.agent);
    const gitIdentity = existing?.git_identity && (existing.git_identity.name || existing.git_identity.email)
      ? existing.git_identity
      : undefined;
    return {
      agent: plannedWorker.agent,
      task_id: firstMeaningfulValue(existing?.task_id, resolvedWorker?.task_id, plannedWorker.task_id),
      branch: firstMeaningfulValue(existing?.branch, resolvedWorker?.branch, runtimeWorker?.branch, plannedWorker.branch),
      worktree_path: firstMeaningfulPath(existing?.worktree_path, resolvedWorker?.worktree_path, runtimeWorker?.worktree_path, plannedWorker.worktree_path),
      resource_pool: firstMeaningfulValue(existing?.resource_pool, resolvedWorker?.resource_pool, resolvedWorker?.locked_pool, runtimeWorker?.resource_pool),
      resource_pool_queue: Array.isArray(existing?.resource_pool_queue) && existing.resource_pool_queue.length > 0
        ? existing.resource_pool_queue
        : (resolvedWorker?.resource_pool_queue || []),
      environment_type: firstMeaningfulValue(existing?.environment_type, runtimeWorker?.environment_type),
      environment_path: firstMeaningfulPath(existing?.environment_path, runtimeWorker?.environment_path),
      sync_command: firstMeaningfulCommand(existing?.sync_command, runtimeWorker?.sync_command),
      test_command: firstMeaningfulCommand(existing?.test_command, resolvedWorker?.test_command, runtimeWorker?.test_command),
      submit_strategy: firstMeaningfulCommand(existing?.submit_strategy, runtimeWorker?.submit_strategy),
      git_identity: gitIdentity,
    };
  });

  const extraWorkers = (next.workers || [])
    .filter((worker) => !plannedAgents.has(worker.agent))
    .map((worker) => ({
      ...worker,
      branch: worker.branch || (worker.agent ? deriveBranchName(worker.agent, worker.task_id || worker.agent, worker.task_id || worker.agent) : ''),
      worktree_path: !normalizedText(worker.worktree_path) || isPlaceholderPath(worker.worktree_path) ? deriveWorktreePath(next, worker.agent) : worker.worktree_path,
    }));

  next.workers = [...hydratedPlannedWorkers, ...extraWorkers];
  return normalizeDerivedPaths(next);
}

export function sectionMatchesField(section: ConfigSection, field: string): boolean {
  if (section === 'project') {
    return field.startsWith('project.') && !field.startsWith('project.integration_branch') && !field.startsWith('project.manager_git_identity');
  }
  if (section === 'merge_policy') {
    return field.startsWith('project.integration_branch') || field.startsWith('project.manager_git_identity');
  }
  if (section === 'resource_pools') {
    return field.startsWith('resource_pools.');
  }
  if (section === 'worker_defaults') {
    return field.startsWith('worker_defaults.');
  }
  return field.startsWith('workers[');
}

export function collectSectionIssues(section: ConfigSection, issues: ValidationIssue[]): ValidationIssue[] {
  return issues.filter((issue) => sectionMatchesField(section, issue.field));
}

export function sectionRouteUnavailable(error: unknown, path: string): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return (message.includes(path) && message.includes('status 404')) || message.includes(`unknown api route: ${path}`);
}
