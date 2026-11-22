/**
 * Key-parity "lint" for every bilingual bundle (ADR-008). Finds all `*.i18n.ts` files in the web app and
 * asserts TH and EN have identical key trees, the same value kinds (string / function / array) and no
 * empty strings. Run: `pnpm --filter web test`.
 */
import { describe, expect, it } from "vitest";

type Tree = Record<string, unknown>;

const modules = import.meta.glob<{ default: { th: Tree; en: Tree } }>(
  ["../../**/*.i18n.ts", "!../../node_modules/**", "!../../.next/**"],
  { eager: true },
);

function walk(th: unknown, en: unknown, path: string, problems: string[]) {
  const kind = (v: unknown) => (Array.isArray(v) ? "array" : typeof v);
  if (kind(th) !== kind(en)) {
    problems.push(`${path}: TH is ${kind(th)}, EN is ${kind(en)}`);
    return;
  }
  if (typeof th === "string") {
    if (!th.trim()) problems.push(`${path}: empty TH string`);
    if (!(en as string).trim()) problems.push(`${path}: empty EN string`);
    return;
  }
  if (typeof th === "function") {
    if (th.length !== (en as (...a: unknown[]) => unknown).length) problems.push(`${path}: function arity differs`);
    return;
  }
  if (Array.isArray(th)) {
    if (th.length !== (en as unknown[]).length) problems.push(`${path}: array length ${th.length} vs ${(en as unknown[]).length}`);
    th.forEach((v, i) => walk(v, (en as unknown[])[i], `${path}[${i}]`, problems));
    return;
  }
  if (th && typeof th === "object") {
    const a = Object.keys(th as Tree).sort();
    const b = Object.keys(en as Tree).sort();
    for (const k of a) if (!b.includes(k)) problems.push(`${path}.${k}: missing in EN`);
    for (const k of b) if (!a.includes(k)) problems.push(`${path}.${k}: missing in TH`);
    for (const k of a) if (b.includes(k)) walk((th as Tree)[k], (en as Tree)[k], `${path}.${k}`, problems);
  }
}

describe("i18n dictionaries", () => {
  const entries = Object.entries(modules);

  it("finds the bundles", () => {
    expect(entries.length).toBeGreaterThanOrEqual(3);
  });

  for (const [file, mod] of entries) {
    it(`${file}: TH and EN keys are identical`, () => {
      expect(mod.default?.th, `${file} must default-export defineMessages({th, en})`).toBeTypeOf("object");
      const problems: string[] = [];
      walk(mod.default.th, mod.default.en, "", problems);
      expect(problems).toEqual([]);
    });
  }
});
