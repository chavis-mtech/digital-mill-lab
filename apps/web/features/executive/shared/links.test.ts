import { describe, expect, it } from "vitest";
import { alertHref, alertSourceKind, KPI_DRILLDOWN, KPI_ORDER, kpiHref, orderKpis, stageHref, teamKey } from "./links";

describe("executive drill-down helpers", () => {
  it("every one of the 12 KPIs drills down somewhere", () => {
    expect(KPI_ORDER).toHaveLength(12);
    for (const k of KPI_ORDER) expect(kpiHref(k)).toMatch(/^\/demo\//);
    expect(Object.keys(KPI_DRILLDOWN).sort()).toEqual([...KPI_ORDER].sort());
  });

  it("orders KPIs in SPEC order and keeps unknown keys last", () => {
    const out = orderKpis([{ key: "zzz" }, { key: "oer_pct" }, { key: "ffb_received_t" }]);
    expect(out.map((k) => k.key)).toEqual(["ffb_received_t", "oer_pct", "zzz"]);
  });

  it("routes alerts by equipment first, then module", () => {
    expect(alertHref({ module: "maintenance", equipment: { id: 18, code: "PRS-03" } })).toBe("/demo/maintenance/equipment?equipment_id=18");
    expect(alertHref({ module: "logistics" })).toBe("/demo/logistics");
    expect(alertHref({ module: "production", process_stage_code: "PRESSING" })).toBe(stageHref("PRESSING"));
    expect(alertHref({ module: "production" })).toBe("/demo/palm-mill");
  });

  it("maps free-text teams onto translatable keys", () => {
    expect(teamKey("maintenance")).toBe("maintenance");
    expect(teamKey("production (utilities / energy)")).toBe("energy");
    expect(teamKey("logistics")).toBe("logistics");
    expect(teamKey(null)).toBe("unknown");
    expect(teamKey("someone else")).toBe("unknown");
  });

  it("classifies alert sources", () => {
    expect(alertSourceKind("rule")).toBe("rule");
    expect(alertSourceKind("equipment_anomaly")).toBe("ml");
  });
});
