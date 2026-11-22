import path from "node:path";
import { describe, expect, it } from "vitest";
import { DOC_PAGES, MODEL_CARD_NAME, isDocSlug, pickEntry, resolveDocPath } from "./registry";

const ROOT = "/repo/docs";

describe("doc path allow-listing", () => {
  it("resolves registry paths inside docs/", () => {
    expect(resolveDocPath(ROOT, "architecture/SYSTEM_ARCHITECTURE.md")).toBe(path.join(ROOT, "architecture/SYSTEM_ARCHITECTURE.md"));
    expect(resolveDocPath(ROOT, "AI_MODELS.md")).toBe(path.join(ROOT, "AI_MODELS.md"));
  });
  it("rejects traversal, absolute paths, backslashes and NUL bytes", () => {
    for (const bad of ["../README.md", "../../etc/passwd", "architecture/../../secret.md", "/etc/passwd", "a\\..\\b.md", "x\0.md", "", "architecture/../.."]) {
      expect(resolveDocPath(ROOT, bad), bad).toBeNull();
    }
  });
  it("never serves docs/internal, docs/status or non-markdown files", () => {
    expect(resolveDocPath(ROOT, "internal/notes.md")).toBeNull();
    expect(resolveDocPath(ROOT, "Internal/notes.md")).toBeNull();
    expect(resolveDocPath(ROOT, "status/frontend-ops.md")).toBeNull();
    expect(resolveDocPath(ROOT, "architecture/DATABASE_SCHEMA.sql")).toBeNull();
    expect(resolveDocPath(ROOT, "architecture")).toBeNull();
  });
  it("every registered document resolves inside docs/", () => {
    for (const entries of Object.values(DOC_PAGES)) for (const e of entries) expect(resolveDocPath(ROOT, e.file), e.file).not.toBeNull();
  });
  it("registers all seven pages and knows slugs", () => {
    expect(Object.keys(DOC_PAGES).sort()).toEqual(["ai-methodology", "architecture", "data-model", "integration", "overview", "roadmap", "security"]);
    expect(isDocSlug("overview")).toBe(true);
    expect(isDocSlug("../etc")).toBe(false);
    expect(isDocSlug("constructor")).toBe(false);
  });
  it("falls back to the first entry for an unknown key and validates model-card names", () => {
    expect(pickEntry("architecture", "nope").key).toBe("system");
    expect(pickEntry("architecture", "api").file).toBe("architecture/API_CONTRACT.md");
    expect(MODEL_CARD_NAME.test("oer_forecast.md")).toBe(true);
    expect(MODEL_CARD_NAME.test("../x.md")).toBe(false);
    expect(MODEL_CARD_NAME.test("a/b.md")).toBe(false);
  });
});
