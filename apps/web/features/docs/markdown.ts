/**
 * Minimal, dependency-free Markdown parser for the /docs pages (frontend-ops). It produces a typed AST that is
 * rendered with React elements only — there is no `dangerouslySetInnerHTML`, raw HTML in a document is shown as
 * text, and link targets are sanitised by `safeHref`. Supported: ATX headings with GitHub-style anchors, fenced code,
 * GFM tables (with alignment), nested ordered/unordered/task lists, block quotes, horizontal rules, paragraphs,
 * and inline code / bold / italic / strikethrough / links / images (alt text only) / autolinks / backslash escapes.
 */
export type Inline =
  | { t: "text"; v: string }
  | { t: "code"; v: string }
  | { t: "strong"; c: Inline[] }
  | { t: "em"; c: Inline[] }
  | { t: "del"; c: Inline[] }
  | { t: "link"; href: string; c: Inline[] }
  | { t: "br" };

export type Align = "left" | "right" | "center" | null;

export type Block =
  | { t: "heading"; level: number; id: string; c: Inline[]; text: string }
  | { t: "p"; c: Inline[] }
  | { t: "code"; lang: string; v: string }
  | { t: "list"; ordered: boolean; start: number; items: { task: boolean | null; c: Block[] }[] }
  | { t: "quote"; c: Block[] }
  | { t: "table"; head: Inline[][]; align: Align[]; rows: Inline[][][] }
  | { t: "hr" };

// ── inline ───────────────────────────────────────────────────────────────────────────────────────────────────

const INLINE =
  /(`+)([\s\S]*?[^`])\1(?!`)|!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)|\[([^\]]+)\]\(([^)\s]+)(?:\s+"[^"]*")?\)|\*\*([\s\S]+?)\*\*|__([\s\S]+?)__|~~([\s\S]+?)~~|\*([^\s*][\s\S]*?)\*|(?<![A-Za-z0-9])_([^\s_][\s\S]*?)_(?![A-Za-z0-9])|<(https?:\/\/[^>\s]+)>|\\([\\`*_{}[\]()#+\-.!|~<>])/;

export function parseInline(src: string): Inline[] {
  const out: Inline[] = [];
  let rest = src;
  const pushText = (v: string) => {
    if (!v) return;
    const last = out[out.length - 1];
    if (last && last.t === "text") last.v += v;
    else out.push({ t: "text", v });
  };
  while (rest.length > 0) {
    const m = INLINE.exec(rest);
    if (!m) {
      pushText(rest);
      break;
    }
    pushText(rest.slice(0, m.index));
    if (m[2] !== undefined) out.push({ t: "code", v: m[2].replace(/^ (.*) $/s, "$1") });
    else if (m[4] !== undefined) pushText(m[3] ?? ""); // image: alt text only, never fetched
    else if (m[6] !== undefined) out.push({ t: "link", href: m[6], c: parseInline(m[5] ?? "") });
    else if (m[7] !== undefined) out.push({ t: "strong", c: parseInline(m[7]) });
    else if (m[8] !== undefined) out.push({ t: "strong", c: parseInline(m[8]) });
    else if (m[9] !== undefined) out.push({ t: "del", c: parseInline(m[9]) });
    else if (m[10] !== undefined) out.push({ t: "em", c: parseInline(m[10]) });
    else if (m[11] !== undefined) out.push({ t: "em", c: parseInline(m[11]) });
    else if (m[12] !== undefined) out.push({ t: "link", href: m[12], c: [{ t: "text", v: m[12] }] });
    else if (m[13] !== undefined) pushText(m[13]);
    rest = rest.slice(m.index + m[0].length);
  }
  return out;
}

export function inlineText(c: readonly Inline[]): string {
  return c
    .map((i) => {
      switch (i.t) {
        case "text":
        case "code":
          return i.v;
        case "br":
          return " ";
        default:
          return inlineText(i.c);
      }
    })
    .join("");
}

// ── helpers ──────────────────────────────────────────────────────────────────────────────────────────────────

/** GitHub-style anchor id with de-duplication (`seen` is shared across one document). */
export function slugify(text: string, seen: Map<string, number>): string {
  let base = text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s-]/gu, "")
    .trim()
    .replace(/\s+/g, "-");
  if (!base) base = "section";
  const n = seen.get(base) ?? 0;
  seen.set(base, n + 1);
  return n === 0 ? base : `${base}-${n}`;
}

