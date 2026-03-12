import type { MailboxDraft, WorkflowDraft } from '../lib/local-types';
import type { DashboardState } from '../types';
import { classNames } from '../lib/utils';
import { projectReferenceWorkspace } from '../lib/utils';
import { renderValidation } from '../lib/data';
import { DataTable } from './shared';
import { CleanupWorkerCard, MailboxComposerCard, WorkflowBriefCard, MailboxPeekCard, WorkflowPatchCard } from './cards';

export function OperationsTab({
  data,
  mailboxDraft,
  workflowDraft,
  cleanupReleaseListener,
  onMailboxDraftChange,
  onWorkflowDraftChange,
  onSendMailboxMessage,
  onApplyWorkflowUpdate,
  onStopWorker,
  onCleanupReleaseChange,
  onConfirmCleanup,
  actionInFlight,
}: {
  data: DashboardState;
  mailboxDraft: MailboxDraft;
  workflowDraft: WorkflowDraft;
  cleanupReleaseListener: boolean;
  onMailboxDraftChange: (field: keyof MailboxDraft, value: string) => void;
  onWorkflowDraftChange: (field: keyof WorkflowDraft, value: string) => void;
  onSendMailboxMessage: () => void;
  onApplyWorkflowUpdate: () => void;
  onStopWorker: (agent: string) => void;
  onCleanupReleaseChange: (value: boolean) => void;
  onConfirmCleanup: () => void;
  actionInFlight: boolean;
}) {
  const projectRows = [
    { key: 'repository_name', value: data.project.repository_name || '' },
    { key: 'local_repo_root', value: data.project.local_repo_root || '' },
    { key: 'reference_workspace_root', value: projectReferenceWorkspace(data.project) },
    { key: 'integration_branch', value: data.project.integration_branch || data.project.base_branch || '' },
    { key: 'dashboard', value: data.project.dashboard?.host && data.project.dashboard?.port ? `${data.project.dashboard.host}:${data.project.dashboard.port}` : '' },
    { key: 'listener_active', value: data.mode.listener_active },
  ];
  const processRows = Object.entries(data.processes || {}).map(([agent, item]) => ({ agent, provider: item.provider, model: item.model, alive: item.alive, pid: item.pid, resource_pool: item.resource_pool, progress_pct: item.progress_pct, total_tokens: item.usage?.total_tokens || 0, phase: item.phase || item.last_log_line || '', recursion_guard: item.recursion_guard, wrapper_path: item.wrapper_path, returncode: item.returncode }));
  const mergeRows = data.merge_queue.map((item) => ({ agent: item.agent, branch: item.branch, submit_strategy: item.submit_strategy, worker_identity: item.worker_identity, merge_target: item.merge_target, status: item.status, manager_action: item.manager_action }));
  const providerRows = data.provider_queue.map((item) => ({ resource_pool: item.resource_pool, provider: item.provider, priority: item.priority, binary_found: item.binary_found, recursion_guard: item.recursion_guard, launch_wrapper: item.launch_wrapper, auth_mode: item.auth_mode, auth_ready: item.auth_ready, launch_ready: item.launch_ready, active_workers: item.active_workers, progress_pct: item.progress_pct ?? '', total_tokens: item.usage?.total_tokens || 0, auth_detail: item.auth_detail, connection_quality: item.connection_quality, work_quality: item.work_quality, score: item.score }));
  const backlogRows = (data.backlog.items || []).map((item) => ({ id: item.id, owner: item.owner, claimed_by: item.claimed_by || '', claim_state: item.claim_state || '', plan_state: item.plan_state || '', status: item.status, gate: item.gate, title: item.title }));
  const mailboxRows = (data.team_mailbox.messages || []).map((item) => ({ id: item.id, from: item.from, to: item.to, topic: item.topic, ack_state: item.ack_state, related_task_ids: (item.related_task_ids || []).join(', '), created_at: item.created_at, body: item.body }));
  const mailboxParticipants = Array.from(new Set(['A0', ...(data.resolved_workers || []).map((item) => item.agent).filter(Boolean)])).sort();
  const cleanup = data.cleanup;
  return (
    <div className="tab-body">
      <section className="grid">
        <WorkflowBriefCard data={data} />
        <MailboxPeekCard data={data} />
      </section>
      <section className="grid">
        <section className="card"><h2>Commands</h2><pre>{`serve:\n${data.commands.serve}\n\nup:\n${data.commands.up}`}</pre></section>
        <section className="card"><h2>Validation</h2><pre>{renderValidation(data)}</pre></section>
      </section>
      <section className="grid">
        <section className="card"><h2>Provider Queue</h2><DataTable columns={['resource_pool', 'provider', 'priority', 'binary_found', 'recursion_guard', 'launch_wrapper', 'auth_mode', 'auth_ready', 'launch_ready', 'active_workers', 'progress_pct', 'total_tokens', 'auth_detail', 'connection_quality', 'work_quality', 'score']} rows={providerRows} /></section>
        <section className="card"><h2>Merge Queue</h2><DataTable columns={['agent', 'branch', 'submit_strategy', 'worker_identity', 'merge_target', 'status', 'manager_action']} rows={mergeRows} /></section>
      </section>
      <section className="grid">
        <section className="card"><h2>Active Processes</h2><DataTable columns={['agent', 'provider', 'model', 'alive', 'pid', 'resource_pool', 'progress_pct', 'total_tokens', 'phase', 'recursion_guard', 'wrapper_path', 'returncode']} rows={processRows} /></section>
        <section className="card"><h2>Project</h2><DataTable columns={['key', 'value']} rows={projectRows} /></section>
      </section>
      <section className="grid">
        <section className="card"><h2>Runtime Topology</h2><DataTable columns={['agent', 'resource_pool', 'provider', 'model', 'branch', 'recursion_guard', 'launch_wrapper', 'status']} rows={data.runtime.workers || []} /></section>
        <section className="card"><h2>Heartbeats</h2><DataTable columns={['agent', 'state', 'last_seen', 'expected_next_checkin']} rows={data.heartbeats.agents || []} /></section>
      </section>
      <section className="grid">
        <section className="card"><h2>Backlog</h2><DataTable columns={['id', 'owner', 'claimed_by', 'claim_state', 'plan_state', 'status', 'gate', 'title']} rows={backlogRows} /></section>
        <section className="card"><h2>Gates</h2><DataTable columns={['id', 'name', 'status', 'owner']} rows={data.gates.gates || []} /></section>
      </section>
      <MailboxComposerCard draft={mailboxDraft} onChange={onMailboxDraftChange} onSend={onSendMailboxMessage} participants={mailboxParticipants} disabled={actionInFlight} />
      <WorkflowPatchCard data={data} draft={workflowDraft} onChange={onWorkflowDraftChange} onSubmit={onApplyWorkflowUpdate} disabled={actionInFlight} />
      <section className="card">
        <div className="panel-title">
          <div>
            <h2>Cleanup Readiness</h2>
            <p className="small">Cleanup remains blocked while workers are alive, reviews are unresolved, or single-writer locks are still held.</p>
          </div>
          <div className={classNames('chip', cleanup.ready ? 'state-active' : 'state-stale')}>{cleanup.ready ? 'Ready' : 'Blocked'}</div>
        </div>
        {cleanup.blockers.length ? <div className="merge-list-block"><strong>Cleanup blockers</strong><ul>{cleanup.blockers.map((entry) => <li key={entry}>{entry}</li>)}</ul></div> : <div className="small muted">No cleanup blockers remain. The team cleanup gate can be confirmed safely.</div>}
        <div className="toolbar-group a0-actions">
          <label className="toggle"><input type="checkbox" checked={cleanupReleaseListener} onChange={(event) => onCleanupReleaseChange(event.target.checked)} /> Auto-release listener after confirm</label>
          <button type="button" onClick={onConfirmCleanup} disabled={actionInFlight || !cleanup.ready}>Confirm cleanup gate</button>
        </div>
        <div className="merge-board">
          {(cleanup.workers || []).map((item) => <CleanupWorkerCard key={item.agent} item={item} onStopWorker={onStopWorker} disabled={actionInFlight} />)}
        </div>
      </section>
      <section className="card"><h2>Team Mailbox</h2><DataTable columns={['id', 'from', 'to', 'topic', 'ack_state', 'related_task_ids', 'created_at', 'body']} rows={mailboxRows} /></section>
      <section className="card"><h2>Manager Report</h2><pre>{data.manager_report}</pre></section>
    </div>
  );
}
