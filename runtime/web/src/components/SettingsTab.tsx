import type { SectionStatusMap, WorkerResetScope } from '../lib/local-types';
import type {
  ConfigResourcePool,
  ConfigSection,
  ConfigShape,
  DashboardState,
  ValidationIssue,
} from '../types';
import { stringifyQueue } from '../lib/utils';
import { projectReferenceWorkspace, translateUiText } from '../lib/utils';
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
            <h2>设置</h2>
            <p className="small">A0 现在会自动补齐 Worker 名册、分支建议、worktree 路径和共享默认值。你通常只需要确认项目路径、资源池路由和真正的例外项。</p>
          </div>
        </div>
        <div className="settings-stack">
          <section className="helper-card settings-card settings-card-wide">
            <SectionHeader title="资源池" section="resource_pools" status={sectionStatuses.resource_pools} onValidate={onValidateSection} onSave={onSaveSection} action={<button className="ghost" type="button" onClick={onAddPool}>新增资源池</button>} />
            <SectionIssueList issues={collectSectionIssues('resource_pools', allIssues)} />
            <div className="pool-strip">
              {Object.entries(pools).map(([poolName, pool]) => (
                <div key={poolName} className="subcard pool-card">
                  <div className="subcard-title">{poolName}</div>
                  <div className="field-grid">
                    <SelectField label="提供方" value={String(pool.provider || '')} onChange={(value) => onPoolChange(poolName, 'provider', value)} issues={issues[`resource_pools.${poolName}.provider`]} options={providerOptions} />
                    <Field label="模型" value={String(pool.model || '')} onChange={(value) => onPoolChange(poolName, 'model', value)} issues={issues[`resource_pools.${poolName}.model`]} />
                    <Field label="优先级" type="number" value={Number(pool.priority ?? 100)} onChange={(value) => onPoolChange(poolName, 'priority', value)} issues={issues[`resource_pools.${poolName}.priority`]} />
                    <Field label="API Key" value={String(pool.api_key || '')} onChange={(value) => onPoolChange(poolName, 'api_key', value)} />
                  </div>
                </div>
              ))}
            </div>
          </section>

          <div className="settings-duo">
            <section className="helper-card settings-card">
            <SectionHeader title="项目" section="project" status={sectionStatuses.project} onValidate={onValidateSection} onSave={onSaveSection} />
            <SectionIssueList issues={collectSectionIssues('project', allIssues)} />
            <div className="field-grid">
              <Field label="仓库名" value={project.repository_name || ''} onChange={(value) => onProjectChange('repository_name', value)} issues={issues['project.repository_name']} />
              <Field label="本地仓库根目录" value={project.local_repo_root || ''} onChange={(value) => onProjectChange('local_repo_root', value)} issues={issues['project.local_repo_root']} />
              <Field label="参考工作区" value={projectReferenceWorkspace(project)} onChange={(value) => onProjectChange('reference_workspace_root', value)} issues={issues['project.reference_workspace_root']} helpText="可选：共享参考仓库或 baseline 工作区，用于为任务提供上下文。" />
              <Field label="面板 Host" value={dashboard.host || ''} onChange={(value) => onProjectChange('dashboard.host', value)} issues={issues['project.dashboard.host']} />
              <Field label="面板端口" type="number" value={dashboard.port || 8233} onChange={(value) => onProjectChange('dashboard.port', value)} issues={issues['project.dashboard.port']} />
            </div>
          </section>

            <section className="helper-card settings-card">
            <SectionHeader title="合并策略" section="merge_policy" status={sectionStatuses.merge_policy} onValidate={onValidateSection} onSave={onSaveSection} />
            <SectionIssueList issues={collectSectionIssues('merge_policy', allIssues)} />
            <div className="field-grid">
              <Field label="集成分支" value={project.integration_branch || project.base_branch || ''} onChange={(value) => onMergeChange('integration_branch', value)} issues={issues['project.integration_branch']} />
              <Field label="管理者姓名" value={project.manager_git_identity?.name || ''} onChange={(value) => onMergeChange('manager_git_identity.name', value)} />
              <Field label="管理者邮箱" value={project.manager_git_identity?.email || ''} onChange={(value) => onMergeChange('manager_git_identity.email', value)} />
            </div>
          </section>
          </div>

          <section className="helper-card settings-card settings-card-wide">
            <SectionHeader
               title="Worker 默认值"
              section="worker_defaults"
              status={sectionStatuses.worker_defaults}
              onValidate={onValidateSection}
              onSave={onSaveSection}
               subtitle="共享默认值是你真正需要跨 Worker 标准化的少量旋钮；高级默认值则是异常环境下的兜底覆写。"
               action={<button className="ghost" type="button" onClick={onResetWorkerDefaults}>重置为 A0</button>}
             />
            <SectionIssueList issues={collectSectionIssues('worker_defaults', allIssues)} />
            <p className="small muted">这些值会作用于所有 Worker，除非下面某一行显式覆写。空白字段会尽量按运行时约定或合理默认值自动补齐，因此主路径应保持稀疏。</p>
            <div className="field-grid compact-field-grid">
              <Field label="默认资源池" value={workerDefaults.resource_pool || ''} onChange={(value) => onWorkerChange(-1, 'worker_defaults.resource_pool', value)} issues={issues['worker_defaults.resource_pool']} helpText="留空则依赖资源池队列或每个 Worker 的覆写。" />
              <Field label="默认资源池队列" value={stringifyQueue(workerDefaults.resource_pool_queue)} onChange={(value) => onWorkerChange(-1, 'worker_defaults.resource_pool_queue', value)} issues={issues['worker_defaults.resource_pool_queue']} placeholder="ducc_pool" />
              <SelectField label="默认环境" value={workerDefaults.environment_type || 'uv'} onChange={(value) => onWorkerChange(-1, 'worker_defaults.environment_type', value)} options={['uv', 'venv', 'none']} />
              <Field label="默认环境路径" value={workerDefaults.environment_path || ''} onChange={(value) => onWorkerChange(-1, 'worker_defaults.environment_path', value)} issues={issues['worker_defaults.environment_path']} />
            </div>
            <details className="advanced-panel defaults-panel">
              <summary>高级默认值</summary>
              <div className="field-grid advanced-grid">
                <Field label="默认同步命令" value={workerDefaults.sync_command || ''} onChange={(value) => onWorkerChange(-1, 'worker_defaults.sync_command', value)} helpText="留空则让 A0 按环境约定自动处理。" />
                <Field label="默认测试命令" value={workerDefaults.test_command || ''} onChange={(value) => onWorkerChange(-1, 'worker_defaults.test_command', value)} issues={issues['worker_defaults.test_command']} helpText="留空则让任务策略为每个 Worker 自动选择。" />
                <Field label="默认提交策略" value={workerDefaults.submit_strategy || ''} onChange={(value) => onWorkerChange(-1, 'worker_defaults.submit_strategy', value)} issues={issues['worker_defaults.submit_strategy']} helpText="留空则保持 A0 的标准交流程。" />
                <Field label="默认 Git 名称" value={workerDefaults.git_identity?.name || ''} onChange={(value) => onWorkerChange(-1, 'worker_defaults.git_identity.name', value)} issues={issues['worker_defaults.git_identity.name']} />
                <Field label="默认 Git 邮箱" value={workerDefaults.git_identity?.email || ''} onChange={(value) => onWorkerChange(-1, 'worker_defaults.git_identity.email', value)} issues={issues['worker_defaults.git_identity.email']} />
              </div>
            </details>
          </section>

          <AutomationSummary draftConfig={draftConfig} data={data} />

          <section className="helper-card settings-card settings-card-wide">
            <SectionHeader
               title="Worker 配置"
              section="workers"
              status={sectionStatuses.workers}
              onValidate={onValidateSection}
              onSave={onSaveSection}
              action={
                <>
                  <button className="ghost" type="button" onClick={onSyncWorkers}>从计划同步</button>
                  <button className="ghost" type="button" onClick={onAutoFillWorktreePaths}>自动补路径</button>
                  <button className="ghost" type="button" onClick={onAddWorker}>新增 Worker</button>
                </>
              }
            />
            <SectionIssueList issues={collectSectionIssues('workers', allIssues)} />
            <p className="small muted">当前从 backlog/运行时检测到的 Worker：{plannedWorkers.map((item) => item.agent).join(', ') || '无'}。A0 计划是派生出的默认执行目标。下面任何已填写的覆写都会变成人工钉住的例外项；使用“重置为 A0”可以清除这些钉子并回退到计划。</p>
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
                    <button className="ghost" type="button" onClick={() => onResetWorkerOverrides(index)}>重置为 A0</button>
                  </div>
                  {recommendation ? <p className="small muted">{translateUiText(recommendation)}</p> : null}
                  <div className="plan-grid">
                    <div className="plan-row"><span className="muted">任务</span><strong>{planned.taskId || 'A0 将分配'}</strong></div>
                    <div className="plan-row"><span className="muted">类型</span><strong>{translateUiText(planned.taskType || 'default')}</strong></div>
                    <div className="plan-row"><span className="muted">分支</span><strong>{planned.branch || 'A0 将自动推导'}</strong></div>
                    <div className="plan-row"><span className="muted">工作树</span><strong>{planned.worktreePath || '由本地仓库根目录推导'}</strong></div>
                    <div className="plan-row"><span className="muted">资源池</span><strong>{planned.lockedPool || planned.recommendedPool || 'A0 路由'}</strong></div>
                    <div className="plan-row"><span className="muted">测试</span><strong>{planned.testCommand || suggestedTest || 'A0 默认值'}</strong></div>
                  </div>
                  <div className="field-grid compact-field-grid">
                    <Field label="Agent" value={worker.agent || ''} onChange={(value) => onWorkerChange(index, 'agent', value)} issues={issues[`workers[${index}].agent`]} />
                    <Field label="资源池覆写" value={worker.resource_pool || ''} onChange={(value) => onWorkerChange(index, 'resource_pool', value)} issues={issues[`workers[${index}].resource_pool`]} helpText={resolved?.locked_pool ? `A0 锁定：${resolved.locked_pool}` : resolved?.recommended_pool ? `A0 推荐：${resolved.recommended_pool}` : (workerDefaults.resource_pool ? `默认值：${workerDefaults.resource_pool}` : '留空表示继承 A0 路由。')} />
                  </div>
                  <details className="advanced-panel">
                    <summary>高级覆写</summary>
                    <div className="override-toolbar">
                      <button className="ghost" type="button" onClick={() => onResetWorkerOverrides(index, 'routing')}>重置路由</button>
                      <button className="ghost" type="button" onClick={() => onResetWorkerOverrides(index, 'runtime')}>重置运行时</button>
                    </div>
                    <div className="field-grid advanced-grid">
                      <Field label="任务 ID 覆写" value={worker.task_id || ''} onChange={(value) => onWorkerChange(index, 'task_id', value)} helpText={planned.taskId ? `A0 计划：${planned.taskId}` : '留空表示继承 A0 任务分配。'} />
                      <Field label="分支覆写" value={worker.branch || ''} onChange={(value) => onWorkerChange(index, 'branch', value)} issues={issues[`workers[${index}].branch`]} helpText={planned.branch ? `A0 计划：${planned.branch}` : '留空则让 A0 自动推导分支。'} />
                      <Field label="Worktree 路径覆写" value={worker.worktree_path || ''} onChange={(value) => onWorkerChange(index, 'worktree_path', value)} issues={issues[`workers[${index}].worktree_path`]} helpText={planned.worktreePath ? `A0 计划：${planned.worktreePath}` : '留空则根据本地仓库根目录推导。'} />
                      <Field label="队列覆写" value={stringifyQueue(worker.resource_pool_queue)} onChange={(value) => onWorkerChange(index, 'resource_pool_queue', value)} issues={issues[`workers[${index}].resource_pool_queue`]} placeholder="pool_a, pool_b" helpText={resolved?.resource_pool_queue?.length ? `A0 顺序：${stringifyQueue(resolved.resource_pool_queue)}` : (workerDefaults.resource_pool_queue?.length ? `默认值：${stringifyQueue(workerDefaults.resource_pool_queue)}` : '留空表示继承 A0 队列。')} />
                      <SelectField label="环境类型" value={worker.environment_type || ''} onChange={(value) => onWorkerChange(index, 'environment_type', value)} options={['uv', 'venv', 'none']} />
                      <Field label="环境路径" value={worker.environment_path || ''} onChange={(value) => onWorkerChange(index, 'environment_path', value)} issues={issues[`workers[${index}].environment_path`]} helpText={workerDefaults.environment_path ? `默认值：${workerDefaults.environment_path}` : undefined} />
                      <Field label="同步命令" value={worker.sync_command || ''} onChange={(value) => onWorkerChange(index, 'sync_command', value)} helpText={workerDefaults.sync_command ? `默认值：${workerDefaults.sync_command}` : undefined} />
                      <Field label="测试命令" value={worker.test_command || ''} onChange={(value) => onWorkerChange(index, 'test_command', value)} issues={issues[`workers[${index}].test_command`]} helpText={suggestedTest ? `A0 选定：${suggestedTest}` : (workerDefaults.test_command ? `默认值：${workerDefaults.test_command}` : undefined)} />
                      <Field label="提交策略" value={worker.submit_strategy || ''} onChange={(value) => onWorkerChange(index, 'submit_strategy', value)} issues={issues[`workers[${index}].submit_strategy`]} helpText={workerDefaults.submit_strategy ? `默认值：${workerDefaults.submit_strategy}` : undefined} />
                      <Field label="Git 名称" value={worker.git_identity?.name || ''} onChange={(value) => onWorkerChange(index, 'git_identity.name', value)} helpText={workerDefaults.git_identity?.name ? `默认值：${workerDefaults.git_identity.name}` : undefined} />
                      <Field label="Git 邮箱" value={worker.git_identity?.email || ''} onChange={(value) => onWorkerChange(index, 'git_identity.email', value)} helpText={workerDefaults.git_identity?.email ? `默认值：${workerDefaults.git_identity.email}` : undefined} />
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
