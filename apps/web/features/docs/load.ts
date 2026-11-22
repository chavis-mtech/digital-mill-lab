import "server-only";
import fs from "node:fs/promises";
import path from "node:path";
import { DOC_PAGES, MODEL_CARD_DIR, MODEL_CARD_NAME, resolveDocPath, type DocEntry, type DocSlug } from "./registry";
import { parseMarkdown, tocOf, type Block } from "./markdown";

/** Repo `docs/` folder: `apps/web` is the working directory for dev / build / start (`DOCS_ROOT` overrides). */
export function docsRoot(): string {
  // The docs folder is read at request time on purpose (never bundled / traced): opt out of file tracing.
  return path.resolve(/* turbopackIgnore: true */ process.env.DOCS_ROOT ?? path.join(/* turbopackIgnore: true */ process.cwd(), "../../docs"));
}

export type LoadedDoc =
  | { ok: true; blocks: Block[]; toc: { id: string; label: string; level: number }[]; modified: Date; bytes: number; relPath: string }
  | { ok: false; reason: "not_written" | "unavailable"; relPath: string };

export async function loadDoc(entry: DocEntry): Promise<LoadedDoc> {
  const root = docsRoot();
  const full = resolveDocPath(root, entry.file);
  const relPath = `docs/${entry.file}`;
  if (!full) return { ok: false, reason: "unavailable", relPath };
  try {
    const [text, stat] = await Promise.all([fs.readFile(/* turbopackIgnore: true */ full, "utf8"), fs.stat(/* turbopackIgnore: true */ full)]);
    const blocks = parseMarkdown(text);
    return { ok: true, blocks, toc: tocOf(blocks), modified: stat.mtime, bytes: stat.size, relPath };
  } catch {
    return { ok: false, reason: entry.plannedOwner ? "not_written" : "unavailable", relPath };
  }
}

/** Model cards actually present in `docs/ai/model-cards/` (names validated against a strict pattern). */
export async function listModelCards(): Promise<DocEntry[]> {
  try {
    const dir = path.join(/* turbopackIgnore: true */ docsRoot(), MODEL_CARD_DIR);
    const names = (await fs.readdir(/* turbopackIgnore: true */ dir)).filter((n) => MODEL_CARD_NAME.test(n)).sort();
    return names.map((n) => {
      const stem = n.replace(/\.md$/i, "");
      return { key: `card:${stem}`, file: `${MODEL_CARD_DIR}/${n}`, title: { th: `การ์ดโมเดล: ${stem}`, en: `Model card: ${stem}` } };
    });
  } catch {
    return [];
  }
}

/** basename -> route for relative `.md` links inside documents. */
export function relativeLinkMap(): Map<string, string> {
  const map = new Map<string, string>();
  for (const [slug, entries] of Object.entries(DOC_PAGES) as [DocSlug, readonly DocEntry[]][]) {
    for (const e of entries) map.set(path.basename(e.file).toLowerCase(), `/docs/${slug}?doc=${e.key}`);
  }
  return map;
}

export function makeLinkMapper(): (rel: string) => string | null {
  const map = relativeLinkMap();
  return (rel) => {
    const [file, hash] = rel.split("#");
    if (!file || !file.toLowerCase().endsWith(".md")) return null;
    const hit = map.get(path.basename(file).toLowerCase());
    return hit ? `${hit}${hash ? `#${hash.replace(/[^\w\-.%]/g, "")}` : ""}` : null;
  };
}
