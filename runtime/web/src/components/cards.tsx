import type {
  A0ConsoleRequest,
  CleanupWorkerState,
  ConfigShape,
  DashboardState,
  MergeQueueItem,
  TeamMailboxMessage,
} from '../types';
import type { MailboxDraft, WorkflowDraft, WorkflowPresetAction } from '../lib/local-types';
import { classNames, displayState, stateClass, formatTokenCount, stringifyQueue, translateUiText } from '../lib/utils';
import { buildPlannedWorkers } from '../lib/config';
import { workflowBriefLines, workflowPeekTasks, mailboxPeekMessages } from '../lib/workflow';
import { Field, SelectField } from './shared';

export function MergeCard({ item }: { item: MergeQueueItem }) {
  const raw = String(item.status || 'not_started');
  const status = raw === 'active' || raw === 'healthy'
    ? { label: '进行中', className: 'state-active' }
    : raw === 'stale' || raw.startsWith('launch_failed')
      ? { label: '需关注', className: 'state-stale' }
      : raw === 'offline' || raw === 'stopped'
        ? { label: '待评审', className: 'state-offline' }
        : { label: '排队中', className: 'state-not_started' };
  const blockers = item.blockers || [];
  const pendingWork = item.pending_work || [];
  const requestedUnlocks = item.requested_unlocks || [];
  const dependencies = item.dependencies || [];
  return (
    <article className="merge-card">
      <div className="merge-card-header">
        <div>
          <div className="merge-branch">{item.branch}</div>
          <div className="merge-track">
            <span>{item.agent}</span>
            <span className="merge-arrow">-&gt;</span>
            <span>{item.merge_target}</span>
          </div>
        </div>
        <span className={classNames('chip', status.className)}>{status.label}</span>
      </div>
      <div className="merge-meta">
        <div><strong>提交</strong> {item.submit_strategy}</div>
        <div><strong>Worker 身份</strong> {item.worker_identity}</div>
        <div><strong>管理者</strong> {item.manager_identity}</div>
        <div><strong>检查点</strong> {translateUiText(item.checkpoint_status || 'unknown')}</div>
      </div>
      {item.attention_summary ? <div className="merge-attention"><strong>关注项</strong> {translateUiText(item.attention_summary)}</div> : null}
      {blockers.length ? <div className="merge-list-block"><strong>阻塞项</strong><ul>{blockers.map((entry) => <li key={entry}>{translateUiText(entry)}</li>)}</ul></div> : null}
      {pendingWork.length ? <div className="merge-list-block"><strong>待完成工作</strong><ul>{pendingWork.map((entry) => <li key={entry}>{translateUiText(entry)}</li>)}</ul></div> : null}
      {requestedUnlocks.length ? <div className="merge-list-block"><strong>请求解锁</strong><ul>{requestedUnlocks.map((entry) => <li key={entry}>{translateUiText(entry)}</li>)}</ul></div> : null}
      {dependencies.length ? <div className="merge-list-block"><strong>依赖项</strong><ul>{dependencies.map((entry) => <li key={entry}>{translateUiText(entry)}</li>)}</ul></div> : null}
      {item.resume_instruction ? <div className="merge-attention"><strong>恢复说明</strong> {translateUiText(item.resume_instruction)}</div> : null}
      {item.next_checkin ? <div className="merge-note"><strong>下次签到</strong> {translateUiText(item.next_checkin)}</div> : null}
      <div className="merge-note">{translateUiText(item.manager_action)}</div>
    </article>
  );
}

