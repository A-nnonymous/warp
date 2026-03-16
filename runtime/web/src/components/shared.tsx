import type { ReactNode } from 'react';
import type { ConfigSection, ValidationIssue } from '../types';
import { classNames, renderCell, translateColumnLabel, translateOptionLabel } from '../lib/utils';

export function DataTable({ columns, rows }: { columns: string[]; rows: Array<Record<string, unknown>> }) {
  if (!rows.length) {
    return <div className="small muted">暂无数据</div>;
  }
  return (
    <div className="table-shell">
      <table>
        <thead>
          <tr>{columns.map((column) => <th key={column}>{translateColumnLabel(column)}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {columns.map((column) => <td key={column}>{renderCell(row[column])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Field({
  label,
  value,
  onChange,
  issues,
  helpText,
  placeholder,
  type = 'text',
}: {
  label: string;
  value: string | number;
  onChange: (value: string) => void;
  issues?: string[];
  helpText?: string;
  placeholder?: string;
  type?: 'text' | 'number';
}) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      <input
        className={classNames('field-input', issues && issues.length > 0 && 'field-input-error')}
        type={type}
        value={value ?? ''}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
      {helpText ? <span className="field-help">{helpText}</span> : null}
      {issues && issues.length > 0 ? <span className="field-error">{issues[0]}</span> : null}
    </label>
  );
}

export function SelectField({
  label,
  value,
  onChange,
  issues,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  issues?: string[];
  options: string[];
}) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      <select className={classNames('field-input', issues && issues.length > 0 && 'field-input-error')} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">请选择…</option>
        {options.map((option) => <option key={option} value={option}>{translateOptionLabel(option)}</option>)}
      </select>
      {issues && issues.length > 0 ? <span className="field-error">{issues[0]}</span> : null}
    </label>
  );
}

export function SectionIssueList({ issues }: { issues: ValidationIssue[] }) {
  if (!issues.length) {
    return null;
  }
  return (
    <div className="settings-issues">
      <h3>校验提示</h3>
      <ul>
        {issues.map((issue, index) => <li key={`${issue.field}-${index}`}>{issue.field}: {issue.message}</li>)}
      </ul>
    </div>
  );
}

export function SectionHeader({
  title,
  section,
  status,
  onValidate,
  onSave,
  action,
  subtitle,
}: {
  title: string;
  section: ConfigSection;
  status?: { message: string; error: boolean };
  onValidate: (section: ConfigSection) => void;
  onSave: (section: ConfigSection) => void;
  action?: ReactNode;
  subtitle?: ReactNode;
}) {
  return (
    <div className="section-head section-head-actions">
      <div>
        <h3>{title}</h3>
        {subtitle ? <div className="section-subtitle small muted">{subtitle}</div> : null}
      </div>
      <div className="section-actions">
        {status?.message ? <span className={classNames('section-status', status.error && 'error')}>{status.message}</span> : null}
        <button className="ghost" type="button" onClick={() => onValidate(section)}>校验</button>
        <button type="button" onClick={() => onSave(section)}>保存</button>
        {action}
      </div>
    </div>
  );
}

export function Metric({ label, value, hint }: { label: string; value: string | number; hint: string }) {
  return <div className="metric"><strong>{value}</strong><div>{label}</div><div className="small">{hint}</div></div>;
}

export function ProgressRow({ label, value }: { label: string; value: string }) {
  return <div className="progress-row"><span className="small">{label}</span><strong>{value}</strong></div>;
}

export function HelperCard({ title, body }: { title: string; body: string }) {
  return <section className="helper-card"><h3>{title}</h3><p className="small">{body}</p></section>;
}
