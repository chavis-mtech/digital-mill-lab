/** Pure helpers for the energy page (frontend-ops). Display mapping only (ADR-002). */
import type { Schema } from "@dml/contracts";

type Marker = Pick<Schema<"EnergyMarker">, "t" | "abnormal" | "z_score" | "severity">;
type Severity = Schema<"Severity">;
const SEVERITIES = new Set<string>(["info", "low", "medium", "high", "critical"]);

/**
 * Chart markers for the days the API flagged `abnormal` (production-adjusted z-score). The marker sits on the
 * series value at that timestamp when it exists; the label carries the API z-score.
 */
export function toEnergyMarkers(markers: readonly Marker[] | undefined, points: readonly { t: string; v: number | null }[] | undefined) {
  const byT = new Map((points ?? []).map((p) => [p.t, p.v]));
  return (markers ?? [])
    .filter((m) => m.abnormal)
    .map((m) => ({
      t: m.t,
      v: byT.get(m.t) ?? undefined,
      label: m.z_score != null ? `z=${m.z_score.toFixed(2)}` : "abnormal",
      severity: m.severity && SEVERITIES.has(m.severity) ? (m.severity as Severity) : undefined,
    }));
}
