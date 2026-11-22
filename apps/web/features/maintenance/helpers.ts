/**
 * Pure helpers for the maintenance screens (frontend-ops). No business numbers are computed here
 * (ADR-002): only ordering, label lookup, and mapping of API-provided states onto UI actions.
 */
import type { Schema } from "@dml/contracts";

export type WorkOrderStatus = Schema<"WorkOrderStatus">;
export type HealthState = Schema<"HealthState">;
export type Severity = Schema<"Severity">;

/** Lifecycle order used to draw the status stepper (AI alert → review → WO → assigned → … → resolved). */
export const WO_FLOW: readonly WorkOrderStatus[] = ["open", "assigned", "in_progress", "resolved", "closed"];

export const WO_STATUSES: readonly WorkOrderStatus[] = ["open", "assigned", "in_progress", "on_hold", "resolved", "closed", "cancelled"];

export function isTerminalStatus(s: WorkOrderStatus): boolean {
  return s === "closed" || s === "cancelled";
}

export type TransitionAction = {
  to: WorkOrderStatus;
  /** `resolved` requires `resolution_notes` (backend rule, 422 otherwise). */
  needsResolutionNotes: boolean;
  /** Visual weight of the button. */
  tone: "primary" | "neutral" | "destructive";
};

/**
 * Turn the API's `allowed_transitions` (role- and clock-aware) into UI actions. The UI never decides which
 * transitions are legal; it only decorates the list the server returned and keeps the server order.
 * `canTransition` is the role's `workorder:transition` permission: without it nothing is offered.
 */
export function transitionActions(allowed: readonly WorkOrderStatus[] | undefined, canTransition: boolean): TransitionAction[] {
  if (!allowed || !canTransition) return [];
  return allowed.map((to) => ({
    to,
    needsResolutionNotes: to === "resolved",
    tone: to === "cancelled" ? "destructive" : to === "in_progress" || to === "resolved" || to === "closed" ? "primary" : "neutral",
  }));
}

/** Validation for a transition request before it is sent (the server validates again). */
export function transitionProblem(action: TransitionAction, resolutionNotes: string): "resolution_notes_required" | null {
  if (action.needsResolutionNotes && resolutionNotes.trim().length === 0) return "resolution_notes_required";
  return null;
}

/** Position of a status in the lifecycle stepper (-1 for off-path states such as on_hold / cancelled). */
export function flowIndex(s: WorkOrderStatus): number {
  return WO_FLOW.indexOf(s);
}

const HEALTH_RANK: Record<HealthState, number> = { critical: 0, maintenance_required: 1, warning: 2, normal: 3 };
const SEVERITY_RANK: Record<Severity, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };

export function healthRank(s: HealthState): number {
  return HEALTH_RANK[s];
}

/** Attention order for the equipment registry: critical first, then by the API risk index (desc). */
export function sortByAttention<T extends { health_state: HealthState; risk_score?: number | null; code: string }>(items: readonly T[]): T[] {
  return [...items].sort((a, b) => HEALTH_RANK[a.health_state] - HEALTH_RANK[b.health_state] || (b.risk_score ?? -1) - (a.risk_score ?? -1) || a.code.localeCompare(b.code));
}

/** Rule-based recommendations carry stable ids from 9,000,000 (backend-b); ML ones come from `ai_recommendations`. */
export const RULE_RECOMMENDATION_ID_MIN = 9_000_000;

export function recommendationOrigin(id: number): "rule" | "ml" {
  return id >= RULE_RECOMMENDATION_ID_MIN ? "rule" : "ml";
}

type RecLike = { id: number; priority: Severity; equipment?: { id: number | string } | null; status: string; risk_score?: number | null };

/**
 * Order recommendations for the engineer: only proposed ones tied to equipment, highest priority first,
 * rule-based (explicit evidence) before ML, then by the API risk score.
 */
export function pickRecommendations<T extends RecLike>(items: readonly T[], opts: { equipmentId?: number | null } = {}): T[] {
  return items
    .filter((r) => r.status === "proposed" && r.equipment && (opts.equipmentId == null || Number(r.equipment.id) === opts.equipmentId))
    .sort(
      (a, b) =>
        SEVERITY_RANK[a.priority] - SEVERITY_RANK[b.priority] ||
        (recommendationOrigin(a.id) === "rule" ? 0 : 1) - (recommendationOrigin(b.id) === "rule" ? 0 : 1) ||
        (b.risk_score ?? -1) - (a.risk_score ?? -1) ||
        b.id - a.id,
    );
}

/** Map the recommendation priority onto the work-order priority scale (low|medium|high|urgent). */
export function priorityForWorkOrder(p: Severity): "low" | "medium" | "high" | "urgent" {
  if (p === "critical") return "urgent";
  if (p === "high") return "high";
  if (p === "medium") return "medium";
  return "low";
}

export type SensorLimit = { warn_limit?: number | null; crit_limit?: number | null; low_is_bad?: boolean };

/** Chart threshold lines from the API sensor limits (values are the API's, labels are provided by the caller). */
export function limitsToThresholds(limit: SensorLimit | undefined, labels: { warn: string; crit: string }) {
  if (!limit) return [];
  const out: { value: number; label: string; tone: "warning" | "critical" }[] = [];
  if (limit.warn_limit != null) out.push({ value: limit.warn_limit, label: labels.warn, tone: "warning" });
  if (limit.crit_limit != null) out.push({ value: limit.crit_limit, label: labels.crit, tone: "critical" });
  return out;
}

type MarkerLike = { peak_ts?: string | null; start_ts: string; code: string; label?: string | null; severity?: string | null; sensor_code?: string | null };

const SEVERITIES = new Set<string>(["info", "low", "medium", "high", "critical"]);

/** API anomaly markers → chart markers (sensor-specific markers only appear on their own sensor's chart). */
export function toChartMarkers(markers: readonly MarkerLike[] | undefined, sensorCode?: string) {
  return (markers ?? [])
    .filter((m) => !m.sensor_code || !sensorCode || m.sensor_code === sensorCode)
    .map((m) => ({
      t: m.peak_ts ?? m.start_ts,
      label: m.code,
      severity: m.severity && SEVERITIES.has(m.severity) ? (m.severity as Severity) : undefined,
    }));
}

/** Sensor types worth a chart on the equipment page, in display order. */
export const CHART_SENSOR_TYPES = ["vibration", "temperature", "current", "pressure"] as const;

export function chartSensorCodes(sensors: readonly { code: string; sensor_type: string }[]): string[] {
  const order = (t: string) => {
    const i = (CHART_SENSOR_TYPES as readonly string[]).indexOf(t);
    return i === -1 ? 99 : i;
  };
  return sensors
    .filter((s) => order(s.sensor_type) < 99)
    .sort((a, b) => order(a.sensor_type) - order(b.sensor_type))
    .map((s) => s.code);
}

/** Short form of a hash for display (the full hash stays in the title attribute). */
export function shortHash(h: string | null | undefined, n = 10): string {
  if (!h) return "—";
  return h.length <= n ? h : `${h.slice(0, n)}…`;
}

/** Parse a positive integer from a URL param; anything else yields null (no NaN leaks into API calls). */
export function parseIdParam(v: string | null | undefined): number | null {
  if (!v || !/^\d{1,9}$/.test(v)) return null;
  const n = Number(v);
  return n > 0 ? n : null;
}
