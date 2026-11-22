"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { ArrowLeft, BookOpen, LayoutGrid, Menu } from "lucide-react";
import { useLocale, useT } from "@/lib/i18n/client";
import { cn } from "@/lib/utils";
import { DEMO_ROUTES, DOCS_ROUTES, NAV_GROUPS, type NavGroupKey, type RouteEntry } from "@/content/routes";
import { FEATURES } from "@/content/status";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { SyntheticDataBanner } from "@/components/demo/synthetic-data-banner";
import { STATUS_STYLE } from "@/components/demo/status-chip";
import { StartTourButton } from "@/components/tour/tour";
import { Brand } from "./brand";
import { DemoControls } from "./demo-controls";
import { MetaIndicator } from "./meta-indicator";
import { ROUTE_ICONS } from "./icons";
import common from "@/messages/common.i18n";

function NavItem({ route, active, onNavigate }: { route: RouteEntry; active: boolean; onNavigate?: () => void }) {
  const { locale } = useLocale();
  const t = useT(common);
  const Icon = ROUTE_ICONS[route.icon];
  const status = FEATURES[route.feature].status;
  const StatusIcon = STATUS_STYLE[status].icon;
  return (
    <li>
      <Link
        href={route.path}
        onClick={onNavigate}
        aria-current={active ? "page" : undefined}
        className={cn(
          "group flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[0.8125rem] transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
          route.parent && "ml-3.5 border-l border-border pl-3",
          active ? "bg-accent-soft font-semibold text-foreground" : "text-muted-foreground hover:bg-surface-2 hover:text-foreground",
        )}
      >
        <Icon className={cn("size-4 shrink-0", active ? "text-accent-text" : "text-subtle-foreground group-hover:text-muted-foreground")} aria-hidden />
        <span className="min-w-0 flex-1 truncate">{route.title[locale]}</span>
        <StatusIcon className="size-3 shrink-0 text-subtle-foreground" aria-hidden />
        <span className="sr-only">({t.status[status]})</span>
      </Link>
    </li>
  );
}

function SidebarNav({ area, onNavigate }: { area: "demo" | "docs"; onNavigate?: () => void }) {
  const pathname = usePathname();
  const { locale } = useLocale();
  const t = useT(common);
  const routes = area === "demo" ? DEMO_ROUTES : DOCS_ROUTES;
  const groups = Array.from(new Set(routes.map((r) => r.group))) as NavGroupKey[];

  return (
    <nav aria-label={area === "demo" ? t.nav.demoNav : t.nav.docs} className="flex flex-col gap-5">
      <ul className="flex flex-col gap-0.5">
        <li>
          <Link
            href="/demo"
            onClick={onNavigate}
            aria-current={pathname === "/demo" ? "page" : undefined}
            className={cn(
              "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[0.8125rem] transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
              pathname === "/demo" ? "bg-accent-soft font-semibold text-foreground" : "text-muted-foreground hover:bg-surface-2 hover:text-foreground",
            )}
          >
            <LayoutGrid className="size-4 text-subtle-foreground" aria-hidden />
            {t.nav.demoHub}
          </Link>
        </li>
        <li>
          <Link
            href={area === "demo" ? "/docs/overview" : "/demo"}
            onClick={onNavigate}
            className="flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[0.8125rem] text-muted-foreground transition-colors hover:bg-surface-2 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <BookOpen className="size-4 text-subtle-foreground" aria-hidden />
            {area === "demo" ? t.nav.docs : t.nav.demo}
          </Link>
        </li>
      </ul>
      {groups.map((g) => (
        <div key={g}>
          <p className="mb-1 px-2.5 text-[0.625rem] font-semibold tracking-[0.08em] text-subtle-foreground uppercase">{NAV_GROUPS[g][locale]}</p>
          <ul className="flex flex-col gap-0.5">
            {routes
              .filter((r) => r.group === g)
              .map((r) => (
                <NavItem key={r.path} route={r} active={pathname === r.path} onNavigate={onNavigate} />
              ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

/**
 * Application shell for the demo and docs areas: persistent Synthetic-Data banner, top bar with
 * DemoControls, sidebar navigation (drawer below lg). Feature pages render inside `<main>` using one of the
 * page layouts (ExecutiveLayout / OperationsLayout / AIWorkspaceLayout / DocsLayout).
 */
export function AppShell({ area, children }: { area: "demo" | "docs"; children: ReactNode }) {
  const t = useT(common);
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- close the drawer after navigation
    setOpen(false);
  }, [pathname]);

  const sidebarBody = (onNavigate?: () => void) => (
    <div className="flex h-full flex-col gap-6">
      <SidebarNav area={area} onNavigate={onNavigate} />
      <div className="mt-auto flex flex-col gap-3 border-t border-border pt-4">
        <MetaIndicator />
        <Link href="/" className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-3.5" aria-hidden /> {t.nav.backToSite}
        </Link>
      </div>
    </div>
  );

  return (
    <div className="min-h-dvh">
      <a href="#main" className="sr-only-focusable fixed top-2 left-2 z-[60] rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground">
        {t.skipToContent}
      </a>
      <header className="sticky top-0 z-30" data-print-hide>
        <SyntheticDataBanner />
        <div className="flex h-[var(--topbar-h)] items-center gap-3 border-b border-border bg-surface/90 px-3 backdrop-blur-md sm:px-4">
          <Button variant="ghost" size="icon-sm" className="lg:hidden" onClick={() => setOpen(true)} aria-label={t.nav.openMenu} aria-expanded={open}>
            <Menu aria-hidden />
          </Button>
          <Brand href="/demo" className="lg:w-[calc(var(--sidebar-w)-1.5rem)] max-sm:[&>span]:sr-only" />
          <div className="ml-auto flex min-w-0 items-center gap-2">
            <StartTourButton variant="accent" size="sm" className="hidden lg:inline-flex" />
            <DemoControls />
          </div>
        </div>
      </header>

      <div className="flex">
        <aside
          className="sticky top-[calc(var(--topbar-h)+var(--banner-h))] hidden h-[calc(100dvh-var(--topbar-h)-var(--banner-h))] w-[var(--sidebar-w)] shrink-0 overflow-y-auto border-r border-border bg-surface/60 px-3 py-4 scrollbar-thin lg:block"
          data-print-hide
        >
          {sidebarBody()}
        </aside>
        <main id="main" tabIndex={-1} className="min-w-0 flex-1 outline-none">
          {children}
        </main>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent side="left" className="overflow-y-auto px-3 py-4" closeLabel={t.nav.closeMenu} aria-describedby={undefined}>
          <DialogTitle className="sr-only">{t.nav.demoNav}</DialogTitle>
          <Brand href="/demo" className="mb-2 px-1" />
          <StartTourButton variant="accent" size="sm" className="mb-2 lg:hidden" />
          {sidebarBody(() => setOpen(false))}
        </DialogContent>
      </Dialog>
    </div>
  );
}