export function AgentCard({ item }: { item: import('../lib/local-types').AgentRow }) {
  const processLine = item.process_alive ? `pid ${item.pid}` : item.last_seen || '尚无心跳';
  const detailLine = item.process_alive
    ? item.phase || item.last_log_line || '进程存活'
    : item.escalation && item.escalation !== 'none'
      ? item.escalation
      : item.evidence || item.expected_next_checkin || '等待启动';
  const telemetryLine = item.process_alive
    ? `${item.progress_pct ?? '–'}% 进度 · ${formatTokenCount(item.total_tokens)} token`
    : item.last_activity_at || item.expected_next_checkin || '近期无活动';
  return (
    <article className="agent-card">
      <header>
        <div>
          <div className="agent-name">{item.agent}</div>
          <div className="agent-role">{item.role}</div>
        </div>
        <span className={classNames('chip', stateClass(item.display_state))}>{displayState(item.display_state)}</span>
      </header>
      <div className="agent-meta">
        <div><strong>资源池</strong> {item.resource_pool} / {item.provider}</div>
        <div><strong>模型</strong> {item.model}</div>
        <div><strong>分支</strong> {item.branch}</div>
        <div><strong>心跳</strong> {translateUiText(processLine)}</div>
        <div><strong>遥测</strong> {translateUiText(telemetryLine)}</div>
        <div className="muted">{translateUiText(detailLine)}</div>
      </div>
    </article>
  );
}

export function A0RequestCard({
  item,
  replyDraft,
  onReplyChange,
  onReply,
  onPrepareWorkflow,
}: {
  item: A0ConsoleRequest;
  replyDraft: string;
  onReplyChange: (requestId: string, value: string) => void;
  onReply: (item: A0ConsoleRequest, action: string) => void;
  onPrepareWorkflow: (item: A0ConsoleRequest, action: WorkflowPresetAction) => void;
}) {
  const primaryAction = item.request_type === 'plan_review'
    ? { action: 'approve', label: '批准计划' }
    : item.request_type === 'task_review'
      ? { action: 'approve', label: '接受任务' }
      : { action: 'resume', label: '恢复' };
  const secondaryAction = item.request_type === 'plan_review'
    ? { action: 'reject', label: '拒绝计划', className: 'danger-outline' }
    : item.request_type === 'task_review'
      ? { action: 'reject', label: '重新打开任务', className: 'danger-outline' }
      : { action: 'acknowledged', label: '确认收到', className: 'ghost' };
  return (
    <article className="merge-card a0-request-card">
      <div className="merge-card-header">
        <div>
          <div className="merge-branch">{item.title}</div>
          <div className="merge-track">
            <span>{item.agent}</span>
            <span className="merge-arrow">-&gt;</span>
            <span>{item.status}</span>
          </div>
        </div>
        <span className={classNames('chip', item.response_state === 'pending' ? 'state-stale' : 'state-active')}>
          {item.response_state === 'pending' ? '等待回复' : translateUiText(item.response_state || 'answered')}
        </span>
      </div>
      <div className="merge-attention"><strong>A0 请求</strong> {item.body}</div>
      {item.resume_instruction ? <div className="merge-note"><strong>恢复说明</strong> {translateUiText(item.resume_instruction)}</div> : null}
      {item.next_checkin ? <div className="merge-note"><strong>下次签到</strong> {translateUiText(item.next_checkin)}</div> : null}
      {item.response_note ? <div className="merge-note"><strong>最新回复</strong> {item.response_note}</div> : null}
      <label className="field">
        <span className="field-label">回复 A0</span>
        <textarea className="field-input field-textarea" value={replyDraft} onChange={(event) => onReplyChange(item.id, event.target.value)} placeholder="向 A0 说明决策、约束或解阻指令。" />
      </label>
      {item.task_id ? (
        <div className="toolbar-group a0-actions">
          <button className="ghost" type="button" onClick={() => onPrepareWorkflow(item, 'replan')}>预填重规划</button>
          <button className="ghost" type="button" onClick={() => onPrepareWorkflow(item, 'reassign')}>预填重分配</button>
          <button className="ghost" type="button" onClick={() => onPrepareWorkflow(item, 'reopen')}>预填重新打开</button>
        </div>
      ) : null}
      <div className="toolbar-group a0-actions">
        <button type="button" onClick={() => onReply(item, primaryAction.action)}>{primaryAction.label}</button>
        <button className={secondaryAction.className} type="button" onClick={() => onReply(item, secondaryAction.action)}>{secondaryAction.label}</button>
        {item.request_type === 'worker_intervention' ? <button className="danger-outline" type="button" onClick={() => onReply(item, 'blocked')}>仍然阻塞</button> : null}
      </div>
    </article>
  );
}

