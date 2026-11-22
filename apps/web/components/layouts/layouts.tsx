"use client";

/**
 * Page layouts used inside <AppShell> (SPEC §5: Executive App · Industrial Operations · AI Workspace ·
 * Technical Docs; the Public Landing layout is `components/public/public-layout.tsx`).
 *
 * Usage (a downstream page):
 *   export default function Page() {
 *     return (
 *       <ExecutiveLayout route="/demo/executive" actions={<ExportButton/>} kpis={<KpiGrid/>}>
 *         …main grid…
 *       </ExecutiveLayout>
 *     );
 *   }
 * `route` pulls title/description/status from content/routes.ts so headers stay consistent.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { ChevronRight, PanelRight } from "lucide-react";
import { useLocale, useT } from "@/lib/i18n/client";
import { cn } from "@/lib/utils";
import { childRoutes, findRoute, ALL_APP_ROUTES, type RouteEntry } from "@/content/routes";
import type { FeatureKey } from "@/content/status";
import { StatusChip } from "@/components/demo/status-chip";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import common from "@/messages/common.i18n";

type HeaderProps = {
  /** Registry path (content/routes.ts) — supplies title, description and feature status. */
  route?: string;
  title?: ReactNode;
  description?: ReactNode;
  feature?: FeatureKey;
  actions?: ReactNode;
  eyebrow?: ReactNode;
};

function useRouteEntry(route?: string): RouteEntry | undefined {
  const pathname = usePathname();
  return findRoute(route ?? pathname);
}

export function PageHeader({ route, title, description, feature, actions, eyebrow, breadcrumbs = true }: HeaderProps & { breadcrumbs?: boolean }) {
  const entry = useRouteEntry(route);
  const { locale } = useLocale();
  const t = useT(common);
  const parent = entry?.parent ? findRoute(entry.parent) : undefined;
  const feat = feature ?? entry?.feature;
  return (
    <header className="flex flex-col gap-3 border-b border-border pb-5 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {breadcrumbs && entry ? (
          <nav aria-label="Breadcrumb" className="mb-1.5">
            <ol className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
              <li>
                <Link href={entry.layout === "docs" ? "/docs/overview" : "/demo"} className="hover:text-foreground">
                  {entry.layout === "docs" ? t.nav.docs : t.nav.demo}
                </Link>
              </li>
              {parent ? (
                <>
                  <ChevronRight className="size-3" aria-hidden />
                  <li>
                    <Link href={parent.path} className="hover:text-foreground">
                      {parent.title[locale]}
                    </Link>
                  </li>
                </>
              ) : null}
              <ChevronRight className="size-3" aria-hidden />
              <li aria-current="page" className="text-foreground">
                {entry.title[locale]}
              </li>
            </ol>
          </nav>
        ) : eyebrow ? (
          <div className="mb-1.5 text-xs text-muted-foreground">{eyebrow}</div>
        ) : null}
        <div className="flex flex-wrap items-center gap-2.5">
          <h1 className="text-xl font-semibold tracking-tight text-foreground sm:text-2xl">{title ?? entry?.title[locale]}</h1>
          {feat ? <StatusChip feature={feat} size="md" /> : null}
        </div>
        {(description ?? entry?.description[locale]) ? <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{description ?? entry?.description[locale]}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}

const PAGE = "mx-auto flex w-full max-w-[1600px] flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8";

