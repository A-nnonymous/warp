import type {
  A0ConsoleRequest,
  CleanupWorkerState,
  ConfigShape,
  DashboardState,
  MergeQueueItem,
  TeamMailboxMessage,
} from '../types';
import type { MailboxDraft, WorkflowDraft, WorkflowPresetAction } from '../lib/local-types';
import { classNames, displayState, stateClass, formatTokenCount, stringifyQueue } from '../lib/utils';
import { buildPlannedWorkers } from '../lib/config';
import { workflowBriefLines, workflowPeekTasks, mailboxPeekMessages } from '../lib/workflow';
import { Field, SelectField } from './shared';

export function MergeCard({ item }: { item: MergeQueueItem }) {
  const raw = String(item.status || 'not_started');
  const status = raw === 'active' || raw === 'healthy'
    ? { label: 'In progress', className: 'state-active' }
    : raw === 'stale' || raw.startsWith('launch_failed')
      ? { label: 'Needs attention', className: 'state-stale' }
      : raw === 'offline' || raw === 'stopped'
        ? { label: 'Ready for review', className: 'state-offline' }
        : { label: 'Queued', className: 'state-not_started' };
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
        <div><strong>Submit</strong> {item.submit_strategy}</div>
        <div><strong>Worker identity</strong> {item.worker_identity}</div>
        <div><strong>Manager</strong> {item.manager_identity}</div>
        <div><strong>Checkpoint</strong> {item.checkpoint_status || 'unknown'}</div>
      </div>
      {item.attention_summary ? <div className="merge-attention"><strong>Attention</strong> {item.attention_summary}</div> : null}
      {blockers.length ? <div className="merge-list-block"><strong>Blockers</strong><ul>{blockers.map((entry) => <li key={entry}>{entry}</li>)}</ul></div> : null}
      {pendingWork.length ? <div className="merge-list-block"><strong>Pending Work</strong><ul>{pendingWork.map((entry) => <li key={entry}>{entry}</li>)}</ul></div> : null}
      {requestedUnlocks.length ? <div className="merge-list-block"><strong>Requested Unlocks</strong><ul>{requestedUnlocks.map((entry) => <li key={entry}>{entry}</li>)}</ul></div> : null}
      {dependencies.length ? <div className="merge-list-block"><strong>Dependencies</strong><ul>{dependencies.map((entry) => <li key={entry}>{entry}</li>)}</ul></div> : null}
      {item.resume_instruction ? <div className="merge-attention"><strong>Resume</strong> {item.resume_instruction}</div> : null}
      {item.next_checkin ? <div className="merge-note"><strong>Next check-in</strong> {item.next_checkin}</div> : null}
      <div className="merge-note">{item.manager_action}</div>
    </article>
  );
}

