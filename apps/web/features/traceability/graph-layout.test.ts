import { describe, expect, it } from "vitest";
import { COL_GAP, NODE_W, connectedEdges, edgePath, edgeWidth, layoutGraph, parseNodeId, truncateLabel } from "./graph-layout";

const nodes = [
  { id: "cpo_lot:120", type: "cpo_lot", label: "CPO-1" },
  { id: "supplier:1", type: "supplier", label: "SUP-001" },
  { id: "supplier:2", type: "supplier", label: "SUP-002" },
  { id: "production_batch:9", type: "production_batch", label: "PB-9" },
];

describe("trace graph layout", () => {
  it("orders layers supplier -> processing batch -> CPO lot regardless of input order", () => {
    const l = layoutGraph(nodes);
    expect(l.layers).toEqual(["supplier", "production_batch", "cpo_lot"]);
    expect(l.byId.get("supplier:1")!.x).toBeLessThan(l.byId.get("production_batch:9")!.x);
    expect(l.byId.get("production_batch:9")!.x).toBeLessThan(l.byId.get("cpo_lot:120")!.x);
    expect(l.width).toBeGreaterThanOrEqual(3 * NODE_W + 2 * COL_GAP);
  });
  it("stacks nodes of one layer in rows without overlap", () => {
    const l = layoutGraph(nodes);
    expect(l.byId.get("supplier:2")!.y).toBeGreaterThan(l.byId.get("supplier:1")!.y);
  });
  it("draws edge paths between the node edges", () => {
    const l = layoutGraph(nodes);
    const d = edgePath(l.byId.get("supplier:1")!, l.byId.get("production_batch:9")!);
    expect(d.startsWith("M")).toBe(true);
    expect(d).toContain("C");
  });
});

describe("edge helpers", () => {
  it("maps an API share onto a bounded stroke width", () => {
    expect(edgeWidth(null)).toBe(1);
    expect(edgeWidth(0)).toBe(1);
    expect(edgeWidth(0.5)).toBe(3.5);
    expect(edgeWidth(7)).toBe(6);
  });
  it("finds edges touching a node", () => {
    const edges = [
      { source: "a", target: "b" },
      { source: "b", target: "c" },
      { source: "x", target: "y" },
    ];
    expect(connectedEdges(edges, "b")).toHaveLength(2);
    expect(connectedEdges(edges, null)).toEqual([]);
  });
  it("parses node ids safely and truncates labels", () => {
    expect(parseNodeId("cpo_lot:120", "cpo_lot")).toBe(120);
    expect(parseNodeId("supplier:120", "cpo_lot")).toBeNull();
    expect(parseNodeId("cpo_lot:abc", "cpo_lot")).toBeNull();
    expect(truncateLabel("abcdefghij", 5)).toBe("abcd…");
  });
});
