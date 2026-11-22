"use client";

import Link from "next/link";
import { ArrowDown, CircleAlert, Coins, Gavel, Users } from "lucide-react";
import type { Schema } from "@dml/contracts";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatValue } from "@/lib/format";
import { cn } from "@/lib/utils";
import { SeverityPill } from "./shared/sev";
import { ProvenanceBadge } from "@/components/demo/provenance-badge";
import { Disclaimer } from "@/components/demo/disclaimer";
import messages from "./executive.i18n";
import { alertHref, teamKey } from "./shared/links";
import { ApiText } from "./shared/section";

type Overview = Schema<"ExecutiveOverviewResponse">;

/** Impact cards shown in the band: money + tonnes first (keys from the API), else the first two. */
export function pickBandImpacts(cards: Overview["impact_cards"]): Overview["impact_cards"] {
  const preferred = ["lost_cpo_t", "lost_cpo_value_thb"];
  const hit = preferred.map((k) => cards.find((c) => c.key === k)).filter((c): c is NonNullable<typeof c> => !!c);
  return hit.length ? hit : cards.slice(0, 2);
}

function Cell({ icon: Icon, title, children, className }: { icon: typeof Users; title: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5 rounded-lg bg-surface p-3", className)}>
      <p className="flex items-center gap-1.5 text-2xs font-semibold tracking-wide text-muted-foreground uppercase">
        <Icon className="size-3.5" aria-hidden />
        {title}
      </p>
      <div className="min-w-0 text-sm">{children}</div>
    </div>
  );
}

/**
 * "What to decide / who checks first" band (SPEC §4-A executive question). Every element comes from
 * GET /executive/overview (insight items, impact cards, alerts); nothing here is pre-written prose.
 */
export function DecisionBand({ data, className }: { data: Overview; className?: string }) {
  const t = useT(messages);
  const { locale } = useLocale();
  const items = data.insight?.items ?? [];
  const top = items[0];
  const impacts = pickBandImpacts(data.impact_cards);
  const equipment = top?.related.find((r) => r.type === "equipment");
  const alertRef = top?.related.find((r) => r.type === "alert");
  const topAlert = alertRef ? data.top_alerts.find((a) => a.id === alertRef.id) : undefined;

  return (
    <section
      aria-labelledby="exec-decision-title"
      data-tour="exec-insight-summary"
      className={cn("col-span-full flex flex-col gap-3 rounded-xl border border-border-strong bg-surface-2 p-3 sm:p-4", className)}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 id="exec-decision-title" className="text-base font-semibold tracking-tight">
          {t.decision.title}
        </h2>
        <p className="text-2xs text-muted-foreground">
          {t.decision.subtitle}
          {locale === "th" ? ` · ${t.decision.apiTextNote}` : ""}
        </p>
      </div>
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-4">
        <Cell icon={CircleAlert} title={t.decision.whatAbnormal}>
          {top ? (
            <div className="flex flex-col gap-1">
              <p className="text-xs text-muted-foreground">{t.decision.findings(items.length)}</p>
              <div className="flex items-start gap-1.5">
                <SeverityPill severity={top.severity} className="mt-0.5" />
                <p className="font-medium">
                  <ApiText>{top.headline}</ApiText>
                </p>
              </div>
            </div>
          ) : (
            <p className="text-muted-foreground">{t.decision.nothingAbnormal}</p>
          )}
        </Cell>
        <Cell icon={Coins} title={t.decision.howMuch}>
          {impacts.length ? (
            <ul className="flex flex-col gap-1.5">
              {impacts.map((c) => (
                <li key={c.key} className="flex flex-col">
                  <span className="flex flex-wrap items-center gap-1.5">
                    <span className="tabular text-lg leading-tight font-semibold">{formatValue(c.value, c.unit, locale)}</span>
                    <ProvenanceBadge provenance={c.provenance} compact />
                  </span>
                  <span className="text-2xs text-muted-foreground">
                    <ApiText>{c.label}</ApiText>
                  </span>
                </li>
              ))}
              <li>
                <Disclaimer kind="roi" className="text-2xs" />
              </li>
            </ul>
          ) : (
            <p className="text-muted-foreground">{t.decision.noImpact}</p>
          )}
        </Cell>
        <Cell icon={Users} title={t.decision.whoFirst}>
          {top ? (
            <div className="flex flex-col gap-1">
              <p className="font-semibold">{t.team[teamKey(top.suggested_team)]}</p>
              {equipment ? (
                <Link
                  className="text-xs text-accent-text underline underline-offset-2"
                  href={topAlert ? alertHref(topAlert) : `/demo/maintenance/equipment?equipment_id=${encodeURIComponent(String(equipment.id))}`}
                >
                  {equipment.code ?? equipment.label}
                  {equipment.label && equipment.code ? ` — ${equipment.label}` : ""}
                </Link>
              ) : null}
            </div>
          ) : (
            <p className="text-muted-foreground">—</p>
          )}
        </Cell>
        <Cell icon={Gavel} title={t.decision.decide}>
          {top?.suggested_decision ? (
            <div className="flex flex-col gap-1.5">
              <p>
                <ApiText>{top.suggested_decision}</ApiText>
              </p>
              <a href="#exec-insights" className="inline-flex items-center gap-1 text-xs text-accent-text underline underline-offset-2">
                <ArrowDown className="size-3" aria-hidden /> {t.decision.openEvidence}
              </a>
            </div>
          ) : (
            <p className="text-muted-foreground">{t.decision.noDecision}</p>
          )}
        </Cell>
      </div>
    </section>
  );
}
