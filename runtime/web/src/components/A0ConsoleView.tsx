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
            <h2>A0 Console</h2>
            <p className="small">Dedicated manager window for approvals, unblock instructions, and resume notes.</p>
          </div>
          <div className="small muted">{data.a0_console.pending_count} pending</div>
        </div>
        <label className="field">
          <span className="field-label">Message to A0</span>
          <textarea className="field-input field-textarea" value={composer} onChange={(event) => onComposerChange(event.target.value)} placeholder="Send a direct note to A0 outside a specific request." />
        </label>
        <div className="toolbar-group a0-actions">
          <button type="button" onClick={onSendMessage} disabled={!composer.trim()}>Send to A0</button>
        </div>
      </section>
      <WorkflowPatchCard data={data} draft={workflowDraft} onChange={onWorkflowDraftChange} onSubmit={onApplyWorkflowUpdate} />
      <section className="card">
        <div className="panel-title">
          <div>
            <h2>Inbox</h2>
            <p className="small">Worker messages that still need acknowledgement or closure from A0.</p>
          </div>
        </div>
        <div className="merge-board">
          {inbox.length ? inbox.map((item) => <MailboxCard key={item.id} item={item} onAck={onMailboxAck} />) : <div className="small muted">No unresolved mailbox items for A0.</div>}
        </div>
      </section>
      <section className="card">
        <div className="panel-title">
          <div>
            <h2>Pending Requests</h2>
            <p className="small">These are the cases where A0 currently needs your decision or confirmation.</p>
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
          )) : <div className="small muted">No open A0 requests.</div>}
        </div>
      </section>
      <section className="card">
        <div className="panel-title">
          <div>
            <h2>Conversation Log</h2>
            <p className="small">Recent user-to-A0 messages and request responses recorded by the control plane.</p>
          </div>
        </div>
        <div className="stack-list">
          {messages.length ? messages.map((item) => <div key={item.id} className="subcard"><div className="subcard-title">{item.action || item.direction}</div><div className="small muted">{item.created_at}</div><p>{item.body}</p></div>) : <div className="small muted">No A0 conversation history yet.</div>}
        </div>
      </section>
    </div>
  );
}
