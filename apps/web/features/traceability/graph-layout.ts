/**
 * Pure layout helpers for the trace graph (frontend-ops). Positions are drawn from the API's nodes and edges;
 * no mass or share is computed here (ADR-002) — `edgeWidth` only maps the API share onto a stroke width.
 */
export type TraceNodeLike = { id: string; type: string; label: string };
export type TraceEdgeLike = { source: string; target: string; share?: number | null; mass?: number | null };

/** Left-to-right order of layers: supplier → … → CPO lot. Unknown types are appended after `cpo_lot`'s predecessors. */
export const LAYER_ORDER = ["supplier", "plantation", "delivery", "ffb_batch", "production_batch", "cpo_lot"] as const;

export type Placed<N> = N & { x: number; y: number; layer: number };

export type GraphLayout<N extends TraceNodeLike> = {
  nodes: Placed<N>[];
  layers: string[];
  width: number;
  height: number;
  byId: Map<string, Placed<N>>;
};

export const NODE_W = 168;
export const NODE_H = 24;
export const COL_GAP = 72;
export const ROW_GAP = 8;
export const PAD = 12;

export function layoutGraph<N extends TraceNodeLike>(nodes: readonly N[]): GraphLayout<N> {
  const present = new Set(nodes.map((n) => n.type));
  const rank = (t: string) => {
    const i = (LAYER_ORDER as readonly string[]).indexOf(t);
    return i === -1 ? LAYER_ORDER.length - 1.5 : i;
  };
  const layers = [...present].sort((a, b) => rank(a) - rank(b));
  const rows = new Map<string, number>();
  const placed: Placed<N>[] = nodes.map((n) => {
    const layer = layers.indexOf(n.type);
    const row = rows.get(n.type) ?? 0;
    rows.set(n.type, row + 1);
    return { ...n, layer, x: PAD + layer * (NODE_W + COL_GAP), y: PAD + 22 + row * (NODE_H + ROW_GAP) };
  });
  const maxRows = Math.max(1, ...rows.values());
  return {
    nodes: placed,
    layers,
    width: PAD * 2 + layers.length * NODE_W + Math.max(0, layers.length - 1) * COL_GAP,
    height: PAD * 2 + 22 + maxRows * (NODE_H + ROW_GAP),
    byId: new Map(placed.map((p) => [p.id, p])),
  };
}

/** Cubic path between the right edge of the source node and the left edge of the target node. */
export function edgePath(a: { x: number; y: number }, b: { x: number; y: number }): string {
  const x1 = a.x + NODE_W;
  const y1 = a.y + NODE_H / 2;
  const x2 = b.x;
  const y2 = b.y + NODE_H / 2;
  const dx = Math.max(24, (x2 - x1) / 2);
  return `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`;
}

/** Stroke width from the API share (a 0..1 fraction): 1px when unknown, up to 6px. */
export function edgeWidth(share: number | null | undefined): number {
  if (share == null || !Number.isFinite(share) || share <= 0) return 1;
  return 1 + Math.min(1, share) * 5;
}

/** Ids of edges touching a node (for highlighting). */
export function connectedEdges<E extends TraceEdgeLike>(edges: readonly E[], nodeId: string | null): E[] {
  if (!nodeId) return [];
  return edges.filter((e) => e.source === nodeId || e.target === nodeId);
}

/** Parse the numeric id out of a node id such as `cpo_lot:120` (null when the type does not match). */
export function parseNodeId(id: string, type: string): number | null {
  const [t, n] = id.split(":");
  if (t !== type || !n || !/^\d{1,9}$/.test(n)) return null;
  return Number(n);
}

export function truncateLabel(label: string, max = 26): string {
  return label.length <= max ? label : `${label.slice(0, max - 1)}…`;
}
