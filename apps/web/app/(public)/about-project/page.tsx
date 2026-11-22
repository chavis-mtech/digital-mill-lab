import type { Metadata } from "next";
import { CircleCheck, CircleX } from "lucide-react";
import { getT } from "@/lib/i18n/server";
import pages from "@/content/public/pages.i18n";
import common from "@/messages/common.i18n";
import { PublicPageHeader, Section } from "@/components/public/public-layout";
import { StatusLegend } from "@/components/demo/status-chip";
import { Badge } from "@/components/ui/badge";

export const metadata: Metadata = { title: "About the project" };

const TAGS = [
  "verified_public_fact",
  "historical_public_information",
  "industry_practice",
  "engineering_assumption",
  "synthetic_demonstration_data",
  "proposed_future_capability",
] as const;

export default async function AboutPage() {
  const t = (await getT(pages)).about;
  const c = await getT(common);
  return (
    <>
      <PublicPageHeader title={t.title} lead={t.lead} />
      <Section title={t.whatTitle}>
        <div className="grid gap-6 lg:grid-cols-2">
          <ul className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-6">
            {t.what.map((w) => (
              <li key={w} className="flex gap-3 text-sm">
                <CircleCheck className="mt-0.5 size-4 shrink-0 text-success-fg" aria-hidden />
                {w}
              </li>
            ))}
          </ul>
          <div className="rounded-xl border border-border bg-surface p-6">
            <h3 className="mb-3 text-sm font-semibold">{t.notTitle}</h3>
            <ul className="flex flex-col gap-3">
              {t.not.map((w) => (
                <li key={w} className="flex gap-3 text-sm">
                  <CircleX className="mt-0.5 size-4 shrink-0 text-critical-fg" aria-hidden />
                  {w}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Section>
      <Section tone="muted" title={t.principlesTitle}>
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {t.principles.map((p) => (
            <li key={p.t} className="rounded-xl border border-border bg-surface p-5">
              <h3 className="text-sm font-semibold">{p.t}</h3>
              <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{p.d}</p>
            </li>
          ))}
        </ul>
      </Section>
      <Section title={t.taxonomyTitle} lead={t.taxonomyBody}>
        <ul className="flex flex-wrap gap-2">
          {TAGS.map((k) => (
            <li key={k}>
              <Badge tone="outline" className="px-2.5 py-1 text-xs">
                {c.factTag[k]}
              </Badge>
            </li>
          ))}
        </ul>
      </Section>
      <Section tone="muted" title={t.scenariosTitle} lead={t.scenariosBody} />
      <Section title={t.statusTitle} lead={t.statusBody}>
        <StatusLegend />
      </Section>
    </>
  );
}
