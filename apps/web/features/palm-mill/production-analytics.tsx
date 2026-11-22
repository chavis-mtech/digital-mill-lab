"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Sparkles } from "lucide-react";
import type { Schema } from "@dml/contracts";
import { useApiQuery } from "@/lib/api/hooks";
import { useDemo } from "@/lib/demo/context";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatDate, formatNumber, formatValue } from "@/lib/format";
import { cn } from "@/lib/utils";
import { OperationsLayout } from "@/components/layouts/layouts";
import { Badge } from "@/components/ui/badge";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { ProvenanceBadge } from "@/components/demo/provenance-badge";
import { BarChart, TimeSeriesChart } from "@/components/charts/charts";
import { DataTable, type DataTableColumn } from "@/components/data/data-table";
import { QueryState } from "@/components/states/states";
import { ApiText, Section } from "@/features/executive/shared/section";
import messages from "./palm-mill.i18n";
import { oerChartSeries } from "./oer-band";

type Gran = "hour" | "shift" | "day";
type Shift = Schema<"ShiftOut">;
type Batch = Schema<"BatchOut">;
type QualityParam = Schema<"QualityParameter">;

/** Over / within / no limit — the comparison is a display check of the API's latest value against the API's limit. */
export function limitState(p: { latest: { value: number | null }; limit?: { low?: number | null; high?: number | null } | null }): "over" | "within" | "none" {
  const v = p.latest.value;
  if (!p.limit || v == null || (p.limit.low == null && p.limit.high == null)) return "none";
  if ((p.limit.high != null && v > p.limit.high) || (p.limit.low != null && v < p.limit.low)) return "over";
  return "within";
}

function OerSection() {
  const t = useT(messages);
  const { period } = useDemo();
  const [gran, setGran] = useState<Gran>(period === "today" ? "hour" : "day");
  const effPeriod = gran === "day" && period === "today" ? "30d" : gran === "shift" && period === "today" ? "7d" : period;
  const q = useApiQuery("/api/v1/production/oer-trend", { params: { query: { period: effPeriod, granularity: gran } } });
  const ts = gran === "day" ? "date" : "datetime";
  return (
    <Section
      id="oer"
      title={t.analytics.oerBand}
      actions={
        <ToggleGroup type="single" value={gran} onValueChange={(v) => v && setGran(v as Gran)} aria-label={t.analytics.granularity}>
          <ToggleGroupItem value="hour">{t.analytics.hour}</ToggleGroupItem>
          <ToggleGroupItem value="shift">{t.analytics.shift}</ToggleGroupItem>
          <ToggleGroupItem value="day">{t.analytics.day}</ToggleGroupItem>
        </ToggleGroup>
      }
    >
      <TimeSeriesChart
        title={t.analytics.oerBand}
        description={t.prod.oerTrendDesc}
        series={q.data ? oerChartSeries(q.data, t.analytics.bandLower, t.analytics.bandUpper) : undefined}
        loading={q.isPending}
        error={q.error}
        onRetry={() => void q.refetch()}
        timeStyle={ts}
        actions={q.data ? <ProvenanceBadge provenance={q.data.oer.provenance} /> : null}
      />
      {q.data?.note ? (
        <p className="text-2xs text-muted-foreground">
          <ApiText>{q.data.note}</ApiText>
        </p>
      ) : null}
      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-2">
        <TimeSeriesChart title={t.analytics.ker} series={q.data?.ker ? [q.data.ker] : undefined} loading={q.isPending} error={q.error} empty={q.isSuccess && !q.data.ker} timeStyle={ts} height={200} />
        <TimeSeriesChart
          title={t.analytics.ripe}
          series={q.data?.ffb_ripe_pct ? [q.data.ffb_ripe_pct] : undefined}
          loading={q.isPending}
          error={q.error}
          empty={q.isSuccess && !q.data.ffb_ripe_pct}
          timeStyle={ts}
          height={200}
        />
      </div>
    </Section>
  );
}

