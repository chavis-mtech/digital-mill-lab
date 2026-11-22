import Link from "next/link";
import { FileX2 } from "lucide-react";
import { DocsLayout } from "@/components/layouts/layouts";
import { StatusChip } from "@/components/demo/status-chip";
import { getLocale, getT } from "@/lib/i18n/server";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { listModelCards, loadDoc, makeLinkMapper } from "./load";
import { DOC_PAGES, pickEntry, type DocSlug } from "./registry";
import { MarkdownView } from "./markdown-view";
import messages from "./docs.i18n";

/**
 * Server component behind every /docs/* page: renders a real repository document selected from the allow-list
 * (`?doc=<key>`, never a path). A missing file shows an honest "not written yet" state, never stand-in text.
 */
export async function DocPage({ slug, docKey }: { slug: DocSlug; docKey?: string }) {
  const t = await getT(messages);
  const locale = await getLocale();
  const cards = slug === "ai-methodology" ? await listModelCards() : [];
  const entry = pickEntry(slug, docKey, cards);
  const doc = await loadDoc(entry);
  const mapper = makeLinkMapper();
  const pills = (items: readonly { key: string; title: { th: string; en: string } }[]) =>
    items.map((e) => (
      <li key={e.key}>
        <Link
          href={`/docs/${slug}?doc=${encodeURIComponent(e.key)}`}
          aria-current={e.key === entry.key ? "page" : undefined}
          className={cn("inline-flex rounded-full border px-3 py-1 text-xs font-medium transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none", e.key === entry.key ? "border-accent bg-accent-soft text-accent-text" : "border-border text-muted-foreground hover:text-foreground")}
        >
          {e.title[locale]}
        </Link>
      </li>
    ));

  return (
    <DocsLayout route={`/docs/${slug}`} toc={doc.ok ? doc.toc.filter((x) => x.level === 2).map((x) => ({ id: x.id, label: x.label })) : undefined}>
      <div className="not-prose mb-6 flex flex-col gap-3">
        {DOC_PAGES[slug].length + cards.length > 1 ? (
          <nav aria-label={t.docNav}>
            <ul className="flex flex-wrap gap-2">{pills(DOC_PAGES[slug])}</ul>
            {cards.length > 0 ? (
              <>
                <p className="mt-3 mb-1 text-2xs font-semibold text-muted-foreground uppercase">{t.modelCards}</p>
                <ul className="flex flex-wrap gap-2">{pills(cards)}</ul>
              </>
            ) : null}
          </nav>
        ) : null}
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span>{t.live}</span>
          <span lang="en" className="font-mono text-2xs">
            {t.source}: {doc.relPath}
            {doc.ok ? ` · ${t.modified}: ${formatDate(doc.modified, locale, "datetime")} · ${t.bytes(doc.bytes)}` : ""}
          </span>
          <span>{t.english}</span>
        </p>
      </div>
      {doc.ok ? (
        <MarkdownView blocks={doc.blocks} mapRelative={mapper} labels={{ table: t.tableLabel, mermaidNote: t.mermaidNote, anchor: t.anchor }} />
      ) : (
        <div role="status" className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-border-strong bg-surface-2/60 px-6 py-12 text-center">
          <FileX2 className="size-6 text-muted-foreground" aria-hidden />
          <StatusChip status="planned" size="md" />
          <p className="text-sm font-semibold text-foreground">{doc.reason === "not_written" ? t.notWrittenTitle : t.unavailableTitle}</p>
          <p className="max-w-md text-xs text-muted-foreground">{doc.reason === "not_written" ? t.notWrittenBody(entry.plannedOwner ?? "—") : t.unavailableBody}</p>
          <p className="font-mono text-2xs text-subtle-foreground">{doc.relPath}</p>
        </div>
      )}
    </DocsLayout>
  );
}
