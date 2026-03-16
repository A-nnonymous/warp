import type { A0ConsoleRequest, DashboardState } from '../types';
import type { WorkflowDraft, WorkflowPresetAction } from '../lib/local-types';
import { classNames } from '../lib/utils';
import { A0RequestCard, MailboxCard, WorkflowBriefCard, MailboxPeekCard, WorkflowPatchCard } from './cards';

export function A0ConsoleView({
  data,
  standalone,
  replyDrafts,
  composer,
  workflowDraft,
  onReplyChange,
  onComposerChange,
  onWorkflowDraftChange,
  onReply,
  onSendMessage,
  onMailboxAck,
  onApplyWorkflowUpdate,
  onPrepareWorkflow,
}: {
  data: DashboardState;
  standalone?: boolean;
  replyDrafts: Record<string, string>;
  composer: string;
  workflowDraft: WorkflowDraft;
  onReplyChange: (requestId: string, value: string) => void;
  onComposerChange: (value: string) => void;
  onWorkflowDraftChange: (field: keyof WorkflowDraft, value: string) => void;
  onReply: (item: A0ConsoleRequest, action: string) => void;
  onSendMessage: () => void;
  onMailboxAck: (messageId: string, ackState: string) => void;
  onApplyWorkflowUpdate: () => void;
  onPrepareWorkflow: (item: A0ConsoleRequest, action: WorkflowPresetAction) => void;
}) {
  const requests = data.a0_console?.requests || [];
  const messages = data.a0_console?.messages || [];
  const inbox = data.a0_console?.inbox || [];
  return (
    <div className={classNames('tab-body', standalone && 'a0-console-body')}>
      <section className="grid">
        <WorkflowBriefCard data={data} />
        <MailboxPeekCard data={data} />
      </section>
      <section className="card">
        <div className="page-header">
          <div>
            <h2>A0 控制台</h2>
            <p className="small">用于审批、解阻和恢复说明的专用管理窗口。</p>
          </div>
          <div className="small muted">{data.a0_console.pending_count} 个待处理</div>
        </div>
        <label className="field">
          <span className="field-label">发给 A0 的消息</span>
          <textarea className="field-input field-textarea" value={composer} onChange={(event) => onComposerChange(event.target.value)} placeholder="向 A0 发送一条不绑定具体请求的直接消息。" />
        </label>
        <div className="toolbar-group a0-actions">
          <button type="button" onClick={onSendMessage} disabled={!composer.trim()}>发送给 A0</button>
        </div>
      </section>
      <WorkflowPatchCard data={data} draft={workflowDraft} onChange={onWorkflowDraftChange} onSubmit={onApplyWorkflowUpdate} />
      <section className="card">
        <div className="panel-title">
          <div>
            <h2>收件箱</h2>
            <p className="small">仍需要 A0 确认或关闭的 Worker 消息。</p>
          </div>
        </div>
        <div className="merge-board">
          {inbox.length ? inbox.map((item) => <MailboxCard key={item.id} item={item} onAck={onMailboxAck} />) : <div className="small muted">A0 当前没有未解决的邮箱消息。</div>}
        </div>
      </section>
      <section className="card">
        <div className="panel-title">
          <div>
            <h2>待处理请求</h2>
            <p className="small">这里汇总了当前需要你做决定或确认的事项。</p>
          </div>
        </div>
        <div className="merge-board">
          {requests.length ? requests.map((item) => (
            <A0RequestCard
              key={item.id}
              item={item}
              replyDraft={replyDrafts[item.id] || ''}
              onReplyChange={onReplyChange}
              onReply={onReply}
              onPrepareWorkflow={onPrepareWorkflow}
            />
          )) : <div className="small muted">当前没有打开的 A0 请求。</div>}
        </div>
      </section>
      <section className="card">
        <div className="panel-title">
          <div>
            <h2>对话记录</h2>
            <p className="small">控制平面记录的近期用户到 A0 的消息与请求响应。</p>
          </div>
        </div>
        <div className="stack-list">
          {messages.length ? messages.map((item) => <div key={item.id} className="subcard"><div className="subcard-title">{item.action || item.direction}</div><div className="small muted">{item.created_at}</div><p>{item.body}</p></div>) : <div className="small muted">当前还没有 A0 对话历史。</div>}
        </div>
      </section>
    </div>
  );
}
