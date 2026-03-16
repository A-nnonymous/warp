import type { ConfigShape, ConfigWorkerDefaults, LaunchStrategy, DashboardState, RuntimeWorker } from '../types';

const EXACT_TEXT: Record<string, string> = {
  unknown: '未知',
  none: '无',
  unassigned: '未分配',
  configured: '已配置',
  active: '运行中',
  healthy: '健康',
  pending: '待处理',
  blocked: '阻塞',
  review: '待评审',
  completed: '已完成',
  done: '已完成',
  merged: '已合并',
  claimed: '已认领',
  unclaimed: '未认领',
  answered: '已答复',
  resolved: '已解决',
  seen: '已查看',
  stale: '需关注',
  offline: '离线',
  stopped: '已停止',
  waiting: '等待中',
  parked: '已暂停',
  checkpointed: '已检查点',
  error: '错误',
  worker: 'Worker',
  manager: '管理者',
  direct: '定向',
  broadcast: '广播',
  status_note: '状态同步',
  blocker: '阻塞',
  handoff: '交接',
  review_request: '评审请求',
  design_question: '设计问题',
  pending_review: '待审批',
  approved: '已批准',
  rejected: '已拒绝',
  yes: '是',
  no: '否',
  process_running: '进程运行中',
  process_exit: '进程已退出',
  initial_provider: '初始 Provider',
  selected_model: '指定模型',
  elastic: '弹性调度',
};

const COLUMN_LABELS: Record<string, string> = {
  id: 'ID',
  key: '键',
  value: '值',
  agent: 'Agent',
  provider: 'Provider',
  model: '模型',
  alive: '存活',
  pid: 'PID',
  resource_pool: '资源池',
  progress_pct: '进度',
  total_tokens: '总 Token',
  phase: '阶段',
  recursion_guard: '递归保护',
  wrapper_path: '包装器路径',
  returncode: '返回码',
  branch: '分支',
  submit_strategy: '提交策略',
  worker_identity: 'Worker 身份',
  merge_target: '合并目标',
  status: '状态',
  manager_action: '管理动作',
  binary_found: '二进制可用',
  launch_wrapper: '启动包装器',
  auth_mode: '认证模式',
  auth_ready: '认证就绪',
  launch_ready: '可启动',
  active_workers: '活跃 Worker',
  auth_detail: '认证详情',
  connection_quality: '连接质量',
  work_quality: '工作质量',
  score: '评分',
  state: '心跳状态',
  last_seen: '最近心跳',
  expected_next_checkin: '下次预期签到',
  owner: '负责人',
  claimed_by: '认领者',
  claim_state: '认领状态',
  plan_state: '计划状态',
  gate: 'Gate',
  title: '标题',
  name: '名称',
  from: '发件人',
  to: '收件人',
  topic: '主题',
  ack_state: '确认状态',
  related_task_ids: '相关任务',
  created_at: '创建时间',
  body: '内容',
};

export function normalizedText(value: unknown): string {
  return String(value ?? '').trim();
}

export function isAutoManagedBlank(value: unknown): boolean {
  const normalized = normalizedText(value).toLowerCase();
  return !normalized || normalized === 'unassigned';
}

export function isAutoManagedCommandBlank(value: unknown): boolean {
  const normalized = normalizedText(value).toLowerCase();
  return !normalized || normalized === 'unassigned' || normalized === 'none';
}

export function isPlaceholderPath(value: unknown): boolean {
  const normalized = normalizedText(value);
  return Boolean(normalized) && (normalized.startsWith('/absolute/path/') || normalized === 'unassigned' || normalized === 'none');
}

export function firstMeaningfulValue(...values: unknown[]): string {
  for (const value of values) {
    if (!isAutoManagedBlank(value)) {
      return normalizedText(value);
    }
  }
  return '';
}

export function firstMeaningfulCommand(...values: unknown[]): string {
  for (const value of values) {
    if (!isAutoManagedCommandBlank(value)) {
      return normalizedText(value);
    }
  }
  return '';
}

export function firstMeaningfulPath(...values: unknown[]): string {
  for (const value of values) {
    if (!isAutoManagedBlank(value) && !isPlaceholderPath(value)) {
      return normalizedText(value);
    }
  }
  return '';
}

export function classNames(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(' ');
}

