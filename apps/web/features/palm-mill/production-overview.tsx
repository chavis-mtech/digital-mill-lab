"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import type { Schema } from "@dml/contracts";
import { useApiQuery } from "@/lib/api/hooks";
import { useDemo } from "@/lib/demo/context";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatDate, formatNumber, formatValue } from "@/lib/format";
import { cn } from "@/lib/utils";
import { OperationsLayout } from "@/components/layouts/layouts";
import { Button } from "@/components/ui/button";
import { KpiCard } from "@/components/data/kpi-card";
import { ProvenanceBadge } from "@/components/demo/provenance-badge";
import { Sparkline, TimeSeriesChart } from "@/components/charts/charts";
import { ErrorState, LoadingState, QueryState } from "@/components/states/states";
import { ApiText, Section } from "@/features/executive/shared/section";
import { FormulaPanel } from "@/features/executive/shared/formulas";
import { useKpiLabel } from "@/features/executive/use-labels";
import messages from "./palm-mill.i18n";
import { oerChartSeries } from "./oer-band";

type MassBalance = Schema<"MassBalance">;

const STREAMS = ["cpo_t", "kernel_t", "shell_t", "fibre_t", "efb_t", "pome_m3", "oil_losses_t"] as const;

function MassBalanceView({ mb, oerFormula }: { mb: MassBalance; oerFormula: Schema<"Formula"> }) {
  const t = useT(messages);
  const { locale } = useLocale();
  return (
    <Section id="mass-balance" title={t.prod.massBalance} description={t.prod.massBalanceDesc} actions={<ProvenanceBadge provenance={mb.provenance} />}>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="relative overflow-x-auto" tabIndex={0} role="region" aria-label={t.prod.massBalance}>
          <table className="w-full text-xs">
            <caption className="sr-only">{t.prod.massBalance}</caption>
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th scope="col" className="py-1.5 pr-2 font-medium">{t.prod.stream}</th>
                <th scope="col" className="py-1.5 text-right font-medium">{t.prod.tonnes}</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-border/60 font-semibold">
                <th scope="row" className="py-1.5 pr-2 text-left">FFB</th>
                <td className="tabular py-1.5 text-right">{formatValue(mb.ffb_processed_t, "t", locale)}</td>
              </tr>
              {STREAMS.map((k) => (
                <tr key={k} className="border-b border-border/60">
                  <th scope="row" className="py-1.5 pr-2 text-left font-normal">{t.prod.streams[k]}</th>
                  <td className="tabular py-1.5 text-right">{formatValue(mb[k] ?? null, "t", locale)}</td>
                </tr>
              ))}
              {mb.closure_pct != null ? (
                <tr>
                  <th scope="row" className="py-1.5 pr-2 text-left font-normal text-muted-foreground">{t.prod.closure}</th>
                  <td className="tabular py-1.5 text-right">{formatValue(mb.closure_pct, "%", locale, { digits: 1 })}</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
        <FormulaPanel formulas={[oerFormula, ...mb.formulas]} title={t.prod.oerDef} />
      </div>
    </Section>
  );
}

function ProcessState() {
  const t = useT(messages);
  const { locale } = useLocale();
  const q = useApiQuery("/api/v1/production/process-state");
  return (
    <Section
      id="process-state"
      title={t.prod.processState}
      description={q.data ? t.prod.processStateDesc(formatDate(q.data.ts, locale, "datetime"), q.data.running ? t.prod.running : t.prod.stopped) : undefined}
      actions={
        <Button asChild variant="outline" size="sm">
          <Link href="/demo/palm-mill/process">
            {t.prod.toProcess} <ArrowRight aria-hidden />
          </Link>
        </Button>
      }
    >
      <QueryState query={q} compact isEmpty={(d) => d.variables.length === 0}>
        {(d) => (
          <div className="relative overflow-x-auto" tabIndex={0} role="region" aria-label={t.prod.processState}>
            <table className="w-full min-w-[34rem] text-xs">
              <caption className="sr-only">{t.prod.processState}</caption>
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th scope="col" className="py-1.5 pr-2 font-medium">{t.panel.variable}</th>
                  <th scope="col" className="py-1.5 pr-2 text-right font-medium">{t.panel.value}</th>
                  <th scope="col" className="py-1.5 pr-2 text-right font-medium">{t.panel.normal}</th>
                  <th scope="col" className="py-1.5 pr-2 font-medium">{t.panel.state}</th>
                  <th scope="col" className="py-1.5 font-medium">{t.prod.trend24}</th>
                </tr>
              </thead>
              <tbody>
                {d.variables.map((v) => (
                  <tr key={v.key} className="border-b border-border/60">
                    <th scope="row" className="py-1.5 pr-2 text-left font-normal">
                      <ApiText>{v.label}</ApiText>
                    </th>
                    <td className="tabular py-1.5 pr-2 text-right">
                      <span className="inline-flex items-center gap-1">
                        {formatValue(v.value.value, v.value.unit, locale)}
                        <ProvenanceBadge provenance={v.value.provenance} compact />
                      </span>
                    </td>
                    <td className="tabular py-1.5 pr-2 text-right" title={v.normal_range?.basis}>
                      {v.normal_range ? `${formatNumber(v.normal_range.low ?? null, locale)} – ${formatNumber(v.normal_range.high ?? null, locale)}` : "—"}
                    </td>
                    <td className={cn("py-1.5 pr-2", v.status === "critical" ? "font-semibold text-critical-fg" : v.status === "warning" ? "font-semibold text-warning-fg" : "text-muted-foreground")}>
                      {(t.panel.statusWord as Readonly<Record<string, string>>)[v.status] ?? v.status}
                    </td>
                    <td className="py-1.5">
                      <Sparkline points={v.trend_24h.map((y, i) => ({ t: String(i), v: y }))} width={80} height={22} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </QueryState>
      {q.data?.note ? (
        <p className="text-2xs text-muted-foreground">
          <ApiText>{q.data.note}</ApiText>
        </p>
      ) : null}
    </Section>
  );
}

/** Palm Mill production overview (DML-043/044): summary KPIs, mass balance + OER definition, process state, OER band. */
export function ProductionOverview() {
  const t = useT(messages);
  const label = useKpiLabel();
  const { locale } = useLocale();
  const { period } = useDemo();
  const summary = useApiQuery("/api/v1/production/summary");
  const trend = useApiQuery("/api/v1/production/oer-trend", { params: { query: { period: period === "today" ? "7d" : period, granularity: "day" } } });

  return (
    <OperationsLayout route="/demo/palm-mill">
      {summary.isPending ? (
        <LoadingState lines={4} />
      ) : summary.isError ? (
        <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />
      ) : (
        <>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-sm font-semibold">{t.prod.kpisTitle(formatDate(summary.data.business_date, locale))}</h2>
            {summary.data.window_start ? (
              <p className="text-2xs text-muted-foreground">
                {t.prod.window(formatDate(summary.data.window_start, locale, "datetime"), formatDate(summary.data.window_end ?? null, locale, "datetime"))}
              </p>
            ) : null}
          </div>
          <section aria-label={t.prod.kpisTitle(summary.data.business_date)} className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5">
            {summary.data.kpis.map((k) => (
              <KpiCard key={k.key} kpi={k} label={label(k.key, k.label)} digits={k.unit === "%" ? 2 : undefined} />
            ))}
          </section>
          <MassBalanceView mb={summary.data.mass_balance} oerFormula={summary.data.oer_formula} />
        </>
      )}
      <Section
        id="oer-trend"
        title={t.prod.oerTrend}
        description={t.prod.oerTrendDesc}
        actions={
          <Button asChild variant="outline" size="sm">
            <Link href="/demo/palm-mill/analytics">
              {t.prod.toAnalytics} <ArrowRight aria-hidden />
            </Link>
          </Button>
        }
      >
        <TimeSeriesChart
          title={t.analytics.oerBand}
          series={trend.data ? oerChartSeries(trend.data, t.analytics.bandLower, t.analytics.bandUpper) : undefined}
          loading={trend.isPending}
          error={trend.error}
          onRetry={() => void trend.refetch()}
          timeStyle="date"
          actions={trend.data ? <ProvenanceBadge provenance={trend.data.oer.provenance} /> : null}
        />
        {trend.data?.note ? (
          <p className="text-2xs text-muted-foreground">
            <ApiText>{trend.data.note}</ApiText>
          </p>
        ) : null}
      </Section>
      <ProcessState />
    </OperationsLayout>
  );
}