export function AgentCard({ item }: { item: import('../lib/local-types').AgentRow }) {
  const processLine = item.process_alive ? `pid ${item.pid}` : item.last_seen || 'no heartbeat yet';
  const detailLine = item.process_alive
    ? item.phase || item.last_log_line || 'process alive'
    : item.escalation && item.escalation !== 'none'
      ? item.escalation
      : item.evidence || item.expected_next_checkin || 'waiting for launch';
  const telemetryLine = item.process_alive
    ? `${item.progress_pct ?? '–'}% progress · ${formatTokenCount(item.total_tokens)} tokens`
    : item.last_activity_at || item.expected_next_checkin || 'no recent activity';
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
        <div><strong>Pool</strong> {item.resource_pool} / {item.provider}</div>
        <div><strong>Model</strong> {item.model}</div>
        <div><strong>Branch</strong> {item.branch}</div>
        <div><strong>Heartbeat</strong> {processLine}</div>
        <div><strong>Telemetry</strong> {telemetryLine}</div>
        <div className="muted">{detailLine}</div>
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
    ? { action: 'approve', label: 'Approve plan' }
    : item.request_type === 'task_review'
      ? { action: 'approve', label: 'Accept task' }
      : { action: 'resume', label: 'Resume' };
  const secondaryAction = item.request_type === 'plan_review'
    ? { action: 'reject', label: 'Reject plan', className: 'danger-outline' }
    : item.request_type === 'task_review'
      ? { action: 'reject', label: 'Reopen task', className: 'danger-outline' }
      : { action: 'acknowledged', label: 'Acknowledge', className: 'ghost' };
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
          {item.response_state === 'pending' ? 'Awaiting reply' : item.response_state || 'answered'}
        </span>
      </div>
      <div className="merge-attention"><strong>A0 asks</strong> {item.body}</div>
      {item.resume_instruction ? <div className="merge-note"><strong>Resume</strong> {item.resume_instruction}</div> : null}
      {item.next_checkin ? <div className="merge-note"><strong>Next check-in</strong> {item.next_checkin}</div> : null}
      {item.response_note ? <div className="merge-note"><strong>Latest reply</strong> {item.response_note}</div> : null}
      <label className="field">
        <span className="field-label">Reply to A0</span>
        <textarea className="field-input field-textarea" value={replyDraft} onChange={(event) => onReplyChange(item.id, event.target.value)} placeholder="Give A0 the decision, constraint, or unblock instruction." />
      </label>
      {item.task_id ? (
        <div className="toolbar-group a0-actions">
          <button className="ghost" type="button" onClick={() => onPrepareWorkflow(item, 'replan')}>Prep replan</button>
          <button className="ghost" type="button" onClick={() => onPrepareWorkflow(item, 'reassign')}>Prep reassign</button>
          <button className="ghost" type="button" onClick={() => onPrepareWorkflow(item, 'reopen')}>Prep reopen</button>
        </div>
      ) : null}
      <div className="toolbar-group a0-actions">
        <button type="button" onClick={() => onReply(item, primaryAction.action)}>{primaryAction.label}</button>
        <button className={secondaryAction.className} type="button" onClick={() => onReply(item, secondaryAction.action)}>{secondaryAction.label}</button>
        {item.request_type === 'worker_intervention' ? <button className="danger-outline" type="button" onClick={() => onReply(item, 'blocked')}>Still blocked</button> : null}
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
      <div className="merge-attention"><strong>Message</strong> {item.body}</div>
      {item.related_task_ids?.length ? <div className="merge-note"><strong>Tasks</strong> {item.related_task_ids.join(', ')}</div> : null}
      <div className="merge-note"><strong>Created</strong> {item.created_at}</div>
      <div className="toolbar-group a0-actions">
        <button className="ghost" type="button" onClick={() => onAck(item.id, 'seen')}>Mark seen</button>
        <button type="button" onClick={() => onAck(item.id, 'resolved')}>Resolve</button>
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
            <span>{item.runtime_status || 'runtime unknown'}</span>
            <span className="merge-arrow">-&gt;</span>
            <span>{item.heartbeat_state || 'heartbeat unknown'}</span>
          </div>
        </div>
        <span className={classNames('chip', item.ready ? 'state-active' : 'state-stale')}>{item.ready ? 'Ready' : 'Blocked'}</span>
      </div>
      {item.blockers.length ? <div className="merge-list-block"><strong>Blockers</strong><ul>{item.blockers.map((entry) => <li key={`${item.agent}-${entry}`}>{entry}</li>)}</ul></div> : <div className="small muted">No cleanup blockers remain for this worker.</div>}
      <div className="toolbar-group a0-actions">
        <button type="button" onClick={() => onStopWorker(item.agent)} disabled={disabled || !item.active}>Shut down worker</button>
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
          <h2>Mailbox Composer</h2>
          <p className="small">Send durable coordination notes through the team mailbox so they survive worker restarts and provider changes.</p>
        </div>
      </div>
      <section className="grid">
        <SelectField label="From" value={draft.from} onChange={(value) => onChange('from', value)} options={participants} />
        <SelectField label="To" value={draft.to} onChange={(value) => onChange('to', value)} options={recipientOptions} />
      </section>
      <section className="grid">
        <SelectField label="Topic" value={draft.topic} onChange={(value) => onChange('topic', value)} options={['status_note', 'blocker', 'handoff', 'review_request', 'design_question']} />
        <SelectField label="Scope" value={draft.scope} onChange={(value) => onChange('scope', value)} options={['direct', 'broadcast', 'manager']} />
      </section>
      <Field label="Related tasks" value={draft.relatedTaskIds} onChange={(value) => onChange('relatedTaskIds', value)} helpText="Optional comma-separated task ids." placeholder="A1-001, A6-001" />
      <label className="field">
        <span className="field-label">Message body</span>
        <textarea className="field-input field-textarea" value={draft.body} onChange={(event) => onChange('body', event.target.value)} placeholder="Write the durable coordination note that should land in the shared mailbox." />
      </label>
      <div className="toolbar-group a0-actions">
        <button type="button" onClick={onSend} disabled={disabled || !draft.from || !draft.to || !draft.body.trim()}>Send mailbox message</button>
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
          <h2>Workflow Brief</h2>
          <p className="small">A0 can scan the current delivery lane before changing ownership, review gates, or task sequencing.</p>
        </div>
      </div>
      <div className="stack-list">
        {lines.map((line) => <div key={line} className="subcard"><p>{line}</p></div>)}
      </div>
      <div className="stack-list">
        {tasks.length ? tasks.map((task) => (
          <div key={task.id} className="subcard">
            <div className="subcard-title">{task.id} · {task.title}</div>
            <div className="small muted">{task.owner || 'unassigned'} · {task.status} · {task.claim_state || 'unclaimed'} · {task.plan_state || 'none'}</div>
            {task.dependencies?.length ? <p className="small">Depends on {task.dependencies.join(', ')}</p> : null}
          </div>
        )) : <div className="small muted">No workflow items available.</div>}
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
          <h2>Mailbox Peek</h2>
          <p className="small">Recent unresolved coordination notes, without leaving the current operating view.</p>
        </div>
        <div className="small muted">{data.team_mailbox.pending_count} open</div>
      </div>
      <div className="stack-list">
        {messages.length ? messages.map((item) => (
          <div key={item.id} className="subcard">
            <div className="subcard-title">{item.topic}</div>
            <div className="small muted">{item.from} -&gt; {item.to} · {item.ack_state} · {item.created_at}</div>
            <p>{item.body}</p>
            {item.related_task_ids?.length ? <div className="small muted">Tasks: {item.related_task_ids.join(', ')}</div> : null}
          </div>
        )) : <div className="small muted">No unresolved mailbox items.</div>}
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
          <h2>Workflow Replan</h2>
          <p className="small">A0 can rewrite ownership, claim state, review posture, and plan intent directly from the control plane.</p>
        </div>
      </div>
      <section className="grid">
        <SelectField label="Task" value={draft.taskId} onChange={(value) => onChange('taskId', value)} options={taskOptions} />
        <Field label="Gate" value={draft.gate} onChange={(value) => onChange('gate', value)} placeholder="gate name" />
      </section>
      <section className="grid">
        <Field label="Title" value={draft.title} onChange={(value) => onChange('title', value)} />
        <Field label="Priority" value={draft.priority} onChange={(value) => onChange('priority', value)} placeholder="P0 / P1" />
      </section>
      <section className="grid">
        <SelectField label="Owner" value={draft.owner} onChange={(value) => onChange('owner', value)} options={participants} />
        <SelectField label="Claimed By" value={draft.claimedBy} onChange={(value) => onChange('claimedBy', value)} options={participants} />
      </section>
      <section className="grid">
        <SelectField label="Status" value={draft.status} onChange={(value) => onChange('status', value)} options={['pending', 'active', 'blocked', 'review', 'completed']} />
        <SelectField label="Claim State" value={draft.claimState} onChange={(value) => onChange('claimState', value)} options={['unclaimed', 'claimed', 'in_progress', 'review', 'completed']} />
      </section>
      <section className="grid">
        <SelectField label="Plan Required" value={draft.planRequired} onChange={(value) => onChange('planRequired', value)} options={['yes', 'no']} />
        <SelectField label="Plan State" value={draft.planState} onChange={(value) => onChange('planState', value)} options={['none', 'pending_review', 'approved', 'rejected']} />
      </section>
      <Field label="Dependencies" value={draft.dependencies} onChange={(value) => onChange('dependencies', value)} helpText="Comma-separated task ids." placeholder="A1-001, A2-001" />
      <label className="field">
        <span className="field-label">Plan Summary</span>
        <textarea className="field-input field-textarea" value={draft.planSummary} onChange={(event) => onChange('planSummary', event.target.value)} placeholder="Rewrite the implementation plan or approval expectations." />
      </label>
      <section className="grid">
        <Field label="Claim Note" value={draft.claimNote} onChange={(value) => onChange('claimNote', value)} placeholder="Current ownership note" />
        <Field label="Review Note" value={draft.reviewNote} onChange={(value) => onChange('reviewNote', value)} placeholder="Acceptance or reopen note" />
      </section>
      <label className="field">
        <span className="field-label">Manager Note</span>
        <textarea className="field-input field-textarea" value={draft.managerNote} onChange={(event) => onChange('managerNote', event.target.value)} placeholder="Optional durable note to send with the workflow change." />
      </label>
      <div className="toolbar-group a0-actions">
        <button type="button" onClick={onSubmit} disabled={disabled || !draft.taskId}>Apply workflow update</button>
      </div>
    </section>
  );
}