export function translateUiText(value: string | undefined): string {
  const original = normalizedText(value);
  if (!original) {
    return '';
  }
  const exact = EXACT_TEXT[original] || EXACT_TEXT[original.toLowerCase()];
  if (exact) {
    return exact;
  }
  return original
    .replace(/validation issue\(s\)/g, '校验问题')
    .replace(/launch blocker\(s\)/g, '启动阻塞项')
    .replace(/approval request\(s\)/g, '审批请求')
    .replace(/pending request\(s\)/g, '待处理请求')
    .replace(/open message\(s\)/g, '未处理消息')
    .replace(/active or healthy/g, '运行中或健康')
    .replace(/ready for review/g, '可评审')
    .replace(/in progress/g, '进行中')
    .replace(/needs attention/g, '需关注')
    .replace(/no recent activity/g, '近期无活动')
    .replace(/waiting for launch/g, '等待启动')
    .replace(/A0 manager identity/g, 'A0 管理身份')
    .replace(/process is still alive/g, '进程仍在运行')
    .replace(/pending plan approvals:/g, '待审批计划：')
    .replace(/pending task reviews:/g, '待处理任务评审：')
    .replace(/locks still held:/g, '仍持有锁：')
    .replace(/active workers must be stopped:/g, '必须先停止的活跃 Worker：')
    .replace(/outstanding single-writer locks:/g, '仍未释放的单写锁：')
    .replace(/requested unlocks:/g, '请求解锁：')
    .replace(/blockers:/g, '阻塞项：')
    .replace(/line\(s\)/g, '行')
    .replace(/agent\(s\) with output/g, '个 Agent 有输出')
    .replace(/gates passed/g, '个 Gate 已通过')
    .replace(/mailbox is clear/g, '邮箱已清空')
    .replace(/no pending requests/g, '无待处理请求')
    .replace(/ready to launch/g, '可启动')
    .replace(/within monitor loop interval/g, '监控轮询周期内')
    .replace(/when listener restarts/g, '监听器重启后')
    .replace(/worker exited cleanly/g, 'Worker 已正常退出')
    .replace(/worker exited with/g, 'Worker 退出码')
    .replace(/process running/g, '进程运行中')
    .replace(/no runtime heartbeat yet/g, '尚无运行时心跳')
    .replace(/listener active/g, '监听器运行中')
    .replace(/listener offline/g, '监听器离线')
    .replace(/All gates passed/g, '全部 Gate 已通过')
    .replace(/No data/g, '暂无数据');
}

export function translateColumnLabel(column: string): string {
  return COLUMN_LABELS[column] || translateUiText(column.replaceAll('_', ' '));
}

export function translateOptionLabel(value: string): string {
  return translateUiText(value.replaceAll('_', ' ')) || value;
}

export function displayState(value: string | undefined): string {
  return translateUiText(String(value || 'unknown').replaceAll('_', ' '));
}

export function stateClass(value: string | undefined): string {
  return `state-${String(value || 'unknown').replace(/[^a-zA-Z0-9]+/g, '_')}`;
}

export function renderCell(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return ' ';
  }
  if (typeof value === 'boolean') {
    return value ? '是' : '否';
  }
  return translateUiText(String(value));
}

export function formatTokenCount(value: unknown): string {
  const amount = Number(value || 0);
  if (!Number.isFinite(amount) || amount <= 0) {
    return '0';
  }
  return amount.toLocaleString();
}

export function cloneConfig(config: ConfigShape | undefined): ConfigShape {
  if (!config) {
    return { project: {}, providers: {}, resource_pools: {}, worker_defaults: {}, workers: [] };
  }
  return JSON.parse(JSON.stringify(config)) as ConfigShape;
}

export function normalizeConfig(config: ConfigShape): ConfigShape {
  return {
    project: config.project || {},
    providers: config.providers || {},
    resource_pools: config.resource_pools || {},
    worker_defaults: config.worker_defaults || {},
    workers: config.workers || [],
  };
}

export function parseQueue(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

export function stringifyQueue(values: string[] | undefined): string {
  return (values || []).join(', ');
}

export function launchStrategyLabel(strategy: LaunchStrategy): string {
  if (strategy === 'initial_provider') {
    return '初始 Provider';
  }
  if (strategy === 'selected_model') {
    return '指定模型';
  }
  return '弹性调度';
}

export function tabLabel(tab: string): string {
  if (tab === 'overview') {
    return '总览';
  }
  if (tab === 'operations') {
    return '运行';
  }
  if (tab === 'settings') {
    return '设置';
  }
  return tab;
}

export function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .replace(/_{2,}/g, '_');
}

export function preferredLaunchProvider(launchPolicy: DashboardState['launch_policy']): string {
  return launchPolicy.default_provider || launchPolicy.initial_provider || launchPolicy.available_providers[0] || '';
}

export async function writeClipboard(text: string): Promise<void> {
  await navigator.clipboard.writeText(text);
}

export function projectReferenceWorkspace(project: ConfigShape['project']): string {
  return normalizedText(project?.reference_workspace_root) || normalizedText(project?.paddle_repo_path);
}
