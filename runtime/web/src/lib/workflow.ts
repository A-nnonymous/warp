import type { A0ConsoleRequest, BacklogItem, DashboardState, TeamMailboxMessage } from '../types';
import type { WorkflowDraft, WorkflowPresetAction } from './local-types';
import { DEFAULT_WORKFLOW_DRAFT } from './local-types';
import { stringifyQueue, translateUiText } from './utils';

export function workflowDraftFromTask(task?: BacklogItem): WorkflowDraft {
  if (!task) {
    return { ...DEFAULT_WORKFLOW_DRAFT };
  }
  return {
    taskId: task.id || '',
    title: task.title || '',
    owner: task.owner || '',
    claimedBy: task.claimed_by || '',
    status: task.status || 'pending',
    claimState: task.claim_state || (task.claimed_by ? 'claimed' : 'unclaimed'),
    gate: task.gate || '',
    priority: task.priority || '',
    dependencies: stringifyQueue(task.dependencies),
    planRequired: task.plan_required ? 'yes' : 'no',
    planState: task.plan_state || 'none',
    planSummary: task.plan_summary || '',
    claimNote: task.claim_note || '',
    reviewNote: task.review_note || '',
    managerNote: '',
  };
}

export function workflowDraftFromRequest(data: DashboardState, request: A0ConsoleRequest, action: WorkflowPresetAction): WorkflowDraft {
  const task = pickWorkflowTask(data, request.task_id || '');
  const base = workflowDraftFromTask(task);
  const taskId = request.task_id || base.taskId;
  const agent = request.agent || base.claimedBy || base.owner;
  const title = task?.title || base.title || request.title || taskId;
  const contextNote = request.body || request.response_note || request.resume_instruction || '';
  if (action === 'replan') {
    return {
      ...base,
      taskId,
      title,
      owner: base.owner || agent,
      claimedBy: agent,
      status: 'pending',
      claimState: agent ? 'claimed' : 'unclaimed',
      planRequired: 'yes',
      planState: 'pending_review',
      planSummary: base.planSummary || contextNote,
      reviewNote: '',
      managerNote: `来自 ${request.id} 的重规划请求：${contextNote}`.trim(),
    };
  }
  if (action === 'reassign') {
    return {
      ...base,
      taskId,
      title,
      owner: '',
      claimedBy: '',
      status: 'pending',
      claimState: 'unclaimed',
      claimNote: '',
      reviewNote: '',
      managerNote: `来自 ${request.id} 的重新分配请求：${contextNote}`.trim(),
    };
  }
  return {
    ...base,
    taskId,
    title,
    owner: base.owner || agent,
    claimedBy: base.claimedBy || agent,
    status: 'pending',
    claimState: (base.claimedBy || agent) ? 'claimed' : 'unclaimed',
    reviewNote: `由 ${request.id} 重新打开：${contextNote}`.trim(),
    managerNote: `来自 ${request.id} 的重新打开请求：${contextNote}`.trim(),
  };
}

export function pickWorkflowTask(data: DashboardState | null, taskId = ''): BacklogItem | undefined {
  const items = data?.backlog?.items || [];
  if (!items.length) {
    return undefined;
  }
  if (taskId) {
    const matching = items.find((item) => item.id === taskId);
    if (matching) {
      return matching;
    }
  }
  const requestTaskId = (data?.a0_console?.requests || []).find((item) => item.task_id)?.task_id;
  if (requestTaskId) {
    const matching = items.find((item) => item.id === requestTaskId);
    if (matching) {
      return matching;
    }
  }
  return items.find((item) => item.status !== 'completed') || items[0];
}

export function workflowBriefLines(data: DashboardState): string[] {
  const items = data.backlog.items || [];
  const active = items.filter((item) => item.status === 'active' || item.claim_state === 'in_progress');
  const review = items.filter((item) => item.status === 'review' || item.claim_state === 'review');
  const blocked = items.filter((item) => item.status === 'blocked');
  const planPending = items.filter((item) => item.plan_state === 'pending_review');
  const cleanupBlockers = data.cleanup.blockers || [];
  return [
    `${active.length} 个任务进行中，${review.length} 个待评审，${blocked.length} 个阻塞`,
    `${planPending.length} 个计划待审批，A0 队列中有 ${data.a0_console.pending_count} 项`,
    cleanupBlockers.length ? `仍有 ${cleanupBlockers.length} 个清理阻塞项` : '清理通道已畅通',
  ];
}

export function workflowPeekTasks(data: DashboardState): BacklogItem[] {
  const items = data.backlog.items || [];
  const spotlight = items.filter((item) => item.status === 'review' || item.claim_state === 'review' || item.plan_state === 'pending_review' || item.status === 'blocked');
  if (spotlight.length) {
    return spotlight.slice(0, 6);
  }
  return items.filter((item) => item.status !== 'completed').slice(0, 6);
}

export function mailboxPeekMessages(data: DashboardState): TeamMailboxMessage[] {
  return (data.team_mailbox.messages || [])
    .filter((item) => item.ack_state !== 'resolved')
    .slice(-6)
    .reverse();
}
