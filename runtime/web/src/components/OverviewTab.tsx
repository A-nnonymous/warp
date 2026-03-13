import type { AgentRow, ProgressModel } from '../lib/local-types';
import type { DashboardState } from '../types';
import { formatTokenCount } from '../lib/utils';
import { Metric, ProgressRow, HelperCard } from './shared';
import { MergeCard, AgentCard } from './cards';
import { AgentPeekPanel } from './AgentPeekPanel';

export function OverviewTab({ data, agentRows, progress, onOpenA0Console }: { data: DashboardState; agentRows: AgentRow[]; progress: ProgressModel; onOpenA0Console: () => void }) {
  const mergeQueue = data.merge_queue || [];
  const mergeReady = mergeQueue.filter((item) => ['offline', 'stopped'].includes(String(item.status))).length;
  const mergeActive = mergeQueue.filter((item) => ['active', 'healthy'].includes(String(item.status))).length;
  const duccPool = data.provider_queue.find((item) => item.provider === 'ducc');
  return (
    <div className="tab-body">
      <section className="overview-hero">
        <section className="card progress-card">
          <div className="page-header">
            <div>
              <h2>Overall Progress</h2>
              <p className="small">A compact view of delivery momentum and the current control-plane state.</p>
            </div>
            <div className="small muted">{progress.passedGates}/{progress.totalGates} gates passed</div>
          </div>
          <div className="progress-bar"><div className="progress-fill" style={{ width: `${progress.progress}%` }} /></div>
          <div className="summary">
            <Metric label="Agents" value={agentRows.length} hint={`${progress.activeAgents} active or healthy`} />
            <Metric label="Overall Progress" value={`${progress.progress}%`} hint={`${progress.passedGates}/${progress.totalGates} gates passed`} />
            <Metric label="Attention Needed" value={progress.attentionAgents} hint={`${progress.blockedItems} backlog items blocked`} />
            <Metric label="Pending Reviews" value={progress.reviewItems + progress.planPending} hint={`${progress.mailboxPending} mailbox item(s) open`} />
          </div>
          <div className="progress-list">
            <ProgressRow label="Backlog" value={`${progress.completedItems}/${progress.totalItems} completed`} />
            <ProgressRow label="Blocked work" value={`${progress.blockedItems} items`} />
            <ProgressRow label="Claimed work" value={`${progress.claimedItems} items`} />
            <ProgressRow label="Awaiting review" value={`${progress.reviewItems} handoff(s), ${progress.planPending} plan(s)`} />
            <ProgressRow label="Agents needing action" value={`${progress.attentionAgents}`} />
            <ProgressRow label="Current gate" value={progress.openGate ? `${progress.openGate.id} · ${progress.openGate.name}` : 'All gates passed'} />
          </div>
        </section>
        <section className="card">
          <div className="page-header">
            <div>
              <h2>Program Snapshot</h2>
              <p className="small">What is blocked, what is runnable, and which event happened last.</p>
            </div>
          </div>
          <div className="helper-list">
            <HelperCard title="Startup state" body={data.mode.reason || data.mode.state} />
            <HelperCard title="Config target" body={data.mode.persist_config_path} />
            <HelperCard title="Last event" body={data.last_event || 'none'} />
            <HelperCard title="Launch posture" body={data.launch_blockers.length ? `${data.launch_blockers.length} blocker(s)` : 'ready to launch'} />
            <HelperCard title="A0 approvals" body={data.a0_console.pending_count ? `${data.a0_console.pending_count} pending request(s)` : 'no pending requests'} />
            <HelperCard title="Team mailbox" body={data.team_mailbox.pending_count ? `${data.team_mailbox.pending_count} open message(s)` : 'mailbox is clear'} />
            <HelperCard title="Cleanup" body={data.cleanup.ready ? 'ready to release the team' : `${data.cleanup.blockers.length} cleanup blocker(s)`} />
            <HelperCard title="ducc pool" body={duccPool ? `${duccPool.active_workers} active · ${formatTokenCount(duccPool.usage?.total_tokens)} tokens` : 'ducc pool not configured'} />
          </div>
          <div className="toolbar-group">
            <button className="ghost" type="button" onClick={onOpenA0Console}>Open A0 Console</button>
          </div>
        </section>
      </section>

      <section className="card">
        <div className="panel-title">
          <div>
            <h2>Branch Merge Status</h2>
            <p className="small">Manager-owned merge visibility for every worker branch.</p>
          </div>
          <div className="small muted">{mergeActive} in progress, {mergeReady} ready for review</div>
        </div>
        <div className="merge-board">
          {mergeQueue.length ? mergeQueue.map((item) => <MergeCard key={`${item.agent}-${item.branch}`} item={item} />) : <div className="small muted">No worker branches registered for manager merge review.</div>}
        </div>
      </section>

      <AgentPeekPanel data={data} />

      <section className="card">
        <div className="panel-title">
          <div>
            <h2>Agent Dashboards</h2>
            <p className="small">Health, execution context, and current ownership.</p>
          </div>
          <div className="small muted">{progress.activeAgents} active, {progress.attentionAgents} need attention</div>
        </div>
        <div className="agent-wall">
          {agentRows.map((item) => <AgentCard key={item.agent} item={item} />)}
        </div>
      </section>
    </div>
  );
}