function LossSection() {
  const t = useT(messages);
  const { locale } = useLocale();
  const { period } = useDemo();
  const q = useApiQuery("/api/v1/production/losses", { params: { query: { period } } });
  return (
    <Section
      id="losses"
      title={t.analytics.losses}
      description={q.data ? t.analytics.lossTotal(formatValue(q.data.total_loss_pct, "% FFB", locale), formatValue(q.data.benchmark_total_pct ?? null, "% FFB", locale)) : undefined}
      actions={q.data ? <ProvenanceBadge provenance={q.data.provenance} /> : null}
    >
      <QueryState query={q} compact isEmpty={(d) => d.components.length === 0}>
        {(d) => (
          <>
            <BarChart
              title={t.analytics.losses}
              unit="% FFB"
              height={240}
              categories={d.components.map((c) => c.label)}
              series={[
                { key: "actual", label: t.analytics.lossActual, values: d.components.map((c) => c.pct_of_ffb) },
                { key: "bench", label: t.analytics.lossBench, values: d.components.map((c) => c.benchmark_pct ?? null) },
              ]}
            />
            <ul className="grid grid-cols-1 gap-2 text-xs sm:grid-cols-2 xl:grid-cols-5">
              {d.components.map((c) => (
                <li key={c.key} className="rounded-md bg-surface-2 p-2">
                  <p className="text-muted-foreground">
                    <ApiText>{c.label}</ApiText>
                  </p>
                  <p className="tabular font-semibold">
                    {t.analytics.lostCpo} {formatValue(c.lost_cpo_t ?? null, "t", locale)}
                  </p>
                </li>
              ))}
            </ul>
            <TimeSeriesChart title={t.analytics.lossSeries} series={d.series} timeStyle="date" height={220} />
            {d.note ? (
              <p className="text-2xs text-muted-foreground">
                <ApiText>{d.note}</ApiText>
              </p>
            ) : null}
          </>
        )}
      </QueryState>
    </Section>
  );
}