export function AutomationSummary({ draftConfig, data }: { draftConfig: ConfigShape; data: DashboardState }) {
  const plannedWorkers = buildPlannedWorkers(data, draftConfig);
  const autoManaged = [
    'Repository name and dashboard host/port defaults',
    'Worker roster from backlog and runtime state',
    'Worker task IDs from the current plan',
    'Suggested branch names from task ownership and title',
    'Worktree paths from repo root plus agent ID',
    'Task-aware resource-pool recommendation and lock from provider quality history',
    'Default pool queue from live provider ranking',
    'Environment type/path defaults',
    'Default sync command',
    'Default submit strategy',
    'Task-aware test-command selection with safe fallbacks',
  ];
  const userOnly = [
    'Local repo root if A0 cannot infer it correctly',
    'Reference workspace path when the project really needs one',
    'Integration branch policy',
    'Resource-pool credentials, provider choice, and model choice',
    'Only exceptional per-worker routing or environment overrides that truly differ from the default path',
  ];

  return (
    <section className="helper-card settings-card settings-card-wide">
      <div className="section-head">
        <h3>A0-Managed Defaults</h3>
        <div className="small muted">{autoManaged.length} areas auto-managed, {userOnly.length} areas still need human confirmation</div>
      </div>
      <p className="small muted">Planned workers currently detected: {plannedWorkers.map((worker) => worker.agent).join(', ') || 'none'}. In Settings, A0 plan means the derived target state; override means a human-pinned exception that should be rare and easy to reset.</p>
      <div className="automation-grid">
        <div className="subcard">
          <div className="subcard-title">You should usually not need to fill these by hand</div>
          <ul className="automation-list">
            {autoManaged.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
        <div className="subcard">
          <div className="subcard-title">You should mostly only confirm these</div>
          <ul className="automation-list">
            {userOnly.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
      </div>
    </section>
  );
}