export function MailboxCard({ item, onAck }: { item: TeamMailboxMessage; onAck: (messageId: string, ackState: string) => void }) {
  return (
    <article className="merge-card a0-request-card">
      <div className="merge-card-header">
        <div>
          <div className="merge-branch">{item.topic}</div>
          <div className="merge-track">
            <span>{item.from}</span>
            <span className="merge-arrow">-&gt;</span>
            <span>{item.to}</span>
          </div>
        </div>
        <span className={classNames('chip', item.ack_state === 'pending' ? 'state-stale' : 'state-active')}>{displayState(item.ack_state)}</span>
      </div>
      <div className="merge-attention"><strong>消息</strong> {item.body}</div>
      {item.related_task_ids?.length ? <div className="merge-note"><strong>任务</strong> {item.related_task_ids.join(', ')}</div> : null}
      <div className="merge-note"><strong>创建时间</strong> {item.created_at}</div>
      <div className="toolbar-group a0-actions">
        <button className="ghost" type="button" onClick={() => onAck(item.id, 'seen')}>标记已查看</button>
        <button type="button" onClick={() => onAck(item.id, 'resolved')}>解决</button>
      </div>
    </article>
  );
}

export function CleanupWorkerCard({ item, onStopWorker, disabled }: { item: CleanupWorkerState; onStopWorker: (agent: string) => void; disabled?: boolean }) {
  return (
    <article className="merge-card a0-request-card">
      <div className="merge-card-header">
        <div>
          <div className="merge-branch">{item.agent}</div>
          <div className="merge-track">
            <span>{translateUiText(item.runtime_status || 'runtime unknown')}</span>
            <span className="merge-arrow">-&gt;</span>
            <span>{translateUiText(item.heartbeat_state || 'heartbeat unknown')}</span>
          </div>
        </div>
        <span className={classNames('chip', item.ready ? 'state-active' : 'state-stale')}>{item.ready ? '就绪' : '阻塞'}</span>
      </div>
      {item.blockers.length ? <div className="merge-list-block"><strong>阻塞项</strong><ul>{item.blockers.map((entry) => <li key={`${item.agent}-${entry}`}>{translateUiText(entry)}</li>)}</ul></div> : <div className="small muted">该 Worker 当前没有清理阻塞项。</div>}
      <div className="toolbar-group a0-actions">
        <button type="button" onClick={() => onStopWorker(item.agent)} disabled={disabled || !item.active}>关闭 Worker</button>
      </div>
    </article>
  );
}

export function MailboxComposerCard({
  draft,
  onChange,
  onSend,
  participants,
  disabled,
}: {
  draft: MailboxDraft;
  onChange: (field: keyof MailboxDraft, value: string) => void;
  onSend: () => void;
  participants: string[];
  disabled?: boolean;
}) {
  const recipientOptions = ['all', 'manager', ...participants.filter((item) => item !== 'A0')];
  return (
    <section className="card">
      <div className="panel-title">
        <div>
          <h2>邮箱编写器</h2>
          <p className="small">通过团队邮箱发送可持久化的协作说明，让它们在 Worker 重启或 Provider 切换后仍然保留。</p>
        </div>
      </div>
      <section className="grid">
        <SelectField label="发件人" value={draft.from} onChange={(value) => onChange('from', value)} options={participants} />
        <SelectField label="收件人" value={draft.to} onChange={(value) => onChange('to', value)} options={recipientOptions} />
      </section>
      <section className="grid">
        <SelectField label="主题" value={draft.topic} onChange={(value) => onChange('topic', value)} options={['status_note', 'blocker', 'handoff', 'review_request', 'design_question']} />
        <SelectField label="范围" value={draft.scope} onChange={(value) => onChange('scope', value)} options={['direct', 'broadcast', 'manager']} />
      </section>
      <Field label="相关任务" value={draft.relatedTaskIds} onChange={(value) => onChange('relatedTaskIds', value)} helpText="可选，使用逗号分隔多个任务 ID。" placeholder="A1-001, A6-001" />
      <label className="field">
        <span className="field-label">消息正文</span>
        <textarea className="field-input field-textarea" value={draft.body} onChange={(event) => onChange('body', event.target.value)} placeholder="填写应写入共享邮箱的持久化协作说明。" />
      </label>
      <div className="toolbar-group a0-actions">
        <button type="button" onClick={onSend} disabled={disabled || !draft.from || !draft.to || !draft.body.trim()}>发送邮箱消息</button>
      </div>
    </section>
  );
}