function QualitySection() {
  const t = useT(messages);
  const { locale } = useLocale();
  const { period } = useDemo();
  const q = useApiQuery("/api/v1/production/quality", { params: { query: { period } } });
  return (
    <Section id="quality" title={t.analytics.quality}>
      <QueryState query={q} compact isEmpty={(d) => d.parameters.length === 0}>
        {(d) => (
          <div className="relative overflow-x-auto" tabIndex={0} role="region" aria-label={t.analytics.quality}>
            <table className="w-full min-w-[34rem] text-xs">
              <caption className="sr-only">{t.analytics.quality}</caption>
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th scope="col" className="py-1.5 pr-2 font-medium">{t.analytics.samplePoint}</th>
                  <th scope="col" className="py-1.5 pr-2 font-medium">{t.analytics.parameter}</th>
                  <th scope="col" className="py-1.5 pr-2 text-right font-medium">{t.analytics.latest}</th>
                  <th scope="col" className="py-1.5 pr-2 text-right font-medium">{t.analytics.limit}</th>
                  <th scope="col" className="py-1.5 font-medium">{t.panel.state}</th>
                </tr>
              </thead>
              <tbody>
                {d.parameters.map((p: QualityParam) => {
                  const st = limitState(p);
                  return (
                    <tr key={`${p.sample_point}-${p.parameter}`} className="border-b border-border/60">
                      <td className="py-1.5 pr-2 font-mono text-2xs">{p.sample_point}</td>
                      <th scope="row" className="py-1.5 pr-2 text-left font-normal">{p.parameter}</th>
                      <td className="tabular py-1.5 pr-2 text-right">
                        <span className="inline-flex items-center gap-1">
                          {formatValue(p.latest.value, p.latest.unit, locale)} <ProvenanceBadge provenance={p.latest.provenance} compact />
                        </span>
                      </td>
                      <td className="tabular py-1.5 pr-2 text-right" title={p.limit?.basis}>
                        {p.limit ? `${p.limit.low != null ? `≥ ${formatNumber(p.limit.low, locale)} ` : ""}${p.limit.high != null ? `≤ ${formatNumber(p.limit.high, locale)}` : ""}` : "—"}
                      </td>
                      <td className="py-1.5">
                        <Badge tone={st === "over" ? "warning" : st === "within" ? "success" : "outline"}>
                          {st === "over" ? t.analytics.overLimit : st === "within" ? t.analytics.withinLimit : t.analytics.noLimit}
                        </Badge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </QueryState>
    </Section>
  );
}

function ShiftSection() {
  const t = useT(messages);
  const { locale } = useLocale();
  const { period } = useDemo();
  const q = useApiQuery("/api/v1/production/shifts", { params: { query: { period: period === "today" ? "7d" : period } } });
  const cols = useMemo<DataTableColumn<Shift>[]>(
    () => [
      { id: "date", header: t.analytics.date, value: (r) => r.business_date, cell: (r) => formatDate(r.business_date, locale) },
      { id: "shift", header: t.analytics.shiftCol, value: (r) => r.shift_code },
      { id: "ffb", header: t.analytics.ffb, value: (r) => r.ffb_processed_t, cell: (r) => formatNumber(r.ffb_processed_t, locale, { digits: 1 }), align: "right" },
      { id: "cpo", header: t.analytics.cpo, value: (r) => r.cpo_t, cell: (r) => formatNumber(r.cpo_t, locale, { digits: 1 }), align: "right" },
      { id: "oer", header: t.analytics.oer, value: (r) => r.oer_pct, cell: (r) => formatNumber(r.oer_pct, locale, { digits: 2 }), align: "right" },
      { id: "ker", header: t.analytics.ker2, value: (r) => r.ker_pct, cell: (r) => formatNumber(r.ker_pct, locale, { digits: 2 }), align: "right" },
      { id: "hours", header: t.analytics.hours, value: (r) => r.operating_hours, cell: (r) => formatNumber(r.operating_hours, locale, { digits: 1 }), align: "right" },
      { id: "down", header: t.analytics.downtime, value: (r) => r.downtime_min, cell: (r) => formatNumber(r.downtime_min, locale, { digits: 0 }), align: "right" },
    ],
    [t, locale],
  );
  return (
    <Section id="shifts" title={t.analytics.shifts} actions={q.data?.items[0] ? <ProvenanceBadge provenance={q.data.items[0].provenance} /> : null}>
      <div className="relative min-w-0 overflow-hidden">
        <DataTable data={q.data?.items} loading={q.isPending} error={q.error} columns={cols} caption={t.analytics.shifts} exportName="shifts" pageSize={8} />
      </div>
      {q.data?.note ? (
        <p className="text-2xs text-muted-foreground">
          <ApiText>{q.data.note}</ApiText>
        </p>
      ) : null}
    </Section>
  );
}

function BatchSection() {
  const t = useT(messages);
  const { locale } = useLocale();
  const { period } = useDemo();
  const q = useApiQuery("/api/v1/production/batches", { params: { query: { period, limit: 100 } } });
  const cols = useMemo<DataTableColumn<Batch>[]>(
    () => [
      { id: "code", header: t.analytics.batch, value: (r) => r.code, cell: (r) => <span className="font-mono text-2xs">{r.code}</span> },
      { id: "start", header: t.analytics.start, value: (r) => r.start_ts, cell: (r) => formatDate(r.start_ts, locale, "datetime") },
      { id: "ffb", header: t.analytics.ffb, value: (r) => r.ffb_input_t, cell: (r) => formatNumber(r.ffb_input_t, locale, { digits: 1 }), align: "right" },
      { id: "cpo", header: t.analytics.cpo, value: (r) => r.cpo_t, cell: (r) => formatNumber(r.cpo_t, locale, { digits: 2 }), align: "right" },
      {
        id: "oer",
        header: t.analytics.oer,
        value: (r) => r.oer_pct,
        cell: (r) => <span className={cn("tabular")}>{formatNumber(r.oer_pct, locale, { digits: 2 })}</span>,
        align: "right",
      },
      { id: "sup", header: t.analytics.suppliers, value: (r) => r.supplier_count ?? null, align: "right" },
      { id: "trace", header: t.analytics.trace, value: (r) => r.trace_method },
    ],
    [t, locale],
  );
  return (
    <Section id="batches" title={t.analytics.batches}>
      <div className="relative min-w-0 overflow-hidden">
        <DataTable data={q.data?.items} loading={q.isPending} error={q.error} columns={cols} caption={t.analytics.batches} exportName="batches" pageSize={8} />
      </div>
    </Section>
  );
}

/** Production analytics (DML-045): OER vs expected band (hour/shift/day), KER, ripeness, losses, quality, shifts, batches. */
export function ProductionAnalytics() {
  const t = useT(messages);
  return (
    <OperationsLayout route="/demo/palm-mill/analytics">
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Sparkles className="size-3.5" aria-hidden />
        <Link href="/demo/palm-mill/ai-insights" className="text-accent-text underline underline-offset-2">
          {t.analytics.forecastLink}
        </Link>
      </p>
      <OerSection />
      <LossSection />
      <QualitySection />
      <div className="grid grid-cols-1 gap-5 2xl:grid-cols-2">
        <ShiftSection />
        <BatchSection />
      </div>
    </OperationsLayout>
  );
}
