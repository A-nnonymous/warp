import { useEffect, useMemo, useRef, useState } from 'react';
import {
  acknowledgeTeamMailboxMessage, applyTaskAction, confirmTeamCleanup,
  enableSilentMode, fetchState, launchWorkers, saveConfig, saveConfigSection,
  sendA0Message, sendA0Response, sendTeamMailboxMessage, stopAll, stopWorker,
  stopWorkers, updateWorkflowTask, validateConfig, validateConfigSection,
} from './api';
import type {
  A0ConsoleRequest, ConfigSection, ConfigResourcePool, ConfigShape,
  DashboardState, LaunchStrategy, TabKey, ValidationIssue,
} from './types';
import type { SectionStatusMap, WorkerResetScope, MailboxDraft, WorkflowDraft, WorkflowPresetAction } from './lib/local-types';
import { AUTO_REFRESH_MS, A0_CONSOLE_VIEW, DEFAULT_MAILBOX_DRAFT, DEFAULT_WORKFLOW_DRAFT } from './lib/local-types';
import {
  normalizedText, isAutoManagedBlank, isPlaceholderPath, classNames,
  cloneConfig, normalizeConfig, parseQueue, writeClipboard,
  launchStrategyLabel, preferredLaunchProvider, projectReferenceWorkspace,
} from './lib/utils';
import {
  mergeWorkerWithDefaults, resetWorkerDefaultsToA0, resetWorkerOverridesToA0,
  deriveWorktreePath, deriveBranchName, deriveDefaultEnvironmentPath,
  normalizeDerivedPaths, hydrateConfigForA0, buildSectionValue,
  mergeSavedSection, configForProjectSave, buildPlannedWorkers,
  collectSectionIssues, sectionMatchesField, sectionRouteUnavailable,
} from './lib/config';
import { workflowDraftFromTask, workflowDraftFromRequest, pickWorkflowTask } from './lib/workflow';
import { buildAgentRows, buildProgressModel, getLocalValidationIssues, summarizeValidationMessages, formatLaunchErrorMessage } from './lib/data';
import { OverviewTab } from './components/OverviewTab';
import { OperationsTab } from './components/OperationsTab';
import { SettingsTab } from './components/SettingsTab';
import { A0ConsoleView } from './components/A0ConsoleView';

