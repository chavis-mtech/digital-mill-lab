import { describe, expect, it } from "vitest";
import { toEnergyMarkers } from "./helpers";

describe("toEnergyMarkers", () => {
  const points = [
    { t: "2026-09-09T17:00:00Z", v: 18.8 },
    { t: "2026-09-10T17:00:00Z", v: 17.1 },
  ];
  it("keeps only abnormal days and anchors them on the series value", () => {
    const m = toEnergyMarkers(
      [
        { t: "2026-09-09T17:00:00Z", abnormal: true, z_score: 2.25, severity: "medium" },
        { t: "2026-09-10T17:00:00Z", abnormal: false, z_score: 0.1, severity: null },
      ],
      points,
    );
    expect(m).toEqual([{ t: "2026-09-09T17:00:00Z", v: 18.8, label: "z=2.25", severity: "medium" }]);
  });
  it("tolerates missing inputs and unknown severities", () => {
    expect(toEnergyMarkers(undefined, undefined)).toEqual([]);
    const [m] = toEnergyMarkers([{ t: "x", abnormal: true, z_score: null, severity: "weird" }], []);
    expect(m).toEqual({ t: "x", v: undefined, label: "abnormal", severity: undefined });
  });
});
