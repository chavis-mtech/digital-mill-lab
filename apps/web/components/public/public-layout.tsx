"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { ArrowRight, Menu } from "lucide-react";
import { useT } from "@/lib/i18n/client";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Brand } from "@/components/shell/brand";
import { LanguageToggle, ThemeToggle } from "@/components/shell/preferences";
import { Disclaimer } from "@/components/demo/disclaimer";
import { SyntheticDataBanner } from "@/components/demo/synthetic-data-banner";
import common from "@/messages/common.i18n";

function useLinks() {
  const t = useT(common);
  return [
    { href: "/about-project", label: t.nav.about },
    { href: "/business-opportunities", label: t.nav.opportunities },
    { href: "/technical-architecture", label: t.nav.architecture },
    { href: "/implementation-roadmap", label: t.nav.roadmap },
    { href: "/developer", label: t.nav.developer },
    { href: "/contact", label: t.nav.contact },
  ];
}

/** Public Landing layout: marketing header, content, footer with the independence disclaimer. */
export function PublicLayout({ children }: { children: ReactNode }) {
  const t = useT(common);
  const pathname = usePathname();
  const links = useLinks();
  const [open, setOpen] = useState(false);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- close the menu after navigation
    setOpen(false);
  }, [pathname]);

  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#main" className="sr-only-focusable fixed top-2 left-2 z-[60] rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground">
        {t.skipToContent}
      </a>
      <header className="sticky top-0 z-30 border-b border-border bg-background/85 backdrop-blur-md" data-print-hide>
        {/* SPEC §0 rule 2: the synthetic-data / independence banner is visible on every page, public ones included. */}
        <SyntheticDataBanner />
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4 sm:px-6 lg:px-8">
          <Brand className="max-2xl:[&>span>span:last-child]:hidden" />
          <nav aria-label={t.nav.mainNav} className="ml-4 hidden xl:block">
            <ul className="flex items-center gap-1">
              {links.map((l) => (
                <li key={l.href}>
                  <Link
                    href={l.href}
                    aria-current={pathname === l.href ? "page" : undefined}
                    className={cn(
                      "rounded-md px-2.5 py-1.5 text-[0.8125rem] font-medium whitespace-nowrap transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                      pathname === l.href ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <LanguageToggle className="hidden sm:inline-flex" />
            <ThemeToggle />
            <Button asChild variant="accent" size="sm" className="hidden md:inline-flex">
              <Link href="/demo">
                {t.nav.exploreDemo} <ArrowRight aria-hidden />
              </Link>
            </Button>
            <Button variant="ghost" size="icon-sm" className="xl:hidden" onClick={() => setOpen(true)} aria-label={t.nav.openMenu} aria-expanded={open}>
              <Menu aria-hidden />
            </Button>
          </div>
        </div>
      </header>

      <main id="main" tabIndex={-1} className="flex-1 outline-none">
        {children}
      </main>

      <footer className="border-t border-border bg-surface-2/50" data-print-hide>
        <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:px-6 md:grid-cols-[1.4fr_1fr_1fr] lg:px-8">
          <div className="flex flex-col gap-3">
            <Brand />
            <Disclaimer kind="independent" />
            <Disclaimer kind="synthetic" />
          </div>
          <nav aria-label={t.nav.mainNav}>
            <ul className="flex flex-col gap-2 text-sm">
              <li>
                <Link href="/" className="text-muted-foreground hover:text-foreground">
                  {t.nav.home}
                </Link>
              </li>
              {links.slice(0, 3).map((l) => (
                <li key={l.href}>
                  <Link href={l.href} className="text-muted-foreground hover:text-foreground">
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <ul className="flex flex-col gap-2 text-sm">
            {links.slice(3).map((l) => (
              <li key={l.href}>
                <Link href={l.href} className="text-muted-foreground hover:text-foreground">
                  {l.label}
                </Link>
              </li>
            ))}
            <li>
              <Link href="/demo" className="text-muted-foreground hover:text-foreground">
                {t.nav.demo}
              </Link>
            </li>
          </ul>
        </div>
        <div className="border-t border-border">
          <p className="mx-auto max-w-7xl px-4 py-4 text-xs text-subtle-foreground sm:px-6 lg:px-8">
            {t.footer.rights} {t.footer.builtWith}
          </p>
        </div>
      </footer>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent side="right" className="p-5" closeLabel={t.nav.closeMenu} aria-describedby={undefined}>
          <DialogTitle>{t.nav.mainNav}</DialogTitle>
          <nav aria-label={t.nav.mainNav}>
            <ul className="flex flex-col gap-1">
              {[{ href: "/", label: t.nav.home }, ...links].map((l) => (
                <li key={l.href}>
                  <Link
                    href={l.href}
                    aria-current={pathname === l.href ? "page" : undefined}
                    className="block rounded-md px-3 py-2 text-sm font-medium hover:bg-surface-2 aria-[current=page]:bg-accent-soft"
                  >
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <div className="flex items-center gap-2">
            <LanguageToggle />
          </div>
          <Button asChild variant="accent">
            <Link href="/demo">
              {t.nav.exploreDemo} <ArrowRight aria-hidden />
            </Link>
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/** Section scaffold for public pages. */
export function Section({ id, kicker, title, lead, children, className, tone = "plain" }: { id?: string; kicker?: string; title: string; lead?: string; children?: ReactNode; className?: string; tone?: "plain" | "muted" }) {
  return (
    <section id={id} aria-labelledby={id ? `${id}-title` : undefined} className={cn("py-16 sm:py-20", tone === "muted" && "border-y border-border bg-surface-2/50", className)}>
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl">
          {kicker ? <p className="text-xs font-semibold tracking-[0.12em] text-accent-text uppercase">{kicker}</p> : null}
          <h2 id={id ? `${id}-title` : undefined} className="mt-2 text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            {title}
          </h2>
          {lead ? <p className="mt-3 text-base leading-relaxed text-muted-foreground">{lead}</p> : null}
        </div>
        {children ? <div className="mt-10">{children}</div> : null}
      </div>
    </section>
  );
}

/** Page header for public sub-pages. */
export function PublicPageHeader({ kicker, title, lead, children }: { kicker?: string; title: string; lead?: string; children?: ReactNode }) {
  return (
    <div className="relative overflow-hidden border-b border-border">
      <div aria-hidden className="surface-grid absolute inset-0 [mask-image:radial-gradient(ellipse_at_top_left,black,transparent_70%)] opacity-60" />
      <div className="relative mx-auto max-w-7xl px-4 py-14 sm:px-6 sm:py-16 lg:px-8">
        {kicker ? <p className="text-xs font-semibold tracking-[0.12em] text-accent-text uppercase">{kicker}</p> : null}
        <h1 className="mt-2 max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
        {lead ? <p className="mt-4 max-w-3xl text-base leading-relaxed text-muted-foreground sm:text-lg">{lead}</p> : null}
        {children ? <div className="mt-6">{children}</div> : null}
      </div>
    </div>
  );
}