export function WorkflowBriefCard({ data }: { data: DashboardState }) {
  const lines = workflowBriefLines(data);
  const tasks = workflowPeekTasks(data);
  return (
    <section className="card">
      <div className="panel-title">
        <div>
          <h2>工作流简报</h2>
          <p className="small">A0 可以在调整归属、评审 Gate 或任务顺序之前，先浏览当前交付通道。</p>
        </div>
      </div>
      <div className="stack-list">
        {lines.map((line) => <div key={line} className="subcard"><p>{line}</p></div>)}
      </div>
      <div className="stack-list">
        {tasks.length ? tasks.map((task) => (
          <div key={task.id} className="subcard">
            <div className="subcard-title">{task.id} · {task.title}</div>
            <div className="small muted">{translateUiText(task.owner || 'unassigned')} · {translateUiText(task.status)} · {translateUiText(task.claim_state || 'unclaimed')} · {translateUiText(task.plan_state || 'none')}</div>
            {task.dependencies?.length ? <p className="small">依赖于 {task.dependencies.join(', ')}</p> : null}
          </div>
        )) : <div className="small muted">当前没有可展示的工作流条目。</div>}
      </div>
    </section>
  );
}

export function MailboxPeekCard({ data }: { data: DashboardState }) {
  const messages = mailboxPeekMessages(data);
  return (
    <section className="card">
      <div className="panel-title">
        <div>
          <h2>邮箱预览</h2>
          <p className="small">无需离开当前视图即可查看近期未解决的协作说明。</p>
        </div>
        <div className="small muted">{data.team_mailbox.pending_count} 条待处理</div>
      </div>
      <div className="stack-list">
        {messages.length ? messages.map((item) => (
          <div key={item.id} className="subcard">
            <div className="subcard-title">{item.topic}</div>
            <div className="small muted">{item.from} -&gt; {item.to} · {translateUiText(item.ack_state)} · {item.created_at}</div>
            <p>{item.body}</p>
            {item.related_task_ids?.length ? <div className="small muted">任务：{item.related_task_ids.join(', ')}</div> : null}
          </div>
        )) : <div className="small muted">当前没有未解决的邮箱消息。</div>}
      </div>
    </section>
  );
}