export type LinkTarget = { kind: "internal" | "external" | "anchor" | "mailto"; href: string } | null;

/**
 * Sanitise a link target. Only http(s), mailto, same-page anchors and links mapped by `mapRelative` (a document
 * route) are allowed; everything else (javascript:, data:, file:, unmapped relative paths) yields null and the
 * link is shown as plain text.
 */
export function safeHref(href: string, mapRelative?: (rel: string) => string | null): LinkTarget {
  const h = href.trim();
  if (h.startsWith("#")) return /^#[\w\-.%\p{L}\p{N}]*$/u.test(h) ? { kind: "anchor", href: h } : null;
  if (/^https?:\/\//i.test(h)) return { kind: "external", href: h };
  if (/^mailto:[^\s]+$/i.test(h)) return { kind: "mailto", href: h };
  if (/^[a-z][a-z0-9+.-]*:/i.test(h)) return null; // javascript:, data:, file:, vbscript: …
  const mapped = mapRelative?.(h) ?? null;
  return mapped ? { kind: "internal", href: mapped } : null;
}

// ── blocks ───────────────────────────────────────────────────────────────────────────────────────────────────

const RE_HEADING = /^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$/;
const RE_FENCE = /^(\s*)(`{3,}|~{3,})\s*([\w+-]*)[^`]*$/;
const RE_HR = /^ {0,3}([-*_])(?:\s*\1){2,}\s*$/;
const RE_LIST = /^(\s*)([-*+]|\d{1,9}[.)])\s+(.*)$/;
const RE_TABLE_SEP = /^\s*\|?\s*:?-{1,}:?\s*(?:\|\s*:?-{1,}:?\s*)*\|?\s*$/;
const RE_QUOTE = /^ {0,3}>/;

function splitRow(line: string): string[] {
  let s = line.trim();
  if (s.startsWith("|")) s = s.slice(1);
  if (s.endsWith("|") && !s.endsWith("\\|")) s = s.slice(0, -1);
  const cells: string[] = [];
  let cur = "";
  let inCode = false;
  for (let i = 0; i < s.length; i++) {
    const ch = s[i]!;
    if (ch === "`") inCode = !inCode;
    if (ch === "\\" && s[i + 1] === "|") {
      cur += "|";
      i++;
      continue;
    }
    if (ch === "|" && !inCode) {
      cells.push(cur.trim());
      cur = "";
      continue;
    }
    cur += ch;
  }
  cells.push(cur.trim());
  return cells;
}

function alignOf(cell: string): Align {
  const c = cell.trim();
  const l = c.startsWith(":");
  const r = c.endsWith(":");
  return l && r ? "center" : r ? "right" : l ? "left" : null;
}

const indentOf = (s: string) => s.length - s.trimStart().length;
const isBlank = (s: string) => s.trim().length === 0;

function startsBlock(line: string, next: string | undefined): boolean {
  return RE_HEADING.test(line) || RE_FENCE.test(line) || RE_HR.test(line) || RE_QUOTE.test(line) || RE_LIST.test(line) || (line.includes("|") && next !== undefined && RE_TABLE_SEP.test(next) && next.includes("-"));
}