export function App() {
  const isA0ConsoleView = new URLSearchParams(window.location.search).get('view') === A0_CONSOLE_VIEW;
  const [tab, setTab] = useState<TabKey>('overview');
  const [data, setData] = useState<DashboardState | null>(null);
  const [draftConfig, setDraftConfig] = useState<ConfigShape>({ project: {}, providers: {}, resource_pools: {}, worker_defaults: {}, workers: [] });
  const [configDirty, setConfigDirty] = useState(false);
  const [launchStrategy, setLaunchStrategy] = useState<LaunchStrategy>('initial_provider');
  const [launchProvider, setLaunchProvider] = useState('ducc');
  const [launchModel, setLaunchModel] = useState('');
  const [launchDirty, setLaunchDirty] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [actionInFlight, setActionInFlight] = useState(false);
  const [status, setStatus] = useState<{ message: string; error: boolean }>({ message: '', error: false });
  const [backendIssues, setBackendIssues] = useState<ValidationIssue[]>([]);
  const [sectionStatuses, setSectionStatuses] = useState<SectionStatusMap>({});
  const [a0ReplyDrafts, setA0ReplyDrafts] = useState<Record<string, string>>({});
  const [a0Composer, setA0Composer] = useState('');
  const [mailboxDraft, setMailboxDraft] = useState<MailboxDraft>(DEFAULT_MAILBOX_DRAFT);
  const [workflowDraft, setWorkflowDraft] = useState<WorkflowDraft>(DEFAULT_WORKFLOW_DRAFT);
  const [cleanupReleaseListener, setCleanupReleaseListener] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const previousPendingA0Ref = useRef(0);

  const agentRows = useMemo(() => buildAgentRows(data), [data]);
  const progress = useMemo(() => buildProgressModel(data, agentRows), [data, agentRows]);
  const localIssues = useMemo(() => getLocalValidationIssues(draftConfig, data), [draftConfig, data]);
  const allIssues = useMemo(() => [...localIssues, ...backendIssues], [localIssues, backendIssues]);
  const providerOptions = useMemo(() => Object.keys(draftConfig.providers || {}), [draftConfig.providers]);

  const setStampedStatus = (message: string, error = false) => {
    const stamp = new Date().toLocaleTimeString();
    setStatus({ message: `[${stamp}] ${message}`, error });
  };

  const refresh = async (forceStatus = false) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const nextData = await fetchState(controller.signal);
      setData(nextData);
      if (!configDirty) {
        setDraftConfig(hydrateConfigForA0(nextData, cloneConfig(nextData.config)));
        setBackendIssues([]);
        setSectionStatuses({});
      }
      if (!launchDirty) {
        setLaunchStrategy(nextData.launch_policy.default_strategy);
        setLaunchProvider(preferredLaunchProvider(nextData.launch_policy));
        setLaunchModel(nextData.launch_policy.default_model || '');
      }
      if (forceStatus) {
        setStampedStatus(`state refreshed, last event: ${nextData.last_event || 'none'}`);
      }
    } catch (error) {
      if ((error as Error).name !== 'AbortError') {
        setStampedStatus(`refresh failed: ${String(error)}`, true);
      }
    }
  };

  useEffect(() => {
    void refresh(true);
    return () => abortRef.current?.abort();
  }, []);

  useEffect(() => {
    if (!autoRefresh || actionInFlight) {
      return;
    }
    const timer = window.setInterval(() => {
      void refresh(false);
    }, AUTO_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [autoRefresh, actionInFlight, configDirty, launchDirty]);

  useEffect(() => {
    const pendingCount = data?.a0_console?.pending_count || 0;
    if (pendingCount > previousPendingA0Ref.current && document.visibilityState !== 'visible' && 'Notification' in window) {
      if (Notification.permission === 'granted') {
        new Notification('A0 needs input', { body: `${pendingCount} approval request(s) pending in A0 Console.` });
      } else if (Notification.permission === 'default') {
        void Notification.requestPermission();
      }
    }
    previousPendingA0Ref.current = pendingCount;
  }, [data]);

  useEffect(() => {
    if (!data) {
      return;
    }
    setWorkflowDraft((current) => {
      const selectedTask = pickWorkflowTask(data, current.taskId);
      if (!selectedTask) {
        return current.taskId ? { ...DEFAULT_WORKFLOW_DRAFT } : current;
      }
      if (!current.taskId) {
        return workflowDraftFromTask(selectedTask);
      }
      const taskStillExists = (data.backlog.items || []).some((item) => item.id === current.taskId);
      return taskStillExists ? current : workflowDraftFromTask(selectedTask);
    });
  }, [data]);

  const runAction = async (label: string, action: () => Promise<void>) => {
    if (actionInFlight) {
      return;
    }
    setActionInFlight(true);
    setStampedStatus(`${label}...`);
    try {
      await action();
    } catch (error) {
      setStampedStatus(String(error), true);
    } finally {
      setActionInFlight(false);
    }
  };

  const updateConfig = (updater: (current: ConfigShape) => ConfigShape) => {
    setConfigDirty(true);
    setBackendIssues([]);
    setDraftConfig((current) => hydrateConfigForA0(data, normalizeConfig(updater(normalizeConfig(cloneConfig(current))))));
  };

  const refreshStateOnly = async () => {
    const controller = new AbortController();
    const nextData = await fetchState(controller.signal);
    setData(nextData);
    return nextData;
  };

  const onProjectChange = (field: string, value: string) => {
    updateConfig((current) => {
      const next = normalizeConfig(current);
      const previousAutoEnvPath = deriveDefaultEnvironmentPath(current);
      next.project = next.project || {};
      if (field.startsWith('dashboard.')) {
        const key = field.replace('dashboard.', '');
        next.project.dashboard = next.project.dashboard || {};
        if (key === 'port') {
          next.project.dashboard.port = Number(value);
        } else {
          next.project.dashboard.host = value;
        }
      } else if (field === 'repository_name') {
        next.project.repository_name = value;
      } else if (field === 'local_repo_root') {
        next.project.local_repo_root = value;
      } else if (field === 'reference_workspace_root' || field === 'paddle_repo_path') {
        next.project.reference_workspace_root = value;
      }
      const nextAutoEnvPath = deriveDefaultEnvironmentPath(next);
      next.worker_defaults = next.worker_defaults || {};
      if (next.worker_defaults.environment_type !== 'none') {
        const currentEnvironmentPath = normalizedText(next.worker_defaults.environment_path);
        if (!currentEnvironmentPath || isPlaceholderPath(currentEnvironmentPath) || currentEnvironmentPath === previousAutoEnvPath) {
          next.worker_defaults.environment_path = nextAutoEnvPath;
        }
      }
      next.workers = (next.workers || []).map((worker) => ({
        ...worker,
        worktree_path: (() => {
          const previousDerived = deriveWorktreePath(current, worker.agent);
          const nextDerived = deriveWorktreePath(next, worker.agent);
          const currentPath = normalizedText(worker.worktree_path);
          if (!currentPath || isPlaceholderPath(currentPath) || currentPath === previousDerived) {
            return nextDerived || undefined;
          }
          return worker.worktree_path;
        })(),
      }));
      return normalizeDerivedPaths(next);
    });
  };

  const onMergeChange = (field: string, value: string) => {
    updateConfig((current) => {
      const next = normalizeConfig(current);
      next.project = next.project || {};
      if (field === 'integration_branch') {
        next.project.integration_branch = value;
      } else {
        next.project.manager_git_identity = next.project.manager_git_identity || {};
        if (field.endsWith('.name')) {
          next.project.manager_git_identity.name = value;
        } else {
          next.project.manager_git_identity.email = value;
        }
      }
      return next;
    });
  };

  const onPoolChange = (poolName: string, field: keyof ConfigResourcePool, value: string) => {
    updateConfig((current) => {
      const next = normalizeConfig(current);
      next.resource_pools = next.resource_pools || {};
      const existing = next.resource_pools[poolName] || {};
      next.resource_pools[poolName] = {
        ...existing,
        [field]: field === 'priority' ? Number(value) : value,
      };
      return next;
    });
  };

  const onAddPool = () => {
    updateConfig((current) => {
      const next = normalizeConfig(current);
      next.resource_pools = next.resource_pools || {};
      let index = Object.keys(next.resource_pools).length + 1;
      let name = `pool_${index}`;
      while (next.resource_pools[name]) {
        index += 1;
        name = `pool_${index}`;
      }
      next.resource_pools[name] = { priority: 100, provider: providerOptions[0] || '', model: '', api_key: '' };
      return next;
    });
  };

  const onWorkerChange = (index: number, field: string, value: string) => {
    updateConfig((current) => {
      const next = normalizeConfig(current);
      if (index === -1) {
        next.worker_defaults = next.worker_defaults || {};
        if (field === 'worker_defaults.resource_pool_queue') {
          next.worker_defaults.resource_pool_queue = parseQueue(value);
        } else if (field === 'worker_defaults.git_identity.name' || field === 'worker_defaults.git_identity.email') {
          next.worker_defaults.git_identity = next.worker_defaults.git_identity || {};
          if (field.endsWith('.name')) {
            next.worker_defaults.git_identity.name = value;
          } else {
            next.worker_defaults.git_identity.email = value;
          }
        } else {
          const normalizedField = field.replace('worker_defaults.', '');
          (next.worker_defaults as Record<string, unknown>)[normalizedField] = value;
        }
        return next;
      }
      const workers = [...(next.workers || [])];
      const worker = { ...(workers[index] || { agent: `A${index + 1}` }) };
      const previousAgent = String(worker.agent || '');
      const previousTaskId = String(worker.task_id || '');
      const previousBranch = String(worker.branch || '');
      const previousWorktreePath = String(worker.worktree_path || '');
      if (field === 'resource_pool_queue') {
        worker.resource_pool_queue = parseQueue(value);
      } else if (field === 'git_identity.name' || field === 'git_identity.email') {
        worker.git_identity = worker.git_identity || {};
        if (field.endsWith('.name')) {
          worker.git_identity.name = value;
        } else {
          worker.git_identity.email = value;
        }
      } else {
        (worker as Record<string, unknown>)[field] = value;
      }
      if (field === 'agent') {
        const nextAgent = String(value || '');
        const previousDerivedTaskId = previousAgent ? `${previousAgent}-001` : '';
        const nextDerivedTaskId = nextAgent ? `${nextAgent}-001` : '';
        const previousDerivedBranch = previousAgent
          ? deriveBranchName(previousAgent, previousTaskId || previousAgent, previousTaskId || previousAgent)
          : '';
        const nextDerivedBranch = nextAgent
          ? deriveBranchName(nextAgent, worker.task_id || nextAgent, worker.task_id || nextAgent)
          : '';
        const previousDerivedWorktreePath = previousAgent ? deriveWorktreePath(next, previousAgent) : '';
        const nextDerivedWorktreePath = nextAgent ? deriveWorktreePath(next, nextAgent) : '';

        if (!previousTaskId || previousTaskId === previousDerivedTaskId) {
          worker.task_id = nextDerivedTaskId;
        }
        if (!previousBranch || previousBranch === previousDerivedBranch) {
          worker.branch = nextDerivedBranch;
        }
        if (!previousWorktreePath || previousWorktreePath === previousDerivedWorktreePath) {
          worker.worktree_path = nextDerivedWorktreePath || undefined;
        }
      }
      workers[index] = worker;
      next.workers = workers;
      return normalizeDerivedPaths(next);
    });
  };

  const onAddWorker = () => {
    updateConfig((current) => {
      const next = normalizeConfig(current);
      const workers = [...(next.workers || [])];
      const usedAgents = new Set(workers.map((worker) => worker.agent));
      const plannedCandidate = buildPlannedWorkers(data, next).find((worker) => !usedAgents.has(worker.agent));
      if (plannedCandidate) {
        workers.push({
          agent: plannedCandidate.agent,
          task_id: plannedCandidate.task_id,
          resource_pool: '',
          resource_pool_queue: [],
          worktree_path: plannedCandidate.worktree_path || undefined,
          branch: plannedCandidate.branch,
        });
      } else {
        const nextAgent = `A${workers.length + 1}`;
        workers.push({
          agent: nextAgent,
          task_id: `${nextAgent}-001`,
          resource_pool: '',
          resource_pool_queue: [],
          worktree_path: deriveWorktreePath(next, nextAgent) || undefined,
          branch: deriveBranchName(nextAgent, nextAgent, `${nextAgent}-001`),
        });
      }
      next.workers = workers;
      return normalizeDerivedPaths(next);
    });
  };

  const onSyncWorkers = () => {
    updateConfig((current) => {
      const next = normalizeConfig(current);
      const plannedWorkers = buildPlannedWorkers(data, next);
      const existingByAgent = new Map((next.workers || []).map((worker) => [worker.agent, worker]));
      const syncedWorkers = plannedWorkers.map((plannedWorker) => {
        const existing = existingByAgent.get(plannedWorker.agent);
        return {
          agent: plannedWorker.agent,
          task_id: existing?.task_id || plannedWorker.task_id,
          branch: existing?.branch || plannedWorker.branch,
          worktree_path: existing?.worktree_path || plannedWorker.worktree_path,
          resource_pool: existing?.resource_pool || '',
          resource_pool_queue: existing?.resource_pool_queue || [],
          environment_type: existing?.environment_type,
          environment_path: existing?.environment_path,
          sync_command: existing?.sync_command,
          test_command: existing?.test_command,
          submit_strategy: existing?.submit_strategy,
          git_identity: existing?.git_identity,
        };
      });
      const extraWorkers = (next.workers || []).filter((worker) => !plannedWorkers.some((plannedWorker) => plannedWorker.agent === worker.agent));
      next.workers = [...syncedWorkers, ...extraWorkers];
      return normalizeDerivedPaths(next);
    });
    setStampedStatus('worker list synced from backlog and runtime plan');
  };

  const onAutoFillWorktreePaths = () => {
    updateConfig((current) => {
      const next = normalizeConfig(current);
      next.workers = (next.workers || []).map((worker) => ({
        ...worker,
        worktree_path: !normalizedText(worker.worktree_path) || isPlaceholderPath(worker.worktree_path) ? (deriveWorktreePath(next, worker.agent) || undefined) : worker.worktree_path,
      }));
      return normalizeDerivedPaths(next);
    });
    setStampedStatus('missing worktree paths filled from local repo root');
  };

  const persistDirtyDraft = async () => {
    const effectiveDraft = normalizeDerivedPaths(draftConfig);
    const validation = await validateConfig(effectiveDraft);
    setBackendIssues(validation.validation_issues || []);
    if (!validation.ok) {
      throw new Error(`Current settings cannot be launched yet: ${summarizeValidationMessages(validation.validation_issues || [], validation.launch_blockers || [])}`);
    }
    await saveConfig(effectiveDraft);
    const nextData = await refreshStateOnly();
    setDraftConfig(hydrateConfigForA0(nextData, cloneConfig(nextData.config)));
    setConfigDirty(false);
    return nextData;
  };

  const onResetWorkerDefaults = () => {
    updateConfig((current) => ({
      ...normalizeConfig(current),
      worker_defaults: resetWorkerDefaultsToA0(current.worker_defaults),
    }));
    setStampedStatus('worker defaults reset to A0-managed defaults');
  };

  const onResetWorkerOverrides = (index: number, scope: WorkerResetScope = 'all') => {
    updateConfig((current) => {
      const next = normalizeConfig(current);
      const workers = [...(next.workers || [])];
      if (!workers[index]) {
        return next;
      }
      workers[index] = resetWorkerOverridesToA0(workers[index], scope);
      next.workers = workers;
      return next;
    });
    const message = scope === 'all'
      ? 'worker overrides reset to A0 plan'
      : scope === 'routing'
        ? 'worker routing overrides cleared'
        : 'worker runtime overrides cleared';
    setStampedStatus(message);
  };

  const onValidateSection = (section: ConfigSection) => void runAction(`validating ${section}`, async () => {
    const effectiveDraft = section === 'project'
      ? configForProjectSave(data?.config, draftConfig)
      : normalizeDerivedPaths(draftConfig);
    const sectionValue = buildSectionValue(effectiveDraft, section);
    let validation;
    let usedFullConfigFallback = section === 'project';
    try {
      validation = usedFullConfigFallback ? await validateConfig(effectiveDraft) : await validateConfigSection(section, sectionValue);
    } catch (error) {
      if (!sectionRouteUnavailable(error, '/api/config/validate-section')) {
        throw error;
      }
      validation = await validateConfig(effectiveDraft);
      usedFullConfigFallback = true;
    }
    const nextIssues = usedFullConfigFallback
      ? collectSectionIssues(section, validation.validation_issues)
      : validation.validation_issues;
    const blockingOtherIssues = usedFullConfigFallback
      ? validation.validation_issues.filter((issue) => !sectionMatchesField(section, issue.field)).length
      : 0;
    setBackendIssues((current) => [
      ...current.filter((issue) => usedFullConfigFallback || !sectionMatchesField(section, issue.field)),
      ...(usedFullConfigFallback ? validation.validation_issues : nextIssues),
    ]);
    setSectionStatuses((current) => ({
      ...current,
      [section]: {
        message: validation.ok
          ? (usedFullConfigFallback ? 'validated via full-config fallback' : 'validated')
          : usedFullConfigFallback && blockingOtherIssues > 0
            ? `${nextIssues.length} section issue(s), ${blockingOtherIssues} other blocker(s)`
            : `${nextIssues.length} issue(s)`,
        error: !validation.ok,
      },
    }));
    setStampedStatus(
      validation.ok
        ? `${section} validated${usedFullConfigFallback ? ' via full-config fallback' : ''}`
        : `${section} has validation issues`,
      !validation.ok,
    );
  });

  const onSaveSection = (section: ConfigSection) => void runAction(`saving ${section}`, async () => {
    const sectionLocalIssues = collectSectionIssues(section, localIssues);
    if (sectionLocalIssues.length > 0) {
      setSectionStatuses((current) => ({
        ...current,
        [section]: { message: `${sectionLocalIssues.length} local issue(s)`, error: true },
      }));
      setStampedStatus(`${section} contains local validation issues`, true);
      return;
    }
    const effectiveDraft = section === 'project'
      ? configForProjectSave(data?.config, draftConfig)
      : normalizeDerivedPaths(draftConfig);
    const sectionValue = buildSectionValue(effectiveDraft, section);
    let validation;
    let usedFullConfigFallback = section === 'project';
    try {
      validation = usedFullConfigFallback ? await validateConfig(effectiveDraft) : await validateConfigSection(section, sectionValue);
    } catch (error) {
      if (!sectionRouteUnavailable(error, '/api/config/validate-section')) {
        throw error;
      }
      validation = await validateConfig(effectiveDraft);
      usedFullConfigFallback = true;
    }
    const validationIssues = usedFullConfigFallback
      ? validation.validation_issues
      : validation.validation_issues;
    const sectionIssues = collectSectionIssues(section, validationIssues);
    const blockingOtherIssues = usedFullConfigFallback
      ? validationIssues.filter((issue) => !sectionMatchesField(section, issue.field)).length
      : 0;
    if (!validation.ok) {
      setBackendIssues((current) => [
        ...current.filter((issue) => usedFullConfigFallback || !sectionMatchesField(section, issue.field)),
        ...validationIssues,
      ]);
      setSectionStatuses((current) => ({
        ...current,
        [section]: {
          message: usedFullConfigFallback && blockingOtherIssues > 0
            ? `${sectionIssues.length} section issue(s), ${blockingOtherIssues} other blocker(s)`
            : `${sectionIssues.length} issue(s)`,
          error: true,
        },
      }));
      setStampedStatus(`${section} rejected by validation`, true);
      return;
    }
    const response = usedFullConfigFallback
      ? await saveConfig(effectiveDraft)
      : await saveConfigSection(section, sectionValue);
    setBackendIssues((current) => current.filter((issue) => usedFullConfigFallback || !sectionMatchesField(section, issue.field)));
    setSectionStatuses((current) => ({
      ...current,
      [section]: { message: usedFullConfigFallback ? 'saved via full-config fallback' : 'saved', error: false },
    }));
    const nextData = await refreshStateOnly();
    setDraftConfig((current) => {
      const mergedDraft = hydrateConfigForA0(nextData, mergeSavedSection(current, nextData.config, section));
      setConfigDirty(JSON.stringify(normalizeConfig(mergedDraft)) !== JSON.stringify(normalizeConfig(nextData.config)));
      return mergedDraft;
    });
    setStampedStatus(
      `${section} saved${usedFullConfigFallback ? ' via full-config fallback' : ''}: ${response.validation_errors.length} note(s), ${response.launch_blockers.length} blocker(s)`,
    );
  });

  const onLaunch = (restart: boolean) => void runAction(restart ? 'restarting workers' : 'launching workers', async () => {
    try {
      if (configDirty) {
        await persistDirtyDraft();
      }
      const response = await launchWorkers(restart, {
        strategy: launchStrategy,
        provider: launchStrategy === 'elastic' ? undefined : launchProvider,
        model: launchStrategy === 'selected_model' ? launchModel : undefined,
      });
      setStampedStatus(
        `launch complete (${launchStrategyLabel(response.launch_policy?.strategy || launchStrategy)}): ${(response.launched || []).length} launched, ${(response.failures || []).length} failures`,
        !response.ok,
      );
    } catch (error) {
      throw new Error(formatLaunchErrorMessage(error));
    } finally {
      await refresh(true);
    }
  });

  const onStopWorkers = () => void runAction('stopping workers', async () => {
    const response = await stopWorkers();
    setStampedStatus(`stopped workers: ${response.stopped.join(', ') || 'none'}`);
    await refresh(true);
  });

  const onStopAll = () => void runAction('stopping listener and workers', async () => {
    const response = await stopAll();
    setStampedStatus(
      response.listener_released
        ? `stop all requested: ${response.stopped_workers?.length || 0} worker(s) stopped, port ${response.listener_port} released`
        : `stop all requested${response.warning ? `: ${response.warning}` : ''}`,
      !response.listener_released,
    );
  });

  const onSilentMode = () => void runAction('entering silent mode', async () => {
    const response = await enableSilentMode();
    setStampedStatus(`silent mode enabled: listener on port ${response.listener_port} closed`);
  });

  const onCopy = (mode: 'serve' | 'up') => void runAction(`copying ${mode} command`, async () => {
    if (!data?.commands[mode]) {
      throw new Error(`no ${mode} command available`);
    }
    await writeClipboard(data.commands[mode]);
    setStampedStatus(`${mode} command copied`);
  });

  const onOpenA0Console = () => {
    window.open(`/?view=${A0_CONSOLE_VIEW}`, 'a0-console', 'width=860,height=960');
  };

  const onA0ReplyChange = (requestId: string, value: string) => {
    setA0ReplyDrafts((current) => ({ ...current, [requestId]: value }));
  };

  const onA0Reply = (item: A0ConsoleRequest, action: string) => void runAction(`sending A0 ${action}`, async () => {
    const requestId = item.id;
    const message = String(a0ReplyDrafts[requestId] || '').trim() || `${action} by A0`;
    if (item.request_type === 'plan_review' && item.task_id) {
      await applyTaskAction(item.task_id, action === 'approve' ? 'approve_plan' : 'reject_plan', 'A0', message);
    } else if (item.request_type === 'task_review' && item.task_id) {
      await applyTaskAction(item.task_id, action === 'approve' ? 'complete' : 'reopen', 'A0', message);
    } else {
      await sendA0Response(requestId, message, action);
    }
    setA0ReplyDrafts((current) => ({ ...current, [requestId]: '' }));
    await refresh(true);
  });

  const onA0MailboxAck = (messageId: string, ackState: string) => void runAction(`marking mailbox item ${ackState}`, async () => {
    await acknowledgeTeamMailboxMessage(messageId, ackState);
    await refresh(true);
  });

  const onMailboxDraftChange = (field: keyof MailboxDraft, value: string) => {
    setMailboxDraft((current) => ({ ...current, [field]: value }));
  };

  const onWorkflowDraftChange = (field: keyof WorkflowDraft, value: string) => {
    if (field === 'taskId') {
      const selectedTask = pickWorkflowTask(data, value);
      setWorkflowDraft(selectedTask ? workflowDraftFromTask(selectedTask) : { ...DEFAULT_WORKFLOW_DRAFT, taskId: value });
      return;
    }
    setWorkflowDraft((current) => ({ ...current, [field]: value }));
  };

  const onPrepareWorkflow = (item: A0ConsoleRequest, action: WorkflowPresetAction) => {
    if (!data) {
      return;
    }
    const nextDraft = workflowDraftFromRequest(data, item, action);
    setWorkflowDraft(nextDraft);
    const taskLabel = nextDraft.taskId || item.task_id || item.id;
    setStampedStatus(`${action} preset loaded for ${taskLabel}`);
    window.requestAnimationFrame(() => {
      document.getElementById('workflow-replan-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  };

  const onSendMailboxMessage = () => void runAction('sending mailbox message', async () => {
    const payload = {
      from: mailboxDraft.from.trim(),
      to: mailboxDraft.to.trim(),
      topic: mailboxDraft.topic.trim() || 'status_note',
      scope: mailboxDraft.scope.trim() || 'direct',
      body: mailboxDraft.body.trim(),
      related_task_ids: parseQueue(mailboxDraft.relatedTaskIds),
    };
    if (!payload.from || !payload.to || !payload.body) {
      throw new Error('mailbox sender, recipient, and body are required');
    }
    await sendTeamMailboxMessage(payload);
    setMailboxDraft((current) => ({ ...current, relatedTaskIds: '', body: '' }));
    await refresh(true);
  });

  const onApplyWorkflowUpdate = () => void runAction('updating workflow plan', async () => {
    if (!workflowDraft.taskId) {
      throw new Error('task selection is required');
    }
    const updates = {
      title: workflowDraft.title.trim(),
      owner: workflowDraft.owner.trim(),
      claimed_by: workflowDraft.claimedBy.trim(),
      status: workflowDraft.status.trim(),
      claim_state: workflowDraft.claimState.trim(),
      gate: workflowDraft.gate.trim(),
      priority: workflowDraft.priority.trim(),
      dependencies: parseQueue(workflowDraft.dependencies),
      plan_required: workflowDraft.planRequired === 'yes',
      plan_state: workflowDraft.planState.trim(),
      plan_summary: workflowDraft.planSummary.trim(),
      claim_note: workflowDraft.claimNote.trim(),
      review_note: workflowDraft.reviewNote.trim(),
    };
    const response = await updateWorkflowTask(workflowDraft.taskId, updates, workflowDraft.managerNote.trim());
    setWorkflowDraft(workflowDraftFromTask(response.task));
    setStampedStatus(`workflow updated for ${response.task.id}`);
    await refreshStateOnly();
  });

  const onStopWorker = (agent: string) => void runAction(`shutting down ${agent}`, async () => {
    await stopWorker(agent, 'A0 requested clean worker shutdown for cleanup.');
    await refresh(true);
  });

  const onConfirmCleanup = () => void runAction('confirming cleanup readiness', async () => {
    const response = await confirmTeamCleanup('Cleanup gate passed; session can now be released safely.', cleanupReleaseListener);
    if (response.listener_release_requested || response.listener_released) {
      setAutoRefresh(false);
      setData((current) => current ? {
        ...current,
        mode: { ...current.mode, listener_active: false },
        cleanup: { ...response.cleanup, listener_active: false },
      } : current);
      setStampedStatus(`cleanup confirmed; listener release ${response.listener_released ? 'already completed' : 'scheduled'} on port ${response.listener_port || 'unknown'}`);
      return;
    }
    await refresh(true);
  });

  const onSendA0Message = () => void runAction('sending message to A0', async () => {
    const message = a0Composer.trim();
    if (!message) {
      throw new Error('message is required');
    }
    await sendA0Message(message);
    setA0Composer('');
    await refresh(true);
  });

  const topMeta = data ? [
    { label: 'Startup', value: data.mode.state || 'configured' },
    { label: 'Listener', value: data.mode.listener_active ? 'active' : 'silent' },
    { label: 'Launch', value: data.launch_blockers.length ? `${data.launch_blockers.length} blocker(s)` : 'ready' },
    { label: 'Launch Mode', value: launchStrategyLabel(launchStrategy) },
    { label: 'Config', value: data.mode.config_path || 'unknown' },
    { label: 'Updated', value: data.updated_at || 'unknown' },
  ] : [];

  if (data && isA0ConsoleView) {
    return (
      <div>
        <header>
          <div className="hero">
            <div>
              <div className="hero-badge">Manager channel</div>
              <h1>A0 Console</h1>
              <p className="small tagline">Focused communication window for manager approvals, unblock decisions, and resume notes.</p>
            </div>
          </div>
        </header>
        <main>
          <section className="card">
            <div className={classNames('status', status.error && 'error')}>{status.message}</div>
          </section>
          <A0ConsoleView
            data={data}
            standalone
            replyDrafts={a0ReplyDrafts}
            composer={a0Composer}
            workflowDraft={workflowDraft}
            onReplyChange={onA0ReplyChange}
            onComposerChange={setA0Composer}
            onWorkflowDraftChange={onWorkflowDraftChange}
            onReply={onA0Reply}
            onSendMessage={onSendA0Message}
            onMailboxAck={onA0MailboxAck}
            onApplyWorkflowUpdate={onApplyWorkflowUpdate}
            onPrepareWorkflow={onPrepareWorkflow}
          />
        </main>
      </div>
    );
  }

  return (
    <div>
      <header>
        <div className="hero">
          <div>
            <div className="hero-badge">FP8 delivery orchestration</div>
            <h1>warp control plane</h1>
            <p className="small tagline">Cold-start by default, fire-and-forget serving, editable settings forms, strict validation, and an explicit silent listener mode.</p>
          </div>
        </div>
      </header>
      <main>
        <section className="card">
          <div className="toolbar">
            <div className="toolbar-group">
              <button disabled={actionInFlight} onClick={() => onLaunch(false)}>Launch</button>
              <button className="secondary" disabled={actionInFlight} onClick={() => onLaunch(true)}>Restart</button>
              <button className="danger" disabled={actionInFlight} onClick={onStopWorkers}>Stop Agents</button>
              <button className="ghost danger-outline" disabled={actionInFlight} onClick={onSilentMode}>Silent Mode</button>
              <button className="danger ghost-danger" disabled={actionInFlight} onClick={onStopAll}>Stop All</button>
              <button className="ghost" disabled={actionInFlight} onClick={() => void refresh(true)}>Refresh</button>
            </div>
            <div className="toolbar-group">
              {data ? (
                <>
                  <label className="field field-compact">
                    <span className="field-label">Launch Mode</span>
                    <select
                      className="field-input compact-input"
                      value={launchStrategy}
                      onChange={(event) => {
                        setLaunchDirty(true);
                        setLaunchStrategy(event.target.value as LaunchStrategy);
                        if (event.target.value === 'initial_provider') {
                          setLaunchProvider(preferredLaunchProvider(data.launch_policy));
                        }
                      }}
                    >
                      {data.launch_policy.available_strategies.map((strategy) => (
                        <option key={strategy} value={strategy}>{launchStrategyLabel(strategy)}</option>
                      ))}
                    </select>
                  </label>
                  {launchStrategy !== 'elastic' ? (
                    <label className="field field-compact">
                      <span className="field-label">Provider</span>
                      <select
                        className="field-input compact-input"
                        value={launchProvider}
                        disabled={launchStrategy === 'initial_provider'}
                        onChange={(event) => {
                          setLaunchDirty(true);
                          setLaunchProvider(event.target.value);
                        }}
                      >
                        {data.launch_policy.available_providers.map((provider) => (
                          <option key={provider} value={provider}>{provider}</option>
                        ))}
                      </select>
                    </label>
                  ) : null}
                  {launchStrategy === 'selected_model' ? (
                    <label className="field field-compact field-compact-wide">
                      <span className="field-label">Model</span>
                      <input
                        className="field-input compact-input"
                        value={launchModel}
                        placeholder={data.launch_policy.default_model || 'model id'}
                        onChange={(event) => {
                          setLaunchDirty(true);
                          setLaunchModel(event.target.value);
                        }}
                      />
                    </label>
                  ) : null}
                </>
              ) : null}
              <button className="ghost" disabled={actionInFlight} onClick={() => onCopy('serve')}>Copy Serve</button>
              <button className="ghost" disabled={actionInFlight} onClick={() => onCopy('up')}>Copy Up</button>
              <button className="ghost" disabled={actionInFlight} onClick={onOpenA0Console}>A0 Console</button>
              <label className="toggle"><input type="checkbox" checked={autoRefresh} onChange={(event) => setAutoRefresh(event.target.checked)} /> Auto refresh</label>
            </div>
          </div>
          <div className={classNames('status', status.error && 'error')}>{status.message}</div>
        </section>

        <section className="card">
          <div className="toolbar">
            <div className="tab-nav" role="tablist" aria-label="Dashboard sections">
              {(['overview', 'operations', 'settings'] as TabKey[]).map((name) => (
                <button key={name} className={classNames('nav-button', tab === name && 'active')} onClick={() => setTab(name)}>{name[0].toUpperCase() + name.slice(1)}</button>
              ))}
            </div>
            <div className="pill-row">
              {topMeta.map((item) => <div key={item.label} className="key-pair"><span className="muted">{item.label}</span><strong>{item.value}</strong></div>)}
            </div>
          </div>
        </section>

        {data ? (
          tab === 'overview'
            ? <OverviewTab data={data} agentRows={agentRows} progress={progress} onOpenA0Console={onOpenA0Console} />
            : tab === 'operations'
              ? <OperationsTab data={data} mailboxDraft={mailboxDraft} workflowDraft={workflowDraft} cleanupReleaseListener={cleanupReleaseListener} onMailboxDraftChange={onMailboxDraftChange} onWorkflowDraftChange={onWorkflowDraftChange} onSendMailboxMessage={onSendMailboxMessage} onApplyWorkflowUpdate={onApplyWorkflowUpdate} onStopWorker={onStopWorker} onCleanupReleaseChange={setCleanupReleaseListener} onConfirmCleanup={onConfirmCleanup} actionInFlight={actionInFlight} />
              : <SettingsTab
                  data={data}
                  draftConfig={draftConfig}
                  providerOptions={providerOptions}
                  allIssues={allIssues}
                  sectionStatuses={sectionStatuses}
                  onProjectChange={onProjectChange}
                  onMergeChange={onMergeChange}
                  onPoolChange={onPoolChange}
                  onAddPool={onAddPool}
                  onWorkerChange={onWorkerChange}
                  onAddWorker={onAddWorker}
                  onValidateSection={onValidateSection}
                  onSaveSection={onSaveSection}
                  onSyncWorkers={onSyncWorkers}
                  onAutoFillWorktreePaths={onAutoFillWorktreePaths}
                  onResetWorkerDefaults={onResetWorkerDefaults}
                  onResetWorkerOverrides={onResetWorkerOverrides}
                />
        ) : (
          <section className="card"><div className="small muted">Loading dashboard state...</div></section>
        )}
      </main>
    </div>
  );
}
