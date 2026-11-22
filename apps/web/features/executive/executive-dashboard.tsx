"use client";

import Link from "next/link";
import { useApiQuery } from "@/lib/api/hooks";
import { useDemo } from "@/lib/demo/context";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatDate } from "@/lib/format";
import { ExecutiveLayout } from "@/components/layouts/layouts";
import { KpiCard } from "@/components/data/kpi-card";
import { Disclaimer } from "@/components/demo/disclaimer";
import { ErrorState, LoadingState } from "@/components/states/states";
import messages from "./executive.i18n";
import { DecisionBand } from "./decision-band";
import { ExecutiveFilters } from "./filters";
import { ExportMenu } from "./export-menu";
import { AlertPriority, Bottlenecks, CostProductivity, ImpactCards, InsightSummary, KpiTrend, ScenarioComparison } from "./panels";
import { kpiHref, orderKpis } from "./shared/links";
import { useKpiLabel } from "./use-labels";

const DIGITS: Record<string, number> = { oer_pct: 2, ker_pct: 2, throughput_tph: 1, energy_kwh_per_t: 2, logistics_queue_time_min: 1, plant_downtime_h: 1 };

/**
 * Drill-down wrapper. The kit's `KpiCard href` sets an aria-label that hides the visible value from the
 * accessible name (axe label-content-name-mismatch), so the link takes its name from the card content.
 */
function KpiLink({ href, tour, children }: { href?: string; tour?: string; children: React.ReactNode }) {
  if (!href) return <div data-tour={tour}>{children}</div>;
  return (
    <Link
      href={href}
      data-tour={tour}
      className="group block rounded-xl transition-shadow hover:shadow-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      {children}
    </Link>
  );
}

/** Executive Industrial Control Tower (DML-036..042). First paint from GET /executive/overview. */
export function ExecutiveDashboard() {
  const t = useT(messages);
  const label = useKpiLabel();
  const { locale } = useLocale();
  const { period } = useDemo();
  const q = useApiQuery("/api/v1/executive/overview", { params: { query: { period } } });

  let kpis: React.ReactNode;
  if (q.isPending) {
    kpis = (
      <>
        <LoadingState className="col-span-full" lines={2} />
        {Array.from({ length: 12 }, (_, i) => (
          <KpiCard key={i} loading />
        ))}
      </>
    );
  } else if (q.isError) {
    kpis = <ErrorState error={q.error} onRetry={() => void q.refetch()} className="col-span-full" />;
  } else {
    const d = q.data;
    kpis = (
      <>
        <DecisionBand data={d} />
        <p className="col-span-full -mb-1 text-2xs text-muted-foreground">
          {t.filters.periodRange(formatDate(d.kpis.period_start, locale, "datetime"), formatDate(d.kpis.period_end, locale, "datetime"))} ·{" "}
          {t.filters.previousRange(formatDate(d.kpis.previous_start, locale, "datetime"), formatDate(d.kpis.previous_end, locale, "datetime"))}
        </p>
        {orderKpis(d.kpis.kpis).map((k) => (
          <KpiLink key={k.key} href={kpiHref(k.key)} tour={k.key === "oer_pct" ? "exec-kpi-oer" : undefined}>
            <KpiCard kpi={k} label={label(k.key, k.label)} sparkline={d.kpis.sparklines?.[k.key]} digits={DIGITS[k.key]} className="h-full" />
          </KpiLink>
        ))}
        <Disclaimer kind="roi" className="col-span-full text-2xs" />
      </>
    );
  }

  return (
    <ExecutiveLayout
      route="/demo/executive"
      kpis={
        <>
          <div className="col-span-full -mt-2 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-surface px-3 py-2">
            <ExecutiveFilters />
            <ExportMenu />
          </div>
          {kpis}
        </>
      }
      aside={
        <>
          {q.data ? <InsightSummary insight={q.data.insight} /> : null}
          <AlertPriority />
        </>
      }
    >
      {q.data ? <ImpactCards cards={q.data.impact_cards} /> : null}
      <KpiTrend />
      <div className="grid grid-cols-1 gap-6 2xl:grid-cols-2">
        <Bottlenecks />
        <ScenarioComparison />
      </div>
      <CostProductivity />
    </ExecutiveLayout>
  );
}
