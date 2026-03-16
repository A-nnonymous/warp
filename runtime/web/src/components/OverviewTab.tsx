import type { AgentRow, ProgressModel } from '../lib/local-types';
import type { DashboardState } from '../types';
import { formatTokenCount, translateUiText } from '../lib/utils';
import { Metric, ProgressRow, HelperCard } from './shared';
import { MergeCard, AgentCard } from './cards';
import { AgentPeekPanel } from './AgentPeekPanel';
import { TaskDAG } from './TaskDAG';

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
              <h2>整体进度</h2>
              <p className="small">交付推进情况与当前控制面状态的紧凑视图。</p>
            </div>
            <div className="small muted">{progress.passedGates}/{progress.totalGates} 个 Gate 已通过</div>
          </div>
          <div className="progress-bar"><div className="progress-fill" style={{ width: `${progress.progress}%` }} /></div>
          <div className="summary">
            <Metric label="Agent" value={agentRows.length} hint={`${progress.activeAgents} 个运行中或健康`} />
            <Metric label="整体进度" value={`${progress.progress}%`} hint={`${progress.passedGates}/${progress.totalGates} 个 Gate 已通过`} />
            <Metric label="需关注" value={progress.attentionAgents} hint={`${progress.blockedItems} 个 backlog 项被阻塞`} />
            <Metric label="待评审" value={progress.reviewItems + progress.planPending} hint={`${progress.mailboxPending} 条邮箱消息未处理`} />
          </div>
          <div className="progress-list">
            <ProgressRow label="Backlog" value={`${progress.completedItems}/${progress.totalItems} 已完成`} />
            <ProgressRow label="阻塞任务" value={`${progress.blockedItems} 项`} />
            <ProgressRow label="已认领任务" value={`${progress.claimedItems} 项`} />
            <ProgressRow label="等待评审" value={`${progress.reviewItems} 个交接，${progress.planPending} 个计划`} />
            <ProgressRow label="需处理 Agent" value={`${progress.attentionAgents}`} />
            <ProgressRow label="当前 Gate" value={progress.openGate ? `${progress.openGate.id} · ${progress.openGate.name}` : '全部 Gate 已通过'} />
          </div>
        </section>
        <section className="card">
          <div className="page-header">
            <div>
              <h2>运行快照</h2>
              <p className="small">当前哪些内容被阻塞、哪些可以运行、最近发生了什么事件。</p>
            </div>
          </div>
          <div className="helper-list">
            <HelperCard title="启动状态" body={translateUiText(data.mode.reason || data.mode.state)} />
            <HelperCard title="配置目标" body={data.mode.persist_config_path} />
            <HelperCard title="最新事件" body={data.last_event || '无'} />
            <HelperCard title="启动条件" body={data.launch_blockers.length ? `${data.launch_blockers.length} 个阻塞项` : '可启动'} />
            <HelperCard title="A0 审批" body={data.a0_console.pending_count ? `${data.a0_console.pending_count} 个待处理请求` : '无待处理请求'} />
            <HelperCard title="团队邮箱" body={data.team_mailbox.pending_count ? `${data.team_mailbox.pending_count} 条未处理消息` : '邮箱已清空'} />
            <HelperCard title="清理状态" body={data.cleanup.ready ? '可以释放团队' : `${data.cleanup.blockers.length} 个清理阻塞项`} />
            <HelperCard title="ducc 资源池" body={duccPool ? `${duccPool.active_workers} 个活跃 · ${formatTokenCount(duccPool.usage?.total_tokens)} token` : 'ducc 资源池未配置'} />
          </div>
          <div className="toolbar-group">
            <button className="ghost" type="button" onClick={onOpenA0Console}>打开 A0 控制台</button>
          </div>
        </section>
      </section>

      <TaskDAG data={data} />

      <AgentPeekPanel data={data} />

      <section className="card">
        <div className="panel-title">
          <div>
            <h2>分支合并状态</h2>
            <p className="small">由管理者掌握的各 Worker 分支合并可见性。</p>
          </div>
          <div className="small muted">{mergeActive} 个进行中，{mergeReady} 个待评审</div>
        </div>
        <div className="merge-board">
          {mergeQueue.length ? mergeQueue.map((item) => <MergeCard key={`${item.agent}-${item.branch}`} item={item} />) : <div className="small muted">当前没有登记到管理者合并评审的 Worker 分支。</div>}
        </div>
      </section>

      <section className="card">
        <div className="panel-title">
          <div>
            <h2>Agent 面板</h2>
            <p className="small">健康状态、执行上下文与当前归属。</p>
          </div>
          <div className="small muted">{progress.activeAgents} 个活跃，{progress.attentionAgents} 个需关注</div>
        </div>
        <div className="agent-wall">
          {agentRows.map((item) => <AgentCard key={item.agent} item={item} />)}
        </div>
      </section>
    </div>
  );
}
