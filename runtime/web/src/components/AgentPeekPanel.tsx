import { useEffect, useRef } from 'react';
import type { DashboardState } from '../types';

const PEEK_WINDOW_LINES = 50;

export function AgentPeekPanel({ data }: { data: DashboardState }) {
  const peek = data.peek || {};
  const agents = Object.keys(peek).sort((a, b) => {
    const numA = Number(String(a).replace(/[^0-9]/g, ''));
    const numB = Number(String(b).replace(/[^0-9]/g, ''));
    return numA - numB;
  });

  // Also show agents from runtime that have no peek data yet
  const runtimeAgents = (data.runtime?.workers || []).map((w) => w.agent).filter(Boolean);
  const allAgents = Array.from(new Set([...agents, ...runtimeAgents])).sort((a, b) => {
    const numA = Number(String(a).replace(/[^0-9]/g, ''));
    const numB = Number(String(b).replace(/[^0-9]/g, ''));
    return numA - numB;
  });

  if (!allAgents.length) {
    return (
      <section className="card">
        <h2>Agent Peek</h2>
        <div className="small muted">No agent output available. Peek buffers populate when agents are active.</div>
      </section>
    );
  }

  return (
    <section className="card">
      <div className="panel-title">
        <div>
          <h2>Agent Peek</h2>
          <p className="small">Real-time sliding window of each agent's output. Last {PEEK_WINDOW_LINES} lines shown.</p>
        </div>
        <div className="small muted">{agents.length} agent(s) with output</div>
      </div>
      <div className="peek-grid">
        {allAgents.map((agent) => (
          <PeekWindow key={agent} agent={agent} lines={peek[agent] || []} />
        ))}
      </div>
    </section>
  );
}

function PeekWindow({ agent, lines }: { agent: string; lines: string[] }) {
  const containerRef = useRef<HTMLPreElement>(null);
  const displayLines = lines.slice(-PEEK_WINDOW_LINES);

  useEffect(() => {
    const el = containerRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [displayLines.length]);

  return (
    <div className="peek-window">
      <div className="peek-header">
        <strong>{agent}</strong>
        <span className="small muted">{lines.length} line(s)</span>
      </div>
      <pre ref={containerRef} className="peek-content">
        {displayLines.length ? displayLines.join('\n') : '(no output yet)'}
      </pre>
    </div>
  );
}
