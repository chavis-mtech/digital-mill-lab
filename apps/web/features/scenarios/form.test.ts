import { describe, expect, it } from "vitest";
import { parseNumber, readForm, toFormValues, tornadoGeometry } from "./form";

describe("simulator form helpers", () => {
  it("parses numbers with separators and rejects junk", () => {
    expect(parseNumber("1,000")).toBe(1000);
    expect(parseNumber(" 18.9 ")).toBe(18.9);
    expect(parseNumber("")).toBeNull();
    expect(parseNumber("abc")).toBeNull();
    expect(parseNumber("-")).toBeNull();
  });

  it("seeds and reads the form, flagging invalid entries", () => {
    const keys = ["a", "b", "c"] as const;
    const v = toFormValues({ a: 911.4, b: "x", c: 1 / 3 }, keys);
    expect(v).toEqual({ a: "911.4", c: "0.3333" });
    const { body, invalid } = readForm({ a: "1,000", b: "oops", c: "" }, keys);
    expect(body).toEqual({ a: 1000 });
    expect(invalid).toEqual(["b"]);
  });

  it("places tornado bars around the base and sorts by swing", () => {
    const g = tornadoGeometry(
      [
        { variable: "small", net_benefit_low_thb: 90, net_benefit_high_thb: 110 },
        { variable: "big", net_benefit_low_thb: -100, net_benefit_high_thb: 300 },
      ],
      100,
      400,
    );
    expect(g.rows.map((r) => r.bar.variable)).toEqual(["big", "small"]);
    expect(g.baseX).toBe(200);
    expect(g.zeroX).toBe(100);
    const big = g.rows[0]!;
    expect(big.low.x + big.low.w).toBeCloseTo(g.baseX);
    expect(big.high.x).toBeCloseTo(g.baseX);
    expect(big.high.w).toBeCloseTo(200);
  });
});
