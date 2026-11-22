import Link from "next/link";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { safeHref, type Block, type Inline } from "./markdown";

export type MarkdownLabels = { table: (n: number) => string; mermaidNote: string; anchor: (h: string) => string };

type Ctx = { mapRelative?: (rel: string) => string | null; labels: MarkdownLabels };

function renderInline(nodes: readonly Inline[], ctx: Ctx): ReactNode[] {
  return nodes.map((n, i) => {
    switch (n.t) {
      case "text":
        return n.v;
      case "br":
        return <br key={i} />;
      case "code":
        return (
          <code key={i} className="rounded bg-surface-2 px-1 py-px font-mono text-[0.8125em] break-words">
            {n.v}
          </code>
        );
      case "strong":
        return <strong key={i}>{renderInline(n.c, ctx)}</strong>;
      case "em":
        return <em key={i}>{renderInline(n.c, ctx)}</em>;
      case "del":
        return <del key={i}>{renderInline(n.c, ctx)}</del>;
      case "link": {
        const target = safeHref(n.href, ctx.mapRelative);
        const kids = renderInline(n.c, ctx);
        if (!target) return <span key={i}>{kids}</span>;
        if (target.kind === "internal") return <Link key={i} href={target.href} className="text-accent-text underline underline-offset-2 hover:no-underline">{kids}</Link>;
        if (target.kind === "external")
          return (
            <a key={i} href={target.href} target="_blank" rel="noopener noreferrer" className="text-accent-text underline underline-offset-2 hover:no-underline">
              {kids}
            </a>
          );
        return (
          <a key={i} href={target.href} className="text-accent-text underline underline-offset-2 hover:no-underline">
            {kids}
          </a>
        );
      }
    }
  });
}

const H: Record<number, string> = {
  1: "mt-2 mb-4 text-2xl font-semibold tracking-tight",
  2: "mt-10 mb-3 border-b border-border pb-1.5 text-xl font-semibold tracking-tight",
  3: "mt-7 mb-2 text-base font-semibold",
  4: "mt-5 mb-1.5 text-sm font-semibold",
  5: "mt-4 mb-1 text-sm font-semibold",
  6: "mt-4 mb-1 text-xs font-semibold uppercase",
};

function renderBlocks(blocks: readonly Block[], ctx: Ctx, counter: { table: number }): ReactNode[] {
  return blocks.map((b, i) => {
    switch (b.t) {
      case "heading": {
        const Tag = `h${Math.min(6, b.level)}` as "h1";
        return (
          <Tag key={i} id={b.id} className={cn("group scroll-mt-28 text-foreground", H[b.level])}>
            {renderInline(b.c, ctx)}
            <a href={`#${b.id}`} className="ml-1.5 text-subtle-foreground opacity-0 group-hover:opacity-100 focus-visible:opacity-100" aria-label={ctx.labels.anchor(b.text)}>
              #
            </a>
          </Tag>
        );
      }
      case "p":
        return (
          <p key={i} className="mb-4 text-[0.9375rem] leading-7 text-foreground [overflow-wrap:anywhere]">
            {renderInline(b.c, ctx)}
          </p>
        );
      case "hr":
        return <hr key={i} className="my-8 border-border" />;
      case "code":
        return (
          <div key={i} className="mb-4">
            {b.lang === "mermaid" ? <p className="mb-1 text-2xs text-muted-foreground">{ctx.labels.mermaidNote}</p> : null}
            <pre tabIndex={0} className="overflow-x-auto rounded-lg border border-border bg-surface-2 p-3 font-mono text-[0.8125rem] leading-relaxed focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
              <code data-lang={b.lang || undefined}>{b.v}</code>
            </pre>
          </div>
        );
      case "quote":
        return (
          <blockquote key={i} className="mb-4 border-l-4 border-border-strong bg-surface-2/50 py-1 pr-3 pl-4 text-muted-foreground [&>p]:mb-2 [&>p]:text-muted-foreground">
            {renderBlocks(b.c, ctx, counter)}
          </blockquote>
        );
      case "list": {
        const Tag = b.ordered ? "ol" : "ul";
        return (
          <Tag key={i} start={b.ordered && b.start !== 1 ? b.start : undefined} className={cn("mb-4 space-y-1 pl-6 text-[0.9375rem] leading-7", b.ordered ? "list-decimal" : "list-disc", b.items.some((x) => x.task !== null) && "list-none pl-1")}>
            {b.items.map((it, k) => (
              <li key={k} className="[&>p]:mb-1 [&>ol]:mt-1 [&>ul]:mt-1 [&>ul]:mb-1">
                {it.task !== null ? (
                  <span className="mr-1.5 inline-block align-middle" aria-label={it.task ? "done" : "to do"} role="img">
                    {it.task ? "☑" : "☐"}
                  </span>
                ) : null}
                {renderBlocks(it.c, ctx, counter)}
              </li>
            ))}
          </Tag>
        );
      }
      case "table": {
        const n = ++counter.table;
        return (
          <div key={i} tabIndex={0} role="region" aria-label={ctx.labels.table(n)} className="relative mb-5 overflow-x-auto rounded-lg border border-border focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
            <table className="w-full border-collapse text-left text-[0.8125rem]">
              <thead className="bg-surface-2">
                <tr>
                  {b.head.map((c, k) => (
                    <th key={k} scope="col" className={cn("border-b border-border px-3 py-2 font-semibold whitespace-nowrap", b.align[k] === "right" && "text-right", b.align[k] === "center" && "text-center")}>
                      {renderInline(c, ctx)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {b.rows.map((r, ri) => (
                  <tr key={ri} className="border-b border-border last:border-0 align-top">
                    {r.map((c, k) => (
                      <td key={k} className={cn("px-3 py-2", b.align[k] === "right" && "text-right", b.align[k] === "center" && "text-center")}>
                        {renderInline(c, ctx)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      }
    }
  });
}

/** Server-renderable view of a parsed document (no client JS, no raw HTML). */
export function MarkdownView({ blocks, labels, mapRelative }: { blocks: readonly Block[]; labels: MarkdownLabels; mapRelative?: (rel: string) => string | null }) {
  return <div className="doc-md min-w-0">{renderBlocks(blocks, { labels, mapRelative }, { table: 0 })}</div>;
}
