import { describe, expect, it } from "vitest";
import { citationKind, isNoData, kbSlug, questionProblem, readVerification, reasonKey } from "./helpers";

describe("refusal reasons", () => {
  it("maps API reasons to translatable keys", () => {
    expect(reasonKey("tool_denied")).toBe("tool_denied");
    expect(reasonKey("control")).toBe("control");
    expect(reasonKey("prompt_injection")).toBe("injection");
    expect(reasonKey("write_request")).toBe("write");
    expect(reasonKey("sql_request")).toBe("sql");
    expect(reasonKey("something new")).toBe("other");
    expect(reasonKey(null)).toBe("other");
  });
  it("detects the no-data state without treating refusals as no-data", () => {
    expect(isNoData({ refused: false, intent: "unknown", uncertainty: "unmatched_question" })).toBe(true);
    expect(isNoData({ refused: true, intent: "unknown" })).toBe(false);
    expect(isNoData({ refused: false, intent: "oer_why", uncertainty: "x" })).toBe(false);
  });
});

describe("citations", () => {
  it("separates tool data from sample documents", () => {
    expect(citationKind("tool:get_oer_trend")).toBe("data");
    expect(citationKind("kb:equipment-inspection-procedure#3")).toBe("document");
    expect(kbSlug("kb:equipment-inspection-procedure#3")).toBe("equipment-inspection-procedure");
    expect(kbSlug("kb:maintenance-checklist")).toBe("maintenance-checklist");
    expect(kbSlug("tool:x")).toBeNull();
    expect(kbSlug("kb:../../etc/passwd")).toBeNull();
  });
});

describe("question validation and verification", () => {
  it("validates length", () => {
    expect(questionProblem("   ")).toBe("empty");
    expect(questionProblem("a".repeat(1001))).toBe("too_long");
    expect(questionProblem("Why did OER drop?")).toBeNull();
  });
  it("reads verification defensively", () => {
    expect(readVerification({ numbers_checked: 19, numbers_supported: 19, unsupported_numbers: [], causal_flags: ["x"] })).toEqual({ checked: 19, supported: 19, unsupported: [], causal: ["x"] });
    expect(readVerification(null)).toEqual({ checked: null, supported: null, unsupported: [], causal: [] });
  });
});
