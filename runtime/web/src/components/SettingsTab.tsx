import type { SectionStatusMap, WorkerResetScope } from '../lib/local-types';
import type {
  ConfigResourcePool,
  ConfigSection,
  ConfigShape,
  DashboardState,
  ValidationIssue,
} from '../types';
import { stringifyQueue } from '../lib/utils';
import { projectReferenceWorkspace } from '../lib/utils';
import {
  buildPlannedWorkers,
  buildResolvedWorkerMap,
  collectSectionIssues,
  workerPlanView,
} from '../lib/config';
import { buildIssueMap } from '../lib/data';
import { Field, SelectField, SectionIssueList, SectionHeader } from './shared';
import { AutomationSummary } from './cards';

export function SettingsTab({
  data,
  draftConfig,
  providerOptions,
  allIssues,
  sectionStatuses,
  onProjectChange,
  onMergeChange,
  onPoolChange,
  onAddPool,
  onWorkerChange,
  onAddWorker,
  onValidateSection,
  onSaveSection,
  onSyncWorkers,
  onAutoFillWorktreePaths,
  onResetWorkerDefaults,
  onResetWorkerOverrides,
}: {
  data: DashboardState;
  draftConfig: ConfigShape;
  providerOptions: string[];
  allIssues: ValidationIssue[];
  sectionStatuses: SectionStatusMap;
  onProjectChange: (field: string, value: string) => void;
  onMergeChange: (field: string, value: string) => void;
  onPoolChange: (poolName: string, field: keyof ConfigResourcePool, value: string) => void;
  onAddPool: () => void;
  onWorkerChange: (index: number, field: string, value: string) => void;
  onAddWorker: () => void;
  onValidateSection: (section: ConfigSection) => void;
  onSaveSection: (section: ConfigSection) => void;
  onSyncWorkers: () => void;
  onAutoFillWorktreePaths: () => void;
  onResetWorkerDefaults: () => void;
  onResetWorkerOverrides: (index: number, scope?: WorkerResetScope) => void;
}) {
  const project = draftConfig.project || {};
  const dashboard = project.dashboard || {};
  const pools = draftConfig.resource_pools || {};
  const workerDefaults = draftConfig.worker_defaults || {};
  const workers = draftConfig.workers || [];
  const plannedWorkers = buildPlannedWorkers(data, draftConfig);
  const resolvedByAgent = buildResolvedWorkerMap(data);
  const issues = buildIssueMap(allIssues);
  return (
    <div className="tab-body">
      <section className="card">
        <div className="page-header">
          <div>
            <h2>Settings</h2>
            <p className="small">A0 now auto-hydrates the worker roster, branch proposals, worktree paths, and shared defaults. You should mostly verify project paths, pool routing, and true exceptions.</p>
          </div>
        </div>
        <div className="settings-stack">
          <section className="helper-card settings-card settings-card-wide">
            <SectionHeader title="Resource Pools" section="resource_pools" status={sectionStatuses.resource_pools} onValidate={onValidateSection} onSave={onSaveSection} action={<button className="ghost" type="button" onClick={onAddPool}>Add Pool</button>} />
            <SectionIssueList issues={collectSectionIssues('resource_pools', allIssues)} />
            <div className="pool-strip">
              {Object.entries(pools).map(([poolName, pool]) => (
                <div key={poolName} className="subcard pool-card">
                  <div className="subcard-title">{poolName}</div>
                  <div className="field-grid">
                    <SelectField label="Provider" value={String(pool.provider || '')} onChange={(value) => onPoolChange(poolName, 'provider', value)} issues={issues[`resource_pools.${poolName}.provider`]} options={providerOptions} />
                    <Field label="Model" value={String(pool.model || '')} onChange={(value) => onPoolChange(poolName, 'model', value)} issues={issues[`resource_pools.${poolName}.model`]} />
                    <Field label="Priority" type="number" value={Number(pool.priority ?? 100)} onChange={(value) => onPoolChange(poolName, 'priority', value)} issues={issues[`resource_pools.${poolName}.priority`]} />
                    <Field label="API Key" value={String(pool.api_key || '')} onChange={(value) => onPoolChange(poolName, 'api_key', value)} />
                  </div>
                </div>
              ))}
            </div>
          </section>

          <div className="settings-duo">
            <section className="helper-card settings-card">
            <SectionHeader title="Project" section="project" status={sectionStatuses.project} onValidate={onValidateSection} onSave={onSaveSection} />
            <SectionIssueList issues={collectSectionIssues('project', allIssues)} />
            <div className="field-grid">
              <Field label="Repository" value={project.repository_name || ''} onChange={(value) => onProjectChange('repository_name', value)} issues={issues['project.repository_name']} />
              <Field label="Local Repo Root" value={project.local_repo_root || ''} onChange={(value) => onProjectChange('local_repo_root', value)} issues={issues['project.local_repo_root']} />
              <Field label="Reference Workspace" value={projectReferenceWorkspace(project)} onChange={(value) => onProjectChange('reference_workspace_root', value)} issues={issues['project.reference_workspace_root']} helpText="Optional shared reference repo or baseline workspace for task guidance." />
              <Field label="Dashboard Host" value={dashboard.host || ''} onChange={(value) => onProjectChange('dashboard.host', value)} issues={issues['project.dashboard.host']} />
              <Field label="Dashboard Port" type="number" value={dashboard.port || 8233} onChange={(value) => onProjectChange('dashboard.port', value)} issues={issues['project.dashboard.port']} />
            </div>
          </section>

            <section className="helper-card settings-card">
            <SectionHeader title="Merge Policy" section="merge_policy" status={sectionStatuses.merge_policy} onValidate={onValidateSection} onSave={onSaveSection} />
            <SectionIssueList issues={collectSectionIssues('merge_policy', allIssues)} />
            <div className="field-grid">
              <Field label="Integration Branch" value={project.integration_branch || project.base_branch || ''} onChange={(value) => onMergeChange('integration_branch', value)} issues={issues['project.integration_branch']} />
              <Field label="Manager Name" value={project.manager_git_identity?.name || ''} onChange={(value) => onMergeChange('manager_git_identity.name', value)} />
              <Field label="Manager Email" value={project.manager_git_identity?.email || ''} onChange={(value) => onMergeChange('manager_git_identity.email', value)} />
            </div>
          </section>
          </div>

          <section className="helper-card settings-card settings-card-wide">
            <SectionHeader
              title="Worker Defaults"
              section="worker_defaults"
              status={sectionStatuses.worker_defaults}
              onValidate={onValidateSection}
              onSave={onSaveSection}
              subtitle="Common defaults are the few knobs you may actually standardize across workers. Advanced defaults are fallback overrides for exceptional environments."
              action={<button className="ghost" type="button" onClick={onResetWorkerDefaults}>Reset to A0</button>}
            />
            <SectionIssueList issues={collectSectionIssues('worker_defaults', allIssues)} />
            <p className="small muted">These values apply to every worker unless a row below overrides them. Blank fields are auto-filled from runtime conventions or sensible defaults where possible, so the main path should stay sparse.</p>
            <div className="field-grid compact-field-grid">
              <Field label="Default Pool" value={workerDefaults.resource_pool || ''} onChange={(value) => onWorkerChange(-1, 'worker_defaults.resource_pool', value)} issues={issues['worker_defaults.resource_pool']} helpText="Leave blank to rely on pool queue or per-worker overrides." />
              <Field label="Default Pool Queue" value={stringifyQueue(workerDefaults.resource_pool_queue)} onChange={(value) => onWorkerChange(-1, 'worker_defaults.resource_pool_queue', value)} issues={issues['worker_defaults.resource_pool_queue']} placeholder="ducc_pool" />
              <SelectField label="Default Environment" value={workerDefaults.environment_type || 'uv'} onChange={(value) => onWorkerChange(-1, 'worker_defaults.environment_type', value)} options={['uv', 'venv', 'none']} />
              <Field label="Default Environment Path" value={workerDefaults.environment_path || ''} onChange={(value) => onWorkerChange(-1, 'worker_defaults.environment_path', value)} issues={issues['worker_defaults.environment_path']} />
            </div>
            <details className="advanced-panel defaults-panel">
              <summary>Advanced defaults</summary>
              <div className="field-grid advanced-grid">
                <Field label="Default Sync Command" value={workerDefaults.sync_command || ''} onChange={(value) => onWorkerChange(-1, 'worker_defaults.sync_command', value)} helpText="Leave blank to let A0 follow the environment convention." />
                <Field label="Default Test Command" value={workerDefaults.test_command || ''} onChange={(value) => onWorkerChange(-1, 'worker_defaults.test_command', value)} issues={issues['worker_defaults.test_command']} helpText="Leave blank to let task policy choose per worker." />
                <Field label="Default Submit Strategy" value={workerDefaults.submit_strategy || ''} onChange={(value) => onWorkerChange(-1, 'worker_defaults.submit_strategy', value)} issues={issues['worker_defaults.submit_strategy']} helpText="Leave blank to keep A0's standard handoff flow." />
                <Field label="Default Git Name" value={workerDefaults.git_identity?.name || ''} onChange={(value) => onWorkerChange(-1, 'worker_defaults.git_identity.name', value)} issues={issues['worker_defaults.git_identity.name']} />
                <Field label="Default Git Email" value={workerDefaults.git_identity?.email || ''} onChange={(value) => onWorkerChange(-1, 'worker_defaults.git_identity.email', value)} issues={issues['worker_defaults.git_identity.email']} />
              </div>
            </details>
          </section>

          <AutomationSummary draftConfig={draftConfig} data={data} />

          <section className="helper-card settings-card settings-card-wide">
            <SectionHeader
              title="Worker Config"
              section="workers"
              status={sectionStatuses.workers}
              onValidate={onValidateSection}
              onSave={onSaveSection}
              action={
                <>
                  <button className="ghost" type="button" onClick={onSyncWorkers}>Sync From Plan</button>
                  <button className="ghost" type="button" onClick={onAutoFillWorktreePaths}>Auto Paths</button>
                  <button className="ghost" type="button" onClick={onAddWorker}>Add Worker</button>
                </>
              }
            />
            <SectionIssueList issues={collectSectionIssues('workers', allIssues)} />
            <p className="small muted">Detected workers from backlog/runtime: {plannedWorkers.map((item) => item.agent).join(', ') || 'none'}. A0 plan is the derived execution target. Any filled override below becomes a human-pinned exception; use Reset to A0 to clear those pins and fall back to the plan.</p>
            <div className="worker-grid">
              {workers.map((worker, index) => (
                <div key={`${worker.agent || 'worker'}-${index}`} className="subcard">
                  {(() => {
                    const resolved = resolvedByAgent.get(worker.agent || '');
                    const planned = workerPlanView(worker, draftConfig, data, plannedWorkers);
                    const recommendation = planned.poolReason || '';
                    const suggestedTest = planned.suggestedTestCommand || '';
                    return (
                      <>
                  <div className="subcard-title worker-card-title-row">
                    <span>{worker.agent || `Worker ${index + 1}`}</span>
                    <button className="ghost" type="button" onClick={() => onResetWorkerOverrides(index)}>Reset to A0</button>
                  </div>
                  {recommendation ? <p className="small muted">{recommendation}</p> : null}
                  <div className="plan-grid">
                    <div className="plan-row"><span className="muted">Task</span><strong>{planned.taskId || 'A0 will assign'}</strong></div>
                    <div className="plan-row"><span className="muted">Type</span><strong>{planned.taskType || 'default'}</strong></div>
                    <div className="plan-row"><span className="muted">Branch</span><strong>{planned.branch || 'A0 will derive'}</strong></div>
                    <div className="plan-row"><span className="muted">Worktree</span><strong>{planned.worktreePath || 'derived from Local Repo Root'}</strong></div>
                    <div className="plan-row"><span className="muted">Pool</span><strong>{planned.lockedPool || planned.recommendedPool || 'A0 routing'}</strong></div>
                    <div className="plan-row"><span className="muted">Test</span><strong>{planned.testCommand || suggestedTest || 'A0 default'}</strong></div>
                  </div>
                  <div className="field-grid compact-field-grid">
                    <Field label="Agent" value={worker.agent || ''} onChange={(value) => onWorkerChange(index, 'agent', value)} issues={issues[`workers[${index}].agent`]} />
                    <Field label="Pool Override" value={worker.resource_pool || ''} onChange={(value) => onWorkerChange(index, 'resource_pool', value)} issues={issues[`workers[${index}].resource_pool`]} helpText={resolved?.locked_pool ? `A0 lock: ${resolved.locked_pool}` : resolved?.recommended_pool ? `A0 recommends: ${resolved.recommended_pool}` : (workerDefaults.resource_pool ? `Default: ${workerDefaults.resource_pool}` : 'Blank means inherit A0 routing.')} />
                  </div>
                  <details className="advanced-panel">
                    <summary>Advanced overrides</summary>
                    <div className="override-toolbar">
                      <button className="ghost" type="button" onClick={() => onResetWorkerOverrides(index, 'routing')}>Reset routing</button>
                      <button className="ghost" type="button" onClick={() => onResetWorkerOverrides(index, 'runtime')}>Reset runtime</button>
                    </div>
                    <div className="field-grid advanced-grid">
                      <Field label="Task ID Override" value={worker.task_id || ''} onChange={(value) => onWorkerChange(index, 'task_id', value)} helpText={planned.taskId ? `A0 plan: ${planned.taskId}` : 'Leave blank to inherit A0 task assignment.'} />
                      <Field label="Branch Override" value={worker.branch || ''} onChange={(value) => onWorkerChange(index, 'branch', value)} issues={issues[`workers[${index}].branch`]} helpText={planned.branch ? `A0 plan: ${planned.branch}` : 'Leave blank to let A0 derive the branch.'} />
                      <Field label="Worktree Path Override" value={worker.worktree_path || ''} onChange={(value) => onWorkerChange(index, 'worktree_path', value)} issues={issues[`workers[${index}].worktree_path`]} helpText={planned.worktreePath ? `A0 plan: ${planned.worktreePath}` : 'Leave blank to derive from Local Repo Root.'} />
                      <Field label="Queue Override" value={stringifyQueue(worker.resource_pool_queue)} onChange={(value) => onWorkerChange(index, 'resource_pool_queue', value)} issues={issues[`workers[${index}].resource_pool_queue`]} placeholder="pool_a, pool_b" helpText={resolved?.resource_pool_queue?.length ? `A0 order: ${stringifyQueue(resolved.resource_pool_queue)}` : (workerDefaults.resource_pool_queue?.length ? `Default: ${stringifyQueue(workerDefaults.resource_pool_queue)}` : 'Blank means inherit A0 queue.')} />
                      <SelectField label="Environment Type" value={worker.environment_type || ''} onChange={(value) => onWorkerChange(index, 'environment_type', value)} options={['uv', 'venv', 'none']} />
                      <Field label="Environment Path" value={worker.environment_path || ''} onChange={(value) => onWorkerChange(index, 'environment_path', value)} issues={issues[`workers[${index}].environment_path`]} helpText={workerDefaults.environment_path ? `Default: ${workerDefaults.environment_path}` : undefined} />
                      <Field label="Sync Command" value={worker.sync_command || ''} onChange={(value) => onWorkerChange(index, 'sync_command', value)} helpText={workerDefaults.sync_command ? `Default: ${workerDefaults.sync_command}` : undefined} />
                      <Field label="Test Command" value={worker.test_command || ''} onChange={(value) => onWorkerChange(index, 'test_command', value)} issues={issues[`workers[${index}].test_command`]} helpText={suggestedTest ? `A0 picked: ${suggestedTest}` : (workerDefaults.test_command ? `Default: ${workerDefaults.test_command}` : undefined)} />
                      <Field label="Submit Strategy" value={worker.submit_strategy || ''} onChange={(value) => onWorkerChange(index, 'submit_strategy', value)} issues={issues[`workers[${index}].submit_strategy`]} helpText={workerDefaults.submit_strategy ? `Default: ${workerDefaults.submit_strategy}` : undefined} />
                      <Field label="Git Name" value={worker.git_identity?.name || ''} onChange={(value) => onWorkerChange(index, 'git_identity.name', value)} helpText={workerDefaults.git_identity?.name ? `Default: ${workerDefaults.git_identity.name}` : undefined} />
                      <Field label="Git Email" value={worker.git_identity?.email || ''} onChange={(value) => onWorkerChange(index, 'git_identity.email', value)} helpText={workerDefaults.git_identity?.email ? `Default: ${workerDefaults.git_identity.email}` : undefined} />
                    </div>
                  </details>
                      </>
                    );
                  })()}
                </div>
              ))}
            </div>
          </section>
        </div>
      </section>
    </div>
  );
}
