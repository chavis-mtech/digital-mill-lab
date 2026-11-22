/**
 * Allow-list of repository documents the /docs pages may render (frontend-ops).
 *
 * SECURITY: a request never supplies a path. `?doc=<key>` selects an entry of this registry; the relative path of
 * an entry is a constant in this file. `resolveDocPath` additionally re-checks that the final absolute path stays
 * inside `<repo>/docs`, is a `.md` file and never touches `docs/internal` (private owner notes) or `docs/status`.
 */
import path from "node:path";

export type DocSlug = "overview" | "architecture" | "data-model" | "ai-methodology" | "integration" | "security" | "roadmap";

export type DocEntry = {
  key: string;
  /** Path relative to the repo `docs/` folder (forward slashes). */
  file: string;
  title: { th: string; en: string };
  /** The owner has not written this document yet: show the honest "not written yet" state when the file is absent. */
  plannedOwner?: string;
};

export const DOC_PAGES: Record<DocSlug, readonly DocEntry[]> = {
  overview: [
    { key: "vision", file: "PROJECT_VISION.md", title: { th: "วิสัยทัศน์โครงการ", en: "Project vision" } },
    { key: "requirements", file: "PRODUCT_REQUIREMENTS.md", title: { th: "ข้อกำหนดผลิตภัณฑ์", en: "Product requirements" } },
    { key: "case-study", file: "TECHNICAL_CASE_STUDY.md", title: { th: "กรณีศึกษาทางเทคนิค", en: "Technical case study" } },
  ],
  architecture: [
    { key: "system", file: "architecture/SYSTEM_ARCHITECTURE.md", title: { th: "สถาปัตยกรรมระบบ", en: "System architecture" } },
    { key: "decisions", file: "DECISIONS.md", title: { th: "บันทึกการตัดสินใจ (ADR)", en: "Decision records (ADR)" } },
    { key: "api", file: "architecture/API_CONTRACT.md", title: { th: "สัญญา API", en: "API contract" } },
    { key: "frontend", file: "architecture/FRONTEND_GUIDE.md", title: { th: "คู่มือส่วนหน้า", en: "Frontend guide" } },
  ],
  "data-model": [
    { key: "domain", file: "architecture/DOMAIN_MODEL.md", title: { th: "โมเดลโดเมน", en: "Domain model" } },
    { key: "schema", file: "architecture/DATABASE_SCHEMA.md", title: { th: "สคีมาฐานข้อมูล", en: "Database schema" } },
    { key: "generation", file: "DATA_GENERATION.md", title: { th: "การสร้างข้อมูลสังเคราะห์", en: "Synthetic data generation" } },
  ],
  "ai-methodology": [
    { key: "models", file: "AI_MODELS.md", title: { th: "โมเดล AI", en: "AI models" } },
    { key: "evaluation", file: "MODEL_EVALUATION.md", title: { th: "การประเมินโมเดล", en: "Model evaluation" } },
    { key: "copilot", file: "ai/copilot.md", title: { th: "ผู้ช่วย AI (Copilot)", en: "Copilot design" } },
    { key: "copilot-eval", file: "ai/COPILOT_EVALUATION.md", title: { th: "การประเมินผู้ช่วย AI", en: "Copilot evaluation" } },
  ],
  integration: [{ key: "contracts", file: "architecture/INTEGRATION_CONTRACTS.md", title: { th: "สัญญาการเชื่อมต่อในอนาคต", en: "Future integration contracts" } }],
  security: [{ key: "security", file: "SECURITY.md", title: { th: "ความปลอดภัย", en: "Security" }, plannedOwner: "qa-security" }],
  roadmap: [{ key: "roadmap", file: "IMPLEMENTATION_ROADMAP.md", title: { th: "แผนงาน 30/60/90 วัน และ 1–3 ปี", en: "30/60/90-day and 1–3 year roadmap" } }],
};

/** Model cards are discovered from `docs/ai/model-cards/` (file names are validated, never taken from the URL). */
export const MODEL_CARD_DIR = "ai/model-cards";
export const MODEL_CARD_NAME = /^[a-z0-9][a-z0-9_-]{0,60}\.md$/i;

export function isDocSlug(s: string): s is DocSlug {
  return Object.prototype.hasOwnProperty.call(DOC_PAGES, s);
}

const BLOCKED_SEGMENTS = new Set(["internal", "status", "node_modules", ".git"]);

/**
 * Resolve a registry-relative file to an absolute path under `docsRoot`, or null when it escapes the root,
 * is not a `.md` file or sits in a blocked folder. Pure (no I/O) so it can be unit-tested.
 */
export function resolveDocPath(docsRoot: string, relative: string): string | null {
  if (!relative || relative.includes("\0") || path.isAbsolute(relative) || relative.includes("\\")) return null;
  const root = path.resolve(docsRoot);
  const full = path.resolve(root, relative);
  if (full !== root && !full.startsWith(root + path.sep)) return null;
  const rel = path.relative(root, full);
  if (!rel || rel.startsWith("..") || path.isAbsolute(rel)) return null;
  if (!rel.toLowerCase().endsWith(".md")) return null;
  if (rel.split(path.sep).some((seg) => BLOCKED_SEGMENTS.has(seg.toLowerCase()))) return null;
  return full;
}

/** Look up an entry for a page by key (unknown keys fall back to the first entry). */
export function pickEntry(slug: DocSlug, key: string | null | undefined, extra: readonly DocEntry[] = []): DocEntry {
  const all = [...DOC_PAGES[slug], ...extra];
  return all.find((e) => e.key === key) ?? all[0]!;
}
