/**
 * Pure drill-down / labelling helpers shared by the executive and palm-mill features (frontend-exec).
 * No business numbers are computed here — only routing and label lookup (ADR-002).
 */

/** Where each control-tower KPI drills down to (SPEC §4-A "drill-down from every KPI"). */
export const KPI_DRILLDOWN: Record<string, string> = {
  ffb_received_t: "/demo/logistics",
  ffb_processed_t: "/demo/palm-mill",
  cpo_produced_t: "/demo/palm-mill",
  oer_pct: "/demo/palm-mill/analytics",
  ker_pct: "/demo/palm-mill/analytics",
  throughput_tph: "/demo/palm-mill/process",
  equipment_availability_pct: "/demo/maintenance",
  plant_downtime_h: "/demo/maintenance",
  energy_kwh_per_t: "/demo/energy",
  est_production_cost_thb_per_t: "/demo/business-impact",
  active_maintenance_alerts: "/demo/maintenance",
  logistics_queue_time_min: "/demo/logistics",
};

export function kpiHref(key: string): string | undefined {
  return KPI_DRILLDOWN[key];
}

/** The 12 control-tower KPIs in SPEC §4-A order (used to order cards and to detect missing ones). */
export const KPI_ORDER = [
  "ffb_received_t",
  "ffb_processed_t",
  "cpo_produced_t",
  "oer_pct",
  "ker_pct",
  "throughput_tph",
  "equipment_availability_pct",
  "plant_downtime_h",
  "energy_kwh_per_t",
  "est_production_cost_thb_per_t",
  "active_maintenance_alerts",
  "logistics_queue_time_min",
] as const;

export function orderKpis<T extends { key: string }>(kpis: readonly T[]): T[] {
  const rank = (k: string) => {
    const i = (KPI_ORDER as readonly string[]).indexOf(k);
    return i === -1 ? KPI_ORDER.length : i;
  };
  return [...kpis].sort((a, b) => rank(a.key) - rank(b.key));
}

type AlertLike = {
  module: string;
  equipment?: { id: number | string; code?: string | null } | null;
  process_stage_code?: string | null;
};

/** Module page for an alert. Equipment alerts open the equipment view filtered to that asset. */
export function alertHref(a: AlertLike): string {
  if (a.equipment) return `/demo/maintenance/equipment?equipment_id=${encodeURIComponent(String(a.equipment.id))}`;
  switch (a.module) {
    case "maintenance":
      return "/demo/maintenance";
    case "logistics":
      return "/demo/logistics";
    case "energy":
      return "/demo/energy";
    case "production":
    case "quality":
      return a.process_stage_code ? stageHref(a.process_stage_code) : "/demo/palm-mill";
    default:
      return "/demo/executive";
  }
}

/** Process-flow page with a stage pre-selected. */
export function stageHref(code: string): string {
  return `/demo/palm-mill/process?stage=${encodeURIComponent(code)}`;
}

export type TeamKey = "maintenance" | "production" | "logistics" | "energy" | "quality" | "unknown";

/** Map the API's free-text `suggested_team` onto a translatable key (unknown text falls back to "unknown"). */
export function teamKey(team: string | null | undefined): TeamKey {
  const t = (team ?? "").toLowerCase();
  if (!t) return "unknown";
  if (t.includes("energy") || t.includes("utilit")) return "energy";
  if (t.startsWith("maintenance")) return "maintenance";
  if (t.startsWith("production")) return "production";
  if (t.startsWith("logistic")) return "logistics";
  if (t.startsWith("quality")) return "quality";
  return "unknown";
}

/** Alert source → "rule" or "ml" (ML detectors write `*_anomaly` sources). */
export function alertSourceKind(source: string): "rule" | "ml" {
  return source === "rule" ? "rule" : "ml";
}
