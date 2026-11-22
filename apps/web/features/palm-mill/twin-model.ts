/**
 * Pure layout + state helpers for the Digital Twin Lite (frontend-exec). Geometry and ordering only: node
 * state, KPIs and alert counts always come from GET /process/stages (never hardcoded).
 */

export type HealthState = "normal" | "warning" | "critical" | "maintenance_required";

export type StageLike = { code: string; sequence: number; kind: string; status: HealthState; active_alerts: number };
export type EdgeLike = { source: string; target: string };

export const NODE_W = 170;
export const NODE_H = 118;
const COL_W = 190;
const MAIN_Y = 24;
const SUPPORT_Y = 240;
export const VIEW_W = 20 + 7 * COL_W;
export const VIEW_H = SUPPORT_Y + NODE_H + 24;

/** Preferred support-row column (under the main stage it serves). Unknown support stages take free columns. */
const SUPPORT_COL: Record<string, number> = {
  WATER_TREATMENT: 0,
  BOILER_STEAM: 1,
  POWER: 2,
  KERNEL_RECOVERY: 4,
  POME_TREATMENT: 5,
};

export type NodeBox = { code: string; x: number; y: number; row: "main" | "support" };

export function layoutTwin(stages: readonly StageLike[]): NodeBox[] {
  const main = stages.filter((s) => s.kind === "main").sort((a, b) => a.sequence - b.sequence);
  const support = stages.filter((s) => s.kind !== "main").sort((a, b) => a.sequence - b.sequence);
  const boxes: NodeBox[] = main.map((s, i) => ({ code: s.code, x: 20 + i * COL_W, y: MAIN_Y, row: "main" }));
  const used = new Set<number>();
  const pending: StageLike[] = [];
  for (const s of support) {
    const col = SUPPORT_COL[s.code];
    if (col !== undefined && !used.has(col)) {
      used.add(col);
      boxes.push({ code: s.code, x: 20 + col * COL_W, y: SUPPORT_Y, row: "support" });
    } else pending.push(s);
  }
  for (const s of pending) {
    let col = 0;
    while (used.has(col)) col++;
    used.add(col);
    boxes.push({ code: s.code, x: 20 + col * COL_W, y: SUPPORT_Y, row: "support" });
  }
  return boxes;
}

/** SVG path for a material-flow edge between two laid-out nodes (orthogonal routing). */
export function edgePath(a: NodeBox, b: NodeBox): string {
  if (a.y === b.y) {
    const forward = b.x > a.x;
    const x1 = forward ? a.x + NODE_W : a.x;
    const x2 = forward ? b.x : b.x + NODE_W;
    const y = a.y + NODE_H / 2;
    return `M${x1},${y} H${x2}`;
  }
  const down = b.y > a.y;
  const x1 = a.x + NODE_W / 2 + (down ? 12 : -12);
  const x2 = b.x + NODE_W / 2 + (down ? 12 : -12);
  const y1 = down ? a.y + NODE_H : a.y;
  const y2 = down ? b.y : b.y + NODE_H;
  const mid = (y1 + y2) / 2;
  return x1 === x2 ? `M${x1},${y1} V${y2}` : `M${x1},${y1} V${mid} H${x2} V${y2}`;
}

/** Severity order used to pick what to show first (SPEC/backend-b: normal < warning < maintenance_required < critical). */
export const HEALTH_RANK: Record<HealthState, number> = { normal: 0, warning: 1, maintenance_required: 2, critical: 3 };

/**
 * Stage selected on first load: an explicit valid `?stage=` wins, else the worst main-line stage (ties → more
 * alerts, then flow order), else the first main stage.
 */
export function pickDefaultStage(stages: readonly StageLike[], requested?: string | null): string | null {
  if (requested && stages.some((s) => s.code === requested)) return requested;
  const main = stages.filter((s) => s.kind === "main");
  const pool = main.length ? main : [...stages];
  if (!pool.length) return null;
  const sorted = [...pool].sort(
    (a, b) => HEALTH_RANK[b.status] - HEALTH_RANK[a.status] || b.active_alerts - a.active_alerts || a.sequence - b.sequence,
  );
  return sorted[0]!.code;
}

/** CSS tokens for a health state (status colours are reserved for status — dataviz rule). */
export function healthTone(state: HealthState): { fill: string; stroke: string; text: string } {
  switch (state) {
    case "critical":
      return { fill: "var(--critical-soft)", stroke: "var(--critical)", text: "var(--critical-fg)" };
    case "warning":
      return { fill: "var(--warning-soft)", stroke: "var(--warning)", text: "var(--warning-fg)" };
    case "maintenance_required":
      return { fill: "var(--maintenance-soft)", stroke: "var(--maintenance)", text: "var(--maintenance-fg)" };
    default:
      return { fill: "var(--surface)", stroke: "var(--border-strong)", text: "var(--success-fg)" };
  }
}

/** Edges whose two ends are both laid out (unknown stage codes are skipped rather than drawn to nowhere). */
export function drawableEdges<E extends EdgeLike>(edges: readonly E[], boxes: readonly NodeBox[]): Array<{ edge: E; a: NodeBox; b: NodeBox }> {
  const byCode = new Map(boxes.map((b) => [b.code, b]));
  const out: Array<{ edge: E; a: NodeBox; b: NodeBox }> = [];
  for (const e of edges) {
    const a = byCode.get(e.source);
    const b = byCode.get(e.target);
    if (a && b) out.push({ edge: e, a, b });
  }
  return out;
}
