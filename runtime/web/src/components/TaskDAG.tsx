import { useMemo } from 'react';
import type { DashboardState, BacklogItem } from '../types';

type DagNode = {
  id: string;
  title: string;
  owner: string;
  gate: string;
  status: string;
  deps: string[];
  layer: number;
  col: number;
  x: number;
  y: number;
};

const NODE_W = 150;
const NODE_H = 62;
const LAYER_GAP_X = 200;
const COL_GAP_Y = 90;
const PAD_X = 40;
const PAD_Y = 30;

const STATUS_COLORS: Record<string, { fill: string; stroke: string; text: string }> = {
  completed: { fill: '#0f2e24', stroke: '#22c55e', text: '#86efac' },
  done: { fill: '#0f2e24', stroke: '#22c55e', text: '#86efac' },
  merged: { fill: '#0f2e24', stroke: '#22c55e', text: '#86efac' },
  active: { fill: '#0f1e3a', stroke: '#3b82f6', text: '#93c5fd' },
  healthy: { fill: '#0f1e3a', stroke: '#3b82f6', text: '#93c5fd' },
  pending: { fill: '#1a1a0f', stroke: '#f59e0b', text: '#fcd34d' },
  blocked: { fill: '#14181f', stroke: '#6b7280', text: '#9ca3af' },
  launch_failed: { fill: '#2a0f18', stroke: '#ef4444', text: '#fca5a5' },
};

function statusStyle(status: string) {
  return STATUS_COLORS[status] || STATUS_COLORS.pending;
}

function buildDag(items: BacklogItem[], runtimeAgents: Set<string>): { nodes: DagNode[]; width: number; height: number } {
  if (!items.length) return { nodes: [], width: 0, height: 0 };

  const byId = new Map<string, BacklogItem>();
  for (const item of items) byId.set(item.id, item);

  // Compute layers via topological order
  const layerMap = new Map<string, number>();
  function getLayer(id: string): number {
    if (layerMap.has(id)) return layerMap.get(id)!;
    const item = byId.get(id);
    if (!item || !item.dependencies?.length) {
      layerMap.set(id, 0);
      return 0;
    }
    let maxDep = 0;
    for (const dep of item.dependencies) {
      maxDep = Math.max(maxDep, getLayer(dep) + 1);
    }
    layerMap.set(id, maxDep);
    return maxDep;
  }
  for (const item of items) getLayer(item.id);

  // Group by layer
  const layers = new Map<number, BacklogItem[]>();
  for (const item of items) {
    const l = layerMap.get(item.id) || 0;
    if (!layers.has(l)) layers.set(l, []);
    layers.get(l)!.push(item);
  }

  const maxLayer = Math.max(...Array.from(layers.keys()));
  const maxColCount = Math.max(...Array.from(layers.values()).map((g) => g.length));

  const nodes: DagNode[] = [];
  for (let l = 0; l <= maxLayer; l++) {
    const group = layers.get(l) || [];
    // Sort within layer by id for stable ordering
    group.sort((a, b) => a.id.localeCompare(b.id));
    const totalHeight = group.length * NODE_H + (group.length - 1) * COL_GAP_Y;
    const maxTotalHeight = maxColCount * NODE_H + (maxColCount - 1) * COL_GAP_Y;
    const offsetY = (maxTotalHeight - totalHeight) / 2;
    for (let c = 0; c < group.length; c++) {
      const item = group[c];
      // Resolve effective status: if runtime shows agent as active/healthy, override
      let effectiveStatus = item.status;
      if (runtimeAgents.has(item.owner) && (effectiveStatus === 'pending' || effectiveStatus === 'blocked')) {
        effectiveStatus = 'active';
      }
      nodes.push({
        id: item.id,
        title: item.title || item.id,
        owner: item.owner,
        gate: item.gate,
        status: effectiveStatus,
        deps: item.dependencies || [],
        layer: l,
        col: c,
        x: PAD_X + l * LAYER_GAP_X,
        y: PAD_Y + offsetY + c * (NODE_H + COL_GAP_Y),
      });
    }
  }

  const width = PAD_X * 2 + maxLayer * LAYER_GAP_X + NODE_W;
  const height = PAD_Y * 2 + maxColCount * NODE_H + (maxColCount - 1) * COL_GAP_Y;
  return { nodes, width, height };
}

export function TaskDAG({ data }: { data: DashboardState }) {
  const items = data.backlog?.items || [];
  const runtimeAgents = useMemo(() => {
    const set = new Set<string>();
    for (const w of data.runtime?.workers || []) {
      if (w.status === 'active' || w.status === 'healthy') set.add(w.agent);
    }
    return set;
  }, [data.runtime]);

  const { nodes, width, height } = useMemo(() => buildDag(items, runtimeAgents), [items, runtimeAgents]);

  if (!nodes.length) {
    return (
      <section className="card">
        <h2>Task DAG</h2>
        <div className="small muted">No backlog items to visualize.</div>
      </section>
    );
  }

  const nodeById = new Map(nodes.map((n) => [n.id, n]));

  // Build edges
  const edges: Array<{ from: DagNode; to: DagNode }> = [];
  for (const node of nodes) {
    for (const dep of node.deps) {
      const src = nodeById.get(dep);
      if (src) edges.push({ from: src, to: node });
    }
  }

  return (
    <section className="card">
      <div className="panel-title">
        <div>
          <h2>Task DAG</h2>
          <p className="small">Dependency graph showing task flow, status, and gate assignments.</p>
        </div>
      </div>
      <div className="dag-container">
        <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} style={{ maxWidth: '100%', height: 'auto' }}>
          <defs>
            <marker id="dag-arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
              <path d="M0 0 L10 5 L0 10 z" fill="#64748b" />
            </marker>
          </defs>

          {/* Edges */}
          {edges.map(({ from, to }) => {
            const x1 = from.x + NODE_W;
            const y1 = from.y + NODE_H / 2;
            const x2 = to.x;
            const y2 = to.y + NODE_H / 2;
            const cx1 = x1 + (x2 - x1) * 0.4;
            const cx2 = x2 - (x2 - x1) * 0.4;
            return (
              <path
                key={`${from.id}-${to.id}`}
                d={`M${x1},${y1} C${cx1},${y1} ${cx2},${y2} ${x2},${y2}`}
                fill="none"
                stroke="#475569"
                strokeWidth={2}
                markerEnd="url(#dag-arrow)"
                opacity={0.6}
              />
            );
          })}

          {/* Nodes */}
          {nodes.map((node) => {
            const style = statusStyle(node.status);
            return (
              <g key={node.id}>
                <rect
                  x={node.x}
                  y={node.y}
                  width={NODE_W}
                  height={NODE_H}
                  rx={10}
                  ry={10}
                  fill={style.fill}
                  stroke={style.stroke}
                  strokeWidth={2}
                />
                <text x={node.x + NODE_W / 2} y={node.y + 20} textAnchor="middle" fill={style.text} fontSize={13} fontWeight={700}>
                  {node.id}
                </text>
                <text x={node.x + NODE_W / 2} y={node.y + 36} textAnchor="middle" fill="#94a3b8" fontSize={10}>
                  {node.owner} · {node.gate}
                </text>
                <text x={node.x + NODE_W / 2} y={node.y + 52} textAnchor="middle" fill={style.text} fontSize={10} opacity={0.8}>
                  {node.status}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </section>
  );
}
