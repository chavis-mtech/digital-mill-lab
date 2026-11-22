import { describe, expect, it } from "vitest";
import {
  chartSensorCodes,
  limitsToThresholds,
  parseIdParam,
  pickRecommendations,
  priorityForWorkOrder,
  recommendationOrigin,
  shortHash,
  sortByAttention,
  toChartMarkers,
  transitionActions,
  transitionProblem,
} from "./helpers";

describe("work-order transition mapping", () => {
  it("keeps the API order and decorates only", () => {
    const a = transitionActions(["in_progress", "on_hold", "cancelled"], true);
    expect(a.map((x) => x.to)).toEqual(["in_progress", "on_hold", "cancelled"]);
    expect(a.find((x) => x.to === "cancelled")?.tone).toBe("destructive");
  });
  it("offers nothing without the transition permission or without allowed transitions", () => {
    expect(transitionActions(["assigned"], false)).toEqual([]);
    expect(transitionActions(undefined, true)).toEqual([]);
    expect(transitionActions([], true)).toEqual([]);
  });
  it("resolving requires resolution notes", () => {
    const [resolve] = transitionActions(["resolved"], true);
    expect(resolve?.needsResolutionNotes).toBe(true);
    expect(transitionProblem(resolve!, "   ")).toBe("resolution_notes_required");
    expect(transitionProblem(resolve!, "Replaced bearing")).toBeNull();
    const [close] = transitionActions(["closed"], true);
    expect(transitionProblem(close!, "")).toBeNull();
  });
});

describe("equipment ordering", () => {
  it("sorts critical first, then by risk index, then code", () => {
    const sorted = sortByAttention([
      { code: "B", health_state: "normal" as const, risk_score: 50 },
      { code: "A", health_state: "maintenance_required" as const, risk_score: 1 },
      { code: "C", health_state: "critical" as const, risk_score: 10 },
      { code: "D", health_state: "critical" as const, risk_score: 91 },
    ]);
    expect(sorted.map((x) => x.code)).toEqual(["D", "C", "A", "B"]);
  });
});

describe("recommendations", () => {
  const items = [
    { id: 10, priority: "high" as const, equipment: { id: 3 }, status: "proposed", risk_score: null },
    { id: 9001802, priority: "critical" as const, equipment: { id: 18 }, status: "proposed", risk_score: 87 },
    { id: 147, priority: "critical" as const, equipment: { id: 18 }, status: "proposed", risk_score: null },
    { id: 11, priority: "critical" as const, equipment: null, status: "proposed", risk_score: null },
    { id: 12, priority: "critical" as const, equipment: { id: 18 }, status: "approved", risk_score: null },
  ];
  it("keeps only proposed equipment-bound items, highest priority and rule-based first", () => {
    expect(pickRecommendations(items).map((x) => x.id)).toEqual([9001802, 147, 10]);
  });
  it("filters by equipment", () => {
    expect(pickRecommendations(items, { equipmentId: 3 }).map((x) => x.id)).toEqual([10]);
  });
  it("distinguishes rule and ML origin by id range", () => {
    expect(recommendationOrigin(9000306)).toBe("rule");
    expect(recommendationOrigin(147)).toBe("ml");
  });
  it("maps severity onto the work-order priority scale", () => {
    expect(priorityForWorkOrder("critical")).toBe("urgent");
    expect(priorityForWorkOrder("high")).toBe("high");
    expect(priorityForWorkOrder("info")).toBe("low");
  });
});

describe("chart helpers", () => {
  it("builds threshold lines only from limits the API provided", () => {
    const labels = { warn: "Warn", crit: "Crit" };
    expect(limitsToThresholds(undefined, labels)).toEqual([]);
    expect(limitsToThresholds({ warn_limit: 2.8, crit_limit: 4.5 }, labels)).toEqual([
      { value: 2.8, label: "Warn", tone: "warning" },
      { value: 4.5, label: "Crit", tone: "critical" },
    ]);
    expect(limitsToThresholds({ warn_limit: null, crit_limit: 100 }, labels)).toEqual([{ value: 100, label: "Crit", tone: "critical" }]);
  });
  it("uses the peak time of a marker and filters sensor-specific markers", () => {
    const m = toChartMarkers(
      [
        { code: "A", start_ts: "2026-11-12T20:00:00Z", peak_ts: "2026-11-12T22:00:00Z", severity: "medium" },
        { code: "B", start_ts: "2026-11-13T09:00:00Z", severity: "weird", sensor_code: "X" },
      ],
      "Y",
    );
    expect(m).toEqual([{ t: "2026-11-12T22:00:00Z", label: "A", severity: "medium" }]);
  });
  it("orders sensors vibration, temperature, current, pressure and drops state/counters", () => {
    expect(
      chartSensorCodes([
        { code: "RH", sensor_type: "running_hours" },
        { code: "CUR", sensor_type: "current" },
        { code: "VIB", sensor_type: "vibration" },
        { code: "TMP", sensor_type: "temperature" },
      ]),
    ).toEqual(["VIB", "TMP", "CUR"]);
  });
});

describe("small formatters", () => {
  it("shortens hashes", () => {
    expect(shortHash("abcdef0123456789", 6)).toBe("abcdef…");
    expect(shortHash(null)).toBe("—");
  });
  it("parses id params defensively", () => {
    expect(parseIdParam("18")).toBe(18);
    expect(parseIdParam("0")).toBeNull();
    expect(parseIdParam("1e3")).toBeNull();
    expect(parseIdParam("-4")).toBeNull();
    expect(parseIdParam(null)).toBeNull();
  });
});