export function WorkflowPatchCard({
  data,
  draft,
  onChange,
  onSubmit,
  disabled,
}: {
  data: DashboardState;
  draft: WorkflowDraft;
  onChange: (field: keyof WorkflowDraft, value: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
}) {
  const participants = Array.from(new Set(['', 'A0', ...(data.resolved_workers || []).map((item) => item.agent).filter(Boolean)])).sort();
  const taskOptions = (data.backlog.items || []).map((item) => item.id);
  return (
    <section id="workflow-replan-card" className="card">
      <div className="panel-title">
        <div>
          <h2>工作流重规划</h2>
          <p className="small">A0 可以直接在控制平面中改写归属、认领状态、评审姿态和计划意图。</p>
        </div>
      </div>
      <section className="grid">
        <SelectField label="任务" value={draft.taskId} onChange={(value) => onChange('taskId', value)} options={taskOptions} />
        <Field label="关卡" value={draft.gate} onChange={(value) => onChange('gate', value)} placeholder="关卡名称" />
      </section>
      <section className="grid">
        <Field label="标题" value={draft.title} onChange={(value) => onChange('title', value)} />
        <Field label="优先级" value={draft.priority} onChange={(value) => onChange('priority', value)} placeholder="P0 / P1" />
      </section>
      <section className="grid">
        <SelectField label="负责人" value={draft.owner} onChange={(value) => onChange('owner', value)} options={participants} />
        <SelectField label="认领者" value={draft.claimedBy} onChange={(value) => onChange('claimedBy', value)} options={participants} />
      </section>
      <section className="grid">
        <SelectField label="状态" value={draft.status} onChange={(value) => onChange('status', value)} options={['pending', 'active', 'blocked', 'review', 'completed']} />
        <SelectField label="认领状态" value={draft.claimState} onChange={(value) => onChange('claimState', value)} options={['unclaimed', 'claimed', 'in_progress', 'review', 'completed']} />
      </section>
      <section className="grid">
        <SelectField label="需要计划" value={draft.planRequired} onChange={(value) => onChange('planRequired', value)} options={['yes', 'no']} />
        <SelectField label="计划状态" value={draft.planState} onChange={(value) => onChange('planState', value)} options={['none', 'pending_review', 'approved', 'rejected']} />
      </section>
      <Field label="依赖项" value={draft.dependencies} onChange={(value) => onChange('dependencies', value)} helpText="使用逗号分隔多个任务 ID。" placeholder="A1-001, A2-001" />
      <label className="field">
        <span className="field-label">计划摘要</span>
        <textarea className="field-input field-textarea" value={draft.planSummary} onChange={(event) => onChange('planSummary', event.target.value)} placeholder="重写实现计划或审批预期。" />
      </label>
      <section className="grid">
        <Field label="认领说明" value={draft.claimNote} onChange={(value) => onChange('claimNote', value)} placeholder="当前归属说明" />
        <Field label="评审说明" value={draft.reviewNote} onChange={(value) => onChange('reviewNote', value)} placeholder="验收或重新打开说明" />
      </section>
      <label className="field">
        <span className="field-label">管理者备注</span>
        <textarea className="field-input field-textarea" value={draft.managerNote} onChange={(event) => onChange('managerNote', event.target.value)} placeholder="可选：随工作流变更一起保存的持久化备注。" />
      </label>
      <div className="toolbar-group a0-actions">
        <button type="button" onClick={onSubmit} disabled={disabled || !draft.taskId}>应用工作流更新</button>
      </div>
    </section>
  );
}

export function AutomationSummary({ draftConfig, data }: { draftConfig: ConfigShape; data: DashboardState }) {
  const plannedWorkers = buildPlannedWorkers(data, draftConfig);
  const autoManaged = [
    '仓库名以及 dashboard host/port 默认值',
    '来自 backlog 与运行时状态的 Worker 名册',
    '来自当前计划的 Worker 任务 ID',
    '根据任务归属和标题生成的推荐分支名',
    '由仓库根目录与 Agent ID 派生出的 worktree 路径',
    '基于 Provider 质量历史的任务感知资源池推荐与锁定',
    '来自实时 Provider 排名的默认资源池队列',
    '环境类型/路径默认值',
    '默认同步命令',
    '默认提交策略',
    '带安全回退的任务感知测试命令选择',
  ];
  const userOnly = [
    '当 A0 无法正确推断时，需要人工确认的本地仓库根目录',
    '项目确实需要时才填写的参考工作区路径',
    '集成分支策略',
    '资源池凭据、Provider 选择与模型选择',
    '只有确实偏离默认路径时才需要填写的 Worker 级路由或环境覆写',
  ];

  return (
    <section className="helper-card settings-card settings-card-wide">
      <div className="section-head">
        <h3>A0 管理默认值</h3>
        <div className="small muted">{autoManaged.length} 项由系统自动管理，{userOnly.length} 项仍需要人工确认</div>
      </div>
      <p className="small muted">当前检测到的计划内 Worker：{plannedWorkers.map((worker) => worker.agent).join(', ') || '无'}。在设置页中，A0 计划表示派生出的目标状态；覆写表示人工钉住的例外项，应当尽量少且容易重置。</p>
      <div className="automation-grid">
        <div className="subcard">
          <div className="subcard-title">通常不需要手填这些项</div>
          <ul className="automation-list">
            {autoManaged.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
        <div className="subcard">
          <div className="subcard-title">你通常只需要确认这些项</div>
          <ul className="automation-list">
            {userOnly.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
      </div>
    </section>
  );
}
