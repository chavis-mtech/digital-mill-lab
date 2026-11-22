import type { Metadata } from "next";
import { getLocale, getT } from "@/lib/i18n/server";
import pages from "@/content/public/pages.i18n";
import { DECISIONS, INTEGRATIONS, LAYERS, LIFECYCLE, MONOREPO } from "@/content/public/architecture";
import { PublicPageHeader, Section } from "@/components/public/public-layout";
import { ArchitectureDiagram } from "@/components/public/architecture-diagram";
import { StatusChip, StatusLegend } from "@/components/demo/status-chip";

export const metadata: Metadata = { title: "Technical architecture" };

export default async function ArchitecturePage() {
  const locale = await getLocale();
  const t = (await getT(pages)).architecture;
  return (
    <>
      <PublicPageHeader title={t.title} lead={t.lead}>
        <StatusLegend />
      </PublicPageHeader>
      <Section title={t.diagramTitle}>
        <ArchitectureDiagram title={t.diagramTitle} description={t.diagramDesc} />
      </Section>
      <Section tone="muted" title={t.layersTitle}>
        <div tabIndex={0} role="region" aria-label={t.layersTitle} className="overflow-x-auto rounded-xl border border-border bg-surface">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">{t.layersTitle}</caption>
            <thead className="bg-surface-2 text-xs text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-2.5 font-semibold">Layer</th>
                <th scope="col" className="px-4 py-2.5 font-semibold">Location</th>
                <th scope="col" className="px-4 py-2.5 font-semibold">Rule</th>
              </tr>
            </thead>
            <tbody>
              {LAYERS.map((l) => (
                <tr key={l.layer} className="border-t border-border">
                  <th scope="row" className="px-4 py-2.5 font-medium whitespace-nowrap">{l.layer}</th>
                  <td className="px-4 py-2.5 font-mono text-xs whitespace-nowrap text-muted-foreground">{l.location}</td>
                  <td className="px-4 py-2.5 text-muted-foreground">{l.rule[locale]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
      <Section title={t.decisionsTitle}>
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {DECISIONS.map((d) => (
            <li key={d.id} className="rounded-xl border border-border bg-surface p-5">
              <p className="font-mono text-2xs text-accent-text">{d.id}</p>
              <h3 className="mt-1 text-sm font-semibold">{d.title[locale]}</h3>
              <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{d.why[locale]}</p>
            </li>
          ))}
        </ul>
      </Section>
      <Section tone="muted" title={t.integrationTitle} lead={t.integrationBody}>
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {INTEGRATIONS.map((i) => (
            <li key={i.system} className="flex flex-col gap-1.5 rounded-xl border border-dashed border-border-strong bg-surface p-4">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-semibold">{i.system}</span>
                <StatusChip feature="integration_contracts" showTooltip={false} />
              </div>
              <p className="text-xs text-muted-foreground">{i.direction[locale]}</p>
              <p className="text-2xs text-subtle-foreground">{i.needs[locale]}</p>
            </li>
          ))}
        </ul>
      </Section>
      <Section title={t.monorepoTitle}>
        <div className="grid gap-6 lg:grid-cols-2">
          <pre tabIndex={0} aria-label={t.monorepoTitle} className="overflow-x-auto rounded-xl border border-border bg-surface-2 p-5 font-mono text-xs leading-6">{MONOREPO}</pre>
          <div>
            <h3 className="mb-3 text-sm font-semibold">{t.requestTitle}</h3>
            <ol className="flex flex-col gap-2">
              {LIFECYCLE.map((s, i) => (
                <li key={s.en} className="flex gap-3 text-sm">
                  <span className="tabular flex size-6 shrink-0 items-center justify-center rounded-full bg-surface-3 text-2xs font-semibold">{i + 1}</span>
                  <span className="text-muted-foreground">{s[locale]}</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </Section>
    </>
  );
}
