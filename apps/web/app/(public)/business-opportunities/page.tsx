import type { Metadata } from "next";
import Link from "next/link";
import { ArrowUpRight, Bot, Gauge, GitBranch, Truck, Wrench, Zap } from "lucide-react";
import { getLocale, getT } from "@/lib/i18n/server";
import pages from "@/content/public/pages.i18n";
import common from "@/messages/common.i18n";
import { OPPORTUNITIES } from "@/content/public/opportunities";
import { PublicPageHeader } from "@/components/public/public-layout";
import { StatusChip } from "@/components/demo/status-chip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = { title: "Business opportunities" };
const ICONS = { gauge: Gauge, wrench: Wrench, truck: Truck, zap: Zap, "git-branch": GitBranch, bot: Bot } as const;

export default async function OpportunitiesPage() {
  const locale = await getLocale();
  const t = (await getT(pages)).opportunities;
  const c = await getT(common);
  return (
    <>
      <PublicPageHeader title={t.title} lead={t.lead}>
        <p className="text-xs text-subtle-foreground">{t.note}</p>
      </PublicPageHeader>
      <div className="mx-auto flex max-w-7xl flex-col gap-5 px-4 py-14 sm:px-6 lg:px-8">
        {OPPORTUNITIES.map((o) => {
          const Icon = ICONS[o.icon];
          return (
            <article key={o.id} id={o.id} className="grid gap-5 rounded-2xl border border-border bg-surface p-6 lg:grid-cols-[1fr_1.4fr]">
              <div className="flex flex-col gap-3">
                <span className="flex size-10 items-center justify-center rounded-lg bg-accent-soft text-accent-text">
                  <Icon className="size-5" aria-hidden />
                </span>
                <h2 className="text-lg font-semibold">{o.title[locale]}</h2>
                <p className="text-sm leading-relaxed text-muted-foreground">{o.summary[locale]}</p>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="outline">{c.factTag[o.tag]}</Badge>
                  <StatusChip feature={o.feature} />
                </div>
                <Button asChild variant="link" className="justify-start">
                  <Link href={o.demoRoute}>
                    {t.tryDemo} <ArrowUpRight aria-hidden />
                  </Link>
                </Button>
              </div>
              <dl className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
                {[
                  [t.value, o.value[locale]],
                  [t.evidence, o.evidenceNeeded[locale]],
                  [t.needs, o.realPlantNeeds[locale]],
                ].map(([k, v]) => (
                  <div key={k} className="rounded-xl bg-surface-2 p-4">
                    <dt className="text-2xs font-semibold tracking-wide text-muted-foreground uppercase">{k}</dt>
                    <dd className="mt-1.5 text-sm leading-relaxed">{v}</dd>
                  </div>
                ))}
              </dl>
            </article>
          );
        })}
      </div>
    </>
  );
}
