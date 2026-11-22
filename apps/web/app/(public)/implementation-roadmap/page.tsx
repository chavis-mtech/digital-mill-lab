import type { Metadata } from "next";
import { ArrowRight, CircleCheck, Link2, ShieldAlert, Users, Package } from "lucide-react";
import { getLocale, getT } from "@/lib/i18n/server";
import pages from "@/content/public/pages.i18n";
import { ROADMAP } from "@/content/public/roadmap";
import { PublicPageHeader } from "@/components/public/public-layout";
import { Badge } from "@/components/ui/badge";

export const metadata: Metadata = { title: "Implementation roadmap" };

export default async function RoadmapPage() {
  const locale = await getLocale();
  const t = (await getT(pages)).roadmap;
  const first = ROADMAP.slice(0, 3);
  const years = ROADMAP.slice(3);

  const Phase = ({ p, idx }: { p: (typeof ROADMAP)[number]; idx: number }) => (
    <li id={p.id} className="relative rounded-2xl border border-border bg-surface p-6">
      <div className="flex flex-wrap items-center gap-3">
        <span className="tabular flex size-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">{idx + 1}</span>
        <p className="tabular text-xs font-semibold tracking-wide text-accent-text uppercase">{p.horizon[locale]}</p>
        <h3 className="text-lg font-semibold">{p.title[locale]}</h3>
      </div>
      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
        <span className="font-semibold text-foreground">{t.goal}: </span>
        {p.goal[locale]}
      </p>
      <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[
          { icon: Package, k: t.deliverables, v: p.deliverables[locale] },
          { icon: Users, k: t.roles, v: p.roles[locale] },
          { icon: Link2, k: t.dependencies, v: p.dependencies[locale] },
          { icon: CircleCheck, k: t.success, v: p.success[locale] },
        ].map((b) => (
          <div key={b.k} className="rounded-xl bg-surface-2 p-4">
            <p className="flex items-center gap-1.5 text-2xs font-semibold tracking-wide text-muted-foreground uppercase">
              <b.icon className="size-3.5" aria-hidden />
              {b.k}
            </p>
            <ul className="mt-2 list-disc space-y-1 pl-4 text-[0.8125rem] leading-relaxed">
              {b.v.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="mt-4 rounded-xl border border-dashed border-warning/50 p-4">
        <p className="flex items-center gap-1.5 text-2xs font-semibold tracking-wide text-warning-fg uppercase">
          <ShieldAlert className="size-3.5" aria-hidden />
          {t.risks}
        </p>
        <ul className="mt-2 flex flex-col gap-1.5 text-[0.8125rem]">
          {p.risks[locale].map((r) => (
            <li key={r.risk} className="flex flex-wrap items-baseline gap-x-2">
              <span>{r.risk}</span>
              <ArrowRight className="size-3 self-center text-subtle-foreground" aria-hidden />
              <span className="text-muted-foreground">
                <span className="sr-only">{t.mitigation}: </span>
                {r.mitigation}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </li>
  );

  return (
    <>
      <PublicPageHeader title={t.title} lead={t.lead}>
        <Badge tone="outline" className="px-2.5 py-1 text-xs">
          {t.tag}
        </Badge>
      </PublicPageHeader>
      <div className="mx-auto flex max-w-7xl flex-col gap-12 px-4 py-14 sm:px-6 lg:px-8">
        <section aria-labelledby="first90">
          <h2 id="first90" className="mb-5 text-2xl font-semibold tracking-tight">
            {t.first90}
          </h2>
          <ol className="flex flex-col gap-5">
            {first.map((p, i) => (
              <Phase key={p.id} p={p} idx={i} />
            ))}
          </ol>
        </section>
        <section aria-labelledby="years">
          <h2 id="years" className="mb-5 text-2xl font-semibold tracking-tight">
            {t.years}
          </h2>
          <ol className="flex flex-col gap-5">
            {years.map((p, i) => (
              <Phase key={p.id} p={p} idx={i + 3} />
            ))}
          </ol>
        </section>
      </div>
    </>
  );
}