export function parseBlocks(lines: string[], seen: Map<string, number> = new Map()): Block[] {
  const blocks: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i]!;
    if (isBlank(line)) {
      i++;
      continue;
    }
    // HTML comments are dropped (they are authoring notes).
    if (line.trim().startsWith("<!--")) {
      while (i < lines.length && !lines[i]!.includes("-->")) i++;
      i++;
      continue;
    }
    const fence = RE_FENCE.exec(line);
    if (fence) {
      const [, ind = "", marker = "```", lang = ""] = fence;
      const body: string[] = [];
      i++;
      while (i < lines.length && !new RegExp(`^\\s*${marker[0] === "`" ? "`" : "~"}{${marker.length},}\\s*$`).test(lines[i]!)) {
        body.push(lines[i]!.startsWith(ind) ? lines[i]!.slice(ind.length) : lines[i]!);
        i++;
      }
      i++; // closing fence
      blocks.push({ t: "code", lang, v: body.join("\n") });
      continue;
    }
    const h = RE_HEADING.exec(line);
    if (h) {
      const c = parseInline(h[2] ?? "");
      const text = inlineText(c);
      blocks.push({ t: "heading", level: h[1]!.length, id: slugify(text, seen), c, text });
      i++;
      continue;
    }
    if (RE_HR.test(line)) {
      blocks.push({ t: "hr" });
      i++;
      continue;
    }
    if (line.includes("|") && i + 1 < lines.length && RE_TABLE_SEP.test(lines[i + 1]!) && lines[i + 1]!.includes("-")) {
      const head = splitRow(line);
      const align = splitRow(lines[i + 1]!).map(alignOf);
      i += 2;
      const rows: Inline[][][] = [];
      while (i < lines.length && !isBlank(lines[i]!) && lines[i]!.includes("|")) {
        const cells = splitRow(lines[i]!);
        rows.push(head.map((_, k) => parseInline(cells[k] ?? "")));
        i++;
      }
      blocks.push({ t: "table", head: head.map((c) => parseInline(c)), align, rows });
      continue;
    }
    if (RE_QUOTE.test(line)) {
      const inner: string[] = [];
      while (i < lines.length && (RE_QUOTE.test(lines[i]!) || (!isBlank(lines[i]!) && inner.length > 0 && !startsBlock(lines[i]!, lines[i + 1])))) {
        inner.push(lines[i]!.replace(/^ {0,3}> ?/, ""));
        i++;
      }
      blocks.push({ t: "quote", c: parseBlocks(inner, seen) });
      continue;
    }
    const li = RE_LIST.exec(line);
    if (li) {
      const baseIndent = li[1]!.length;
      const ordered = /\d/.test(li[2]!);
      const start = ordered ? parseInt(li[2]!, 10) : 1;
      const items: { task: boolean | null; c: Block[] }[] = [];
      while (i < lines.length) {
        const m = RE_LIST.exec(lines[i]!);
        if (!m || m[1]!.length !== baseIndent || /\d/.test(m[2]!) !== ordered) break;
        const contentIndent = m[1]!.length + m[2]!.length + 1;
        const body: string[] = [m[3] ?? ""];
        i++;
        while (i < lines.length) {
          const cur = lines[i]!;
          if (isBlank(cur)) {
            // a blank line stays inside the item only when the next non-blank line is indented under it
            let j = i + 1;
            while (j < lines.length && isBlank(lines[j]!)) j++;
            if (j < lines.length && indentOf(lines[j]!) >= contentIndent) {
              body.push("");
              i++;
              continue;
            }
            break;
          }
          if (indentOf(cur) >= contentIndent) {
            body.push(cur.slice(Math.min(contentIndent, indentOf(cur))));
            i++;
            continue;
          }
          const sibling = RE_LIST.exec(cur);
          if (sibling && sibling[1]!.length <= baseIndent) break;
          if (startsBlock(cur, lines[i + 1])) break;
          body.push(cur.trim()); // lazy paragraph continuation
          i++;
        }
        let task: boolean | null = null;
        const t0 = /^\[( |x|X)\]\s+/.exec(body[0] ?? "");
        if (t0) {
          task = t0[1] !== " ";
          body[0] = (body[0] ?? "").slice(t0[0].length);
        }
        items.push({ task, c: parseBlocks(body, seen) });
      }
      blocks.push({ t: "list", ordered, start, items });
      continue;
    }
    // paragraph
    const para: string[] = [line];
    i++;
    while (i < lines.length && !isBlank(lines[i]!) && !startsBlock(lines[i]!, lines[i + 1]) && !lines[i]!.trim().startsWith("<!--")) {
      para.push(lines[i]!);
      i++;
    }
    const joined = para.map((l, k) => (k < para.length - 1 && /(\s{2,}|\\)$/.test(l) ? `${l.replace(/(\s{2,}|\\)$/, "")}\u0000` : l.trim())).join(" ").replace(/\u0000 ?/g, "\u0000");
    const c: Inline[] = [];
    joined.split("\u0000").forEach((seg, k) => {
      if (k > 0) c.push({ t: "br" });
      c.push(...parseInline(seg));
    });
    blocks.push({ t: "p", c });
  }
  return blocks;
}

export function parseMarkdown(src: string): Block[] {
  return parseBlocks(src.replace(/\r\n?/g, "\n").split("\n"));
}

/** Headings usable for the "on this page" list (levels 2 and 3). */
export function tocOf(blocks: readonly Block[]): { id: string; label: string; level: number }[] {
  return blocks.flatMap((b) => (b.t === "heading" && (b.level === 2 || b.level === 3) ? [{ id: b.id, label: b.text, level: b.level }] : []));
}
