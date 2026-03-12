import type { ConfigShape, ConfigWorkerDefaults, LaunchStrategy, DashboardState, RuntimeWorker } from '../types';

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

export function displayState(value: string | undefined): string {
  return String(value || 'unknown').replaceAll('_', ' ');
}

export function stateClass(value: string | undefined): string {
  return `state-${String(value || 'unknown').replace(/[^a-zA-Z0-9]+/g, '_')}`;
}

export function renderCell(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return ' ';
  }
  if (typeof value === 'boolean') {
    return value ? 'yes' : 'no';
  }
  return String(value);
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
    return 'Initial Provider';
  }
  if (strategy === 'selected_model') {
    return 'Selected Model';
  }
  return 'Elastic';
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
