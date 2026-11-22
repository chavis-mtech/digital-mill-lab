import { describe, expect, it } from "vitest";
import { drawableEdges, edgePath, healthTone, layoutTwin, pickDefaultStage, type StageLike } from "./twin-model";

const S = (code: string, sequence: number, kind = "main", status: StageLike["status"] = "normal", active_alerts = 0): StageLike => ({
  code,
  sequence,
  kind,
  status,
  active_alerts,
});

const stages: StageLike[] = [
  S("STERILIZATION", 2),
  S("FFB_RECEPTION", 1),
  S("PRESSING", 5, "main", "critical", 4),
  S("DIGESTION", 4, "main", "maintenance_required"),
  S("BOILER_STEAM", 102, "support"),
  S("NEW_SUPPORT", 200, "support"),
];

describe("digital twin layout", () => {
  it("orders the main line by sequence and puts support stages on the second row", () => {
    const boxes = layoutTwin(stages);
    const main = boxes.filter((b) => b.row === "main").map((b) => b.code);
    expect(main).toEqual(["FFB_RECEPTION", "STERILIZATION", "DIGESTION", "PRESSING"]);
    const boiler = boxes.find((b) => b.code === "BOILER_STEAM")!;
    const steril = boxes.find((b) => b.code === "STERILIZATION")!;
    expect(boiler.row).toBe("support");
    expect(boiler.x).toBe(steril.x); // boiler sits under the sterilizer it feeds
    const extra = boxes.find((b) => b.code === "NEW_SUPPORT")!;
    expect(extra.row).toBe("support");
    expect(extra.x).not.toBe(boiler.x);
  });

  it("routes horizontal and vertical edges", () => {
    const boxes = layoutTwin(stages);
    const get = (c: string) => boxes.find((b) => b.code === c)!;
    expect(edgePath(get("FFB_RECEPTION"), get("STERILIZATION"))).toMatch(/^M\d+,\d+ H\d+$/);
    expect(edgePath(get("BOILER_STEAM"), get("STERILIZATION"))).toMatch(/^M\d+,\d+ V\d+$/);
  });

  it("skips edges to unknown stages", () => {
    const boxes = layoutTwin(stages);
    const e = drawableEdges([{ source: "FFB_RECEPTION", target: "STERILIZATION" }, { source: "X", target: "PRESSING" }], boxes);
    expect(e).toHaveLength(1);
  });
});

describe("scenario-state mapping", () => {
  it("selects the worst main stage by default and honours a valid ?stage=", () => {
    expect(pickDefaultStage(stages)).toBe("PRESSING");
    expect(pickDefaultStage(stages, "DIGESTION")).toBe("DIGESTION");
    expect(pickDefaultStage(stages, "NOT_A_STAGE")).toBe("PRESSING");
    expect(pickDefaultStage(stages.map((s) => ({ ...s, status: "normal" as const, active_alerts: 0 })))).toBe("FFB_RECEPTION");
    expect(pickDefaultStage([])).toBeNull();
  });

  it("maps every health state to status tokens", () => {
    expect(healthTone("critical").stroke).toBe("var(--critical)");
    expect(healthTone("warning").stroke).toBe("var(--warning)");
    expect(healthTone("maintenance_required").stroke).toBe("var(--maintenance)");
    expect(healthTone("normal").text).toBe("var(--success-fg)");
  });
});
