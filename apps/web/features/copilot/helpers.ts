/** Pure helpers for the Copilot workspace (frontend-ops). Display mapping only. */

export const MAX_QUESTION_CHARS = 1000;

export type ReasonKey = "tool_denied" | "control" | "write" | "injection" | "sql" | "other";

/** Map the API `refusal_reason` onto a translatable key (unknown values fall back to `other`). */
export function reasonKey(reason: string | null | undefined): ReasonKey {
  const r = (reason ?? "").toLowerCase();
  if (r === "tool_denied" || r.includes("denied") || r.includes("not_allowed") || r.includes("forbidden")) return "tool_denied";
  if (r === "control" || r.includes("control")) return "control";
  if (r.includes("write") || r.includes("record")) return "write";
  if (r.includes("inject") || r.includes("prompt")) return "injection";
  if (r.includes("sql")) return "sql";
  return "other";
}

type Answerish = { refused?: boolean | null; intent?: string | null; uncertainty?: string | null };

/** "no data" = the router could not match the question to any tool or document (the copilot does not guess). */
export function isNoData(a: Answerish): boolean {
  return !a.refused && (a.intent === "unknown" || a.uncertainty === "unmatched_question");
}

/** Citation ref `tool:<name>` points to tool data; `kb:<slug>#<chunk>` to a sample document chunk. */
export function citationKind(ref: string): "data" | "document" {
  return ref.startsWith("kb:") ? "document" : "data";
}

/** Slug of a KB reference (`kb:equipment-inspection-procedure#3` -> `equipment-inspection-procedure`). */
export function kbSlug(ref: string): string | null {
  const m = /^kb:([a-z0-9-]+)(?:#\d+)?$/i.exec(ref);
  return m ? m[1]! : null;
}

/** Messages longer than the cap are rejected client-side (the server enforces it too). */
export function questionProblem(text: string): "empty" | "too_long" | null {
  const s = text.trim();
  if (s.length === 0) return "empty";
  if (s.length > MAX_QUESTION_CHARS) return "too_long";
  return null;
}

export type VerificationLike = { numbers_checked?: unknown; numbers_supported?: unknown; unsupported_numbers?: unknown; causal_flags?: unknown } | null | undefined;

/** Read the free-form verification object defensively. */
export function readVerification(v: VerificationLike) {
  const n = (x: unknown) => (typeof x === "number" && Number.isFinite(x) ? x : null);
  const list = (x: unknown) => (Array.isArray(x) ? x.map(String) : []);
  return {
    checked: n(v?.numbers_checked),
    supported: n(v?.numbers_supported),
    unsupported: list(v?.unsupported_numbers),
    causal: list(v?.causal_flags),
  };
}