/** Executive App layout: header, KPI strip, then a main + aside grid (aside drops below on tablet). */
export function ExecutiveLayout({ kpis, aside, children, className, breadcrumbs, ...header }: HeaderProps & { kpis?: ReactNode; aside?: ReactNode; children?: ReactNode; className?: string; breadcrumbs?: boolean }) {
  return (
    <div className={cn(PAGE, className)} data-layout="executive">
      <PageHeader {...header} breadcrumbs={breadcrumbs} />
      {kpis ? <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">{kpis}</section> : null}
      {aside ? (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="flex min-w-0 flex-col gap-6">{children}</div>
          <aside className="flex min-w-0 flex-col gap-4">{aside}</aside>
        </div>
      ) : (
        children
      )}
    </div>
  );
}

/** Sub-navigation tabs for a module (parent + children from the route registry). */
function ModuleTabs({ route }: { route?: string }) {
  const pathname = usePathname();
  const { locale } = useLocale();
  const entry = findRoute(route ?? pathname);
  if (!entry) return null;
  const root = entry.parent ? findRoute(entry.parent) : entry;
  if (!root) return null;
  const items = [root, ...childRoutes(root.path)];
  if (items.length < 2) return null;
  return (
    <nav aria-label={root.title[locale]} className="-mt-2 overflow-x-auto scrollbar-thin">
      <ul className="flex min-w-max gap-1 border-b border-border">
        {items.map((r) => {
          const active = r.path === pathname;
          return (
            <li key={r.path}>
              <Link
                href={r.path}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "-mb-px inline-flex items-center border-b-2 px-3 py-2 text-[0.8125rem] font-medium whitespace-nowrap transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                  active ? "border-accent text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
                )}
              >
                {r.title[locale]}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** Industrial Operations layout: dense header, module tabs, optional toolbar (filters), content. */
export function OperationsLayout({ toolbar, children, className, ...header }: HeaderProps & { toolbar?: ReactNode; children?: ReactNode; className?: string }) {
  return (
    <div className={cn(PAGE, "gap-5", className)} data-layout="operations">
      <PageHeader {...header} />
      <ModuleTabs route={header.route} />
      {toolbar ? <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2">{toolbar}</div> : null}
      {children}
    </div>
  );
}

/**
 * AI Workspace layout: main work area (conversation / analysis) + evidence rail. Below xl the rail becomes
 * a drawer opened from the header.
 */
export function AIWorkspaceLayout({ rail, railTitle, children, className, ...header }: HeaderProps & { rail?: ReactNode; railTitle?: string; children?: ReactNode; className?: string }) {
  const [open, setOpen] = useState(false);
  const t = useT(common);
  const title = railTitle ?? t.evidence.title;
  return (
    <div className={cn(PAGE, "gap-5", className)} data-layout="ai">
      <PageHeader
        {...header}
        actions={
          <>
            {header.actions}
            {rail ? (
              <Button variant="outline" size="sm" className="xl:hidden" onClick={() => setOpen(true)}>
                <PanelRight aria-hidden /> {title}
              </Button>
            ) : null}
          </>
        }
      />
      <div className={cn("grid grid-cols-1 gap-6", rail && "xl:grid-cols-[minmax(0,1fr)_24rem]")}>
        <div className="flex min-w-0 flex-col gap-4">{children}</div>
        {rail ? (
          <aside aria-label={title} className="hidden min-w-0 flex-col gap-4 xl:sticky xl:top-[calc(var(--topbar-h)+var(--banner-h)+1.5rem)] xl:flex xl:max-h-[calc(100dvh-var(--topbar-h)-var(--banner-h)-3rem)] xl:self-start xl:overflow-y-auto">
            {rail}
          </aside>
        ) : null}
      </div>
      {rail ? (
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogContent side="right" className="overflow-y-auto p-4" closeLabel={t.common.close} aria-describedby={undefined}>
            <DialogTitle>{title}</DialogTitle>
            {rail}
          </DialogContent>
        </Dialog>
      ) : null}
    </div>
  );
}

/** Technical Docs layout: docs header + readable prose column + optional "on this page" list. */
export function DocsLayout({ toc, children, className, ...header }: HeaderProps & { toc?: { id: string; label: string }[]; children?: ReactNode; className?: string }) {
  return (
    <div className={cn("mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8", className)} data-layout="docs">
      <PageHeader {...header} />
      <div className={cn("grid grid-cols-1 gap-8", toc?.length && "lg:grid-cols-[minmax(0,1fr)_13rem]")}>
        <article className="prose-doc min-w-0 max-w-3xl text-[0.9375rem] leading-7 text-foreground [&_h2]:mt-8 [&_h2]:mb-3 [&_h2]:text-lg [&_h2]:font-semibold [&_h3]:mt-6 [&_h3]:mb-2 [&_h3]:font-semibold [&_p]:mb-4 [&_p]:text-muted-foreground [&_ul]:mb-4 [&_ul]:list-disc [&_ul]:pl-5 [&_code]:rounded [&_code]:bg-surface-2 [&_code]:px-1 [&_code]:font-mono [&_code]:text-[0.8125rem]">
          {children}
        </article>
        {toc?.length ? (
          <nav aria-label="On this page" className="hidden lg:block">
            <ul className="sticky top-[calc(var(--topbar-h)+var(--banner-h)+1.5rem)] flex flex-col gap-1.5 border-l border-border pl-3 text-xs">
              {toc.map((i) => (
                <li key={i.id}>
                  <a href={`#${i.id}`} className="text-muted-foreground hover:text-foreground">
                    {i.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        ) : null}
      </div>
    </div>
  );
}

/** All registered app routes — exported for hubs/indexes. */
export const APP_ROUTES = ALL_APP_ROUTES;
