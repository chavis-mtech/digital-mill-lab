/**
 * UI-KIT FIXTURES — visual QA only, rendered exclusively on the hidden /ui-kit route.
 * These are NOT demo data and must never be imported by demo/public pages (that would violate SPEC §0
 * rule 8: no hardcoded metrics standing in for computation). Values are arbitrary shapes for layout tests.
 */
import type { Schema } from "@dml/contracts";

const AS_OF = "2026-11-20T11:00:00Z";
const prov = (kind: Schema<"ProvenanceKind">, source = "ui-kit fixture"): Schema<"Provenance"> => ({ kind, source, as_of: AS_OF, model_version: kind === "forecast" ? "fixture@0" : null });

function days(n: number, f: (i: number) => number, start = Date.parse("2026-10-22T11:00:00Z")) {
  return Array.from({ length: n }, (_, i) => ({ t: new Date(start + i * 86_400_000).toISOString(), v: +f(i).toFixed(2) }));
}

export const FX_SERIES_A: Schema<"Series"> = { key: "a", label: "Series A (fixture)", unit: "%", points: days(30, (i) => 20 + Math.sin(i / 3) * 0.6 - (i > 22 ? 1.2 : 0)), provenance: prov("synthetic_actual") };
export const FX_SERIES_B: Schema<"Series"> = { key: "b", label: "Series B (fixture)", unit: "%", points: days(30, (i) => 20.4 + Math.cos(i / 4) * 0.3), provenance: prov("forecast") };
export const FX_SERIES_C: Schema<"Series"> = { key: "c", label: "Series C (fixture)", unit: "%", points: days(30, (i) => 19.6 + Math.sin(i / 5) * 0.4), provenance: prov("what_if") };

export const FX_BAND: Schema<"BandSeries"> = {
  key: "fc",
  label: "Forecast (fixture)",
  unit: "%",
  interval: "P10–P90 (fixture)",
  points: days(14, (i) => 20 + Math.sin(i / 3) * 0.3, Date.parse("2026-11-08T11:00:00Z")).map((p, i) => ({ ...p, lower: +(p.v! - 0.4 - i * 0.03).toFixed(2), upper: +(p.v! + 0.4 + i * 0.03).toFixed(2) })),
  provenance: prov("forecast"),
};
export const FX_ACTUAL: Schema<"Series"> = { key: "act", label: "Actual (fixture)", unit: "%", points: days(10, (i) => 20 + Math.sin(i / 2) * 0.35, Date.parse("2026-11-08T11:00:00Z")), provenance: prov("synthetic_actual") };
export const FX_BASELINE: Schema<"Series"> = { key: "naive", label: "Naive baseline (fixture)", unit: "%", points: days(14, () => 20.1, Date.parse("2026-11-08T11:00:00Z")), provenance: prov("forecast") };

export const FX_KPIS: Schema<"KpiValue">[] = [
  { key: "k1", label: "KPI with delta up (good)", value: 1234.5, unit: "t", previous: 1180, delta: 54.5, delta_pct: 4.6, good_direction: "up", status: null, target: 1300, provenance: prov("synthetic_actual") },
  { key: "k2", label: "KPI with delta down (bad)", value: 19.2, unit: "%", previous: 20.1, delta: -0.9, delta_pct: -4.5, good_direction: "up", status: "high", target: null, provenance: prov("synthetic_actual") },
  { key: "k3", label: "Lower-is-better KPI", value: 31.4, unit: "kWh/t", previous: 33.0, delta: -1.6, delta_pct: -4.8, good_direction: "down", status: null, target: null, provenance: prov("forecast") },
  { key: "k4", label: "What-if KPI", value: 5, unit: "t", previous: null, delta: null, delta_pct: null, good_direction: "up", status: null, target: null, provenance: prov("what_if") },
];

export const FX_EVIDENCE: Schema<"Evidence">[] = [
  { metric: "m1", label: "Signal outside normal range (fixture)", observed: 7.4, expected: 3.1, unit: "mm/s", normal_range: { low: 0, high: 4.5, unit: "mm/s", basis: "fixture basis" }, note: "Fixture note", window_start: "2026-11-19T02:00:00Z", window_end: "2026-11-20T02:00:00Z" },
  { metric: "m2", label: "Signal within range (fixture)", observed: 61, expected: 60, unit: "°C", normal_range: { low: 40, high: 80, unit: "°C", basis: "fixture basis" } },
];
export const FX_ASSUMPTIONS: Schema<"Assumption">[] = [
  { key: "a1", label: "Fixture assumption", value: 300, unit: "days/yr", tag: "engineering_assumption", source: "fixture", editable: true },
  { key: "a2", label: "Fixture price", value: 40, unit: "THB/kg", tag: "historical_public_information", source: "fixture", editable: true },
];
export const FX_FORMULAS: Schema<"Formula">[] = [
  { key: "f1", label: "Calculation example (SPEC §4.B)", expression: "delta_cpo_t = ffb_t × delta_oer_pp / 100", inputs: { ffb_t: 1000, delta_oer_pp: 0.5 }, result: 5, unit: "t" },
];

export type FxRow = { id: string; name: string; area: string; value: number; state: Schema<"HealthState">; severity: Schema<"Severity"> };
export const FX_ROWS: FxRow[] = Array.from({ length: 42 }, (_, i) => ({
  id: `R-${String(i + 1).padStart(3, "0")}`,
  name: ["Pump", "Press", "Conveyor", "Digester", "Boiler feed", "Centrifuge"][i % 6]! + ` ${Math.floor(i / 6) + 1}`,
  area: ["Pressing", "Clarification", "Reception", "Digestion", "Boiler", "Clarification"][i % 6]!,
  value: Math.round(((i * 37) % 100) + 0.5),
  state: (["normal", "warning", "critical", "maintenance_required"] as const)[i % 4]!,
  severity: (["info", "low", "medium", "high", "critical"] as const)[i % 5]!,
}));

export const FX_HEAT = {
  x: Array.from({ length: 12 }, (_, i) => `${String(i * 2).padStart(2, "0")}:00`),
  y: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
  values: Array.from({ length: 7 * 12 }, (_, k) => [k % 12, Math.floor(k / 12), Math.round(((k * 13) % 17) + (k % 12 > 4 && k % 12 < 9 ? 6 : 0))] as [number, number, number]),
};
