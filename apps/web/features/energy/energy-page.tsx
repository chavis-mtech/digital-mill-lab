"use client";

import { useMemo, useState } from "react";
import { Calculator } from "lucide-react";
import { OperationsLayout } from "@/components/layouts/layouts";
import { useApiMutation, useApiQuery } from "@/lib/api/hooks";
import { useDemo } from "@/lib/demo/context";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatDate, formatNumber, formatValue } from "@/lib/format";
import { KpiCard } from "@/components/data/kpi-card";
import { EvidencePanel } from "@/components/data/evidence-panel";
import { FormulaPanel } from "@/components/data/formula-panel";
import { ProvenanceBadge } from "@/components/demo/provenance-badge";
import { Disclaimer } from "@/components/demo/disclaimer";
import { AreaBandChart, BarChart, TimeSeriesChart } from "@/components/charts/charts";
import { ErrorState, QueryState } from "@/components/states/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { ApiText, Field, NativeInput, NativeSelect, OpsSeverityPill, Section, StatTile } from "@/features/maintenance/shared/ops-ui";
import { ModelMetrics } from "@/features/maintenance/shared/model-metrics";
import { toEnergyMarkers } from "./helpers";
import messages from "./energy.i18n";

const METRICS = ["kwh_per_t_ffb", "electricity_kwh", "steam_t", "water_m3", "cost_thb", "grid_import_kwh", "idle_kwh"] as const;
type Metric = (typeof METRICS)[number];

export function EnergyPage() {
  const t = useT(messages);
  return (
    <OperationsLayout route="/demo/energy">
      <SummarySection />
      <TrendSection />
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <ForecastSection />
        <MlAnomalySection />
      </div>
      <WhatIfSection />
      <Disclaimer kind="synthetic" />
      <p className="sr-only">{t.noEnv}</p>
    </OperationsLayout>
  );
}

function SummarySection() {
  const t = useT(messages);
  const { locale } = useLocale();
  const { period } = useDemo();
  const q = useApiQuery("/api/v1/energy/summary", { params: { query: { period } } });
  const labels = t.kpiLabel as Record<string, string>;
  const fuelLabels = t.fuelLabel as Record<string, string>;
  return (
    <Section title={t.kpisTitle} description={t.kpisDesc} id="energy-kpis" data-tour="energy-kpis">
      <QueryState query={q}>
        {(d) => (
          <div className="flex flex-col gap-5">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5">
              {d.kpis.map((k) => (
                <KpiCard key={k.key} kpi={k} label={labels[k.key] ?? k.label} />
              ))}
            </div>
            {d.method ? (
              <p className="text-2xs text-muted-foreground">
                {t.method}: <ApiText>{d.method}</ApiText>
              </p>
            ) : null}
            <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
              <div className="flex min-w-0 flex-col gap-3 rounded-lg border border-border p-3">
                <h3 className="text-sm font-semibold">{t.sourceTitle}</h3>
                <p className="text-xs text-muted-foreground">{t.sourceDesc}</p>
                <BarChart
                  title={t.sourceTitle}
                  categories={(d.sources ?? []).map((s) => s.label)}
                  series={[{ key: "kwh", label: t.colKwh, values: (d.sources ?? []).map((s) => s.kwh), kind: d.provenance.kind }]}
                  unit="kWh"
                  horizontal
                  height={160}
                />
                <ul className="flex flex-wrap gap-2 text-xs">
                  {(d.sources ?? []).map((s) => (
                    <li key={s.key} className="rounded-lg border border-border px-2.5 py-1.5">
                      <span lang="en">{s.label}</span>: <b className="tabular">{formatNumber(s.kwh, locale)} kWh</b> ({formatNumber(s.share_pct, locale, { digits: 1 })}%) <ProvenanceBadge provenance={d.provenance} compact />
                    </li>
                  ))}
                </ul>
              </div>
              <div className="flex min-w-0 flex-col gap-3 rounded-lg border border-border p-3">
                <h3 className="text-sm font-semibold">{t.stageTitle}</h3>
                <BarChart
                  title={t.stageTitle}
                  categories={d.by_stage.map((s) => s.label)}
                  series={[{ key: "kwh", label: t.colKwh, values: d.by_stage.map((s) => s.kwh), kind: d.provenance.kind }]}
                  unit="kWh"
                  horizontal
                  height={300}
                />
              </div>
            </div>
            {d.fuels && d.fuels.length > 0 ? (
              <div>
                <h3 className="mb-2 text-sm font-semibold">{t.fuelTitle}</h3>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {d.fuels.map((f) => (
                    <StatTile key={f.key} label={fuelLabels[f.key] ?? f.label} value={formatNumber(f.value, locale)} unit={f.unit} foot={<ProvenanceBadge provenance={f.provenance} />} />
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        )}
      </QueryState>
    </Section>
  );
}

function TrendSection() {
  const t = useT(messages);
  const { locale } = useLocale();
  const [metric, setMetric] = useState<Metric>("kwh_per_t_ffb");
  const [range, setRange] = useState<"7d" | "30d">("30d");
  const q = useApiQuery("/api/v1/energy/series", { params: { query: { metric, period: range, granularity: "day" } } });
  const metricLabels = t.metrics as Record<string, string>;
  return (
    <Section
      title={t.trendTitle}
      description={t.trendDesc}
      id="energy-trend"
      actions={
        <>
          <label className="flex items-center gap-1.5 text-xs">
            <span className="text-muted-foreground">{t.metric}</span>
            <NativeSelect value={metric} onChange={(e) => setMetric(e.target.value as Metric)} className="h-8 w-auto text-[0.8125rem]">
              {METRICS.map((m) => (
                <option key={m} value={m}>
                  {metricLabels[m]}
                </option>
              ))}
            </NativeSelect>
          </label>
          <ToggleGroup type="single" value={range} onValueChange={(v) => v && setRange(v as "7d" | "30d")} aria-label={t.range}>
            <ToggleGroupItem value="7d" className="px-2.5 text-xs">
              {t.d7}
            </ToggleGroupItem>
            <ToggleGroupItem value="30d" className="px-2.5 text-xs">
              {t.d30}
            </ToggleGroupItem>
          </ToggleGroup>
        </>
      }
    >
      <QueryState query={q}>
        {(d) => {
          const abnormal = (d.markers ?? []).filter((m) => m.abnormal);
          return (
            <div className="flex flex-col gap-4">
              <TimeSeriesChart title={metricLabels[metric] ?? metric} series={d.series} anomalies={toEnergyMarkers(d.markers, d.series[0]?.points)} height={260} timeStyle="date" actions={d.series[0] ? <ProvenanceBadge provenance={d.series[0].provenance} /> : undefined} />
              <div>
                <h3 className="text-sm font-semibold">{t.abnormalTitle}</h3>
                <p className="mb-2 text-xs text-muted-foreground">{t.abnormalDesc}</p>
                {abnormal.length === 0 ? (
                  <p className="text-xs text-muted-foreground">{t.abnormalNone}</p>
                ) : (
                  <div className="relative overflow-x-auto rounded-lg border border-border" tabIndex={0} role="region" aria-label={t.abnormalTitle}>
                    <table className="tabular w-full border-collapse text-left text-xs">
                      <caption className="sr-only">{t.abnormalTitle}</caption>
                      <thead className="bg-surface-2 text-muted-foreground">
                        <tr>
                          {[t.colDay, t.colActual, t.colExpected, t.colZ, t.colFfb, t.colHours, t.colSeverity, t.colBasis].map((h) => (
                            <th key={h} scope="col" className="border-b border-border px-2.5 py-2 font-semibold whitespace-nowrap">
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {abnormal.map((m) => (
                          <tr key={m.t} className="border-b border-border last:border-0 align-top">
                            <th scope="row" className="px-2.5 py-2 text-left font-medium whitespace-nowrap">
                              {formatDate(m.t, locale, "date")}
                            </th>
                            <td className="px-2.5 py-2 font-semibold">{formatNumber(m.actual_kwh, locale)}</td>
                            <td className="px-2.5 py-2">{formatNumber(m.expected_kwh, locale)}</td>
                            <td className="px-2.5 py-2">{formatNumber(m.z_score, locale, { digits: 2 })}</td>
                            <td className="px-2.5 py-2">{formatNumber(m.ffb_processed_t, locale, { digits: 1 })}</td>
                            <td className="px-2.5 py-2">{m.hours}</td>
                            <td className="px-2.5 py-2">{m.severity === "low" || m.severity === "medium" || m.severity === "high" || m.severity === "critical" ? <OpsSeverityPill severity={m.severity} /> : "—"}</td>
                            <td className="min-w-56 px-2.5 py-2 text-muted-foreground" lang="en">
                              {m.basis}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          );
        }}
      </QueryState>
    </Section>
  );
}

function ForecastSection() {
  const t = useT(messages);
  const q = useApiQuery("/api/v1/ai/energy/forecast", { params: { query: { horizon_h: 48 } } });
  return (
    <Section title={t.forecastTitle} description={t.forecastDesc} id="energy-forecast">
      <QueryState query={q}>
        {(d) => (
          <div className="flex flex-col gap-3">
            <AreaBandChart title={t.forecastChart} band={d.forecast} actual={d.actual} baseline={d.baseline ?? undefined} height={260} actions={<ProvenanceBadge provenance={d.forecast.provenance} />} />
            {d.forecast.interval ? (
              <p className="text-2xs text-muted-foreground" lang="en">
                {d.forecast.interval}
              </p>
            ) : null}
            <ModelMetrics model={d.model} />
          </div>
        )}
      </QueryState>
    </Section>
  );
}

function MlAnomalySection() {
  const t = useT(messages);
  const { locale } = useLocale();
  const q = useApiQuery("/api/v1/ai/energy/anomalies", { params: { query: { period: "30d" } } });
  return (
    <Section title={t.mlAnomalyTitle} description={t.abnormalDesc} id="energy-ml-anomalies">
      <QueryState query={q} isEmpty={(d) => d.items.length === 0} empty={<p className="text-xs text-muted-foreground">{t.mlAnomalyNone}</p>} compact>
        {(d) => (
          <ul className="flex flex-col gap-3">
            {d.items.map((a) => (
              <li key={a.id} className="flex flex-col gap-2 rounded-lg border border-border p-3">
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="font-mono font-semibold">{a.code}</span>
                  <OpsSeverityPill severity={a.severity} />
                  <ProvenanceBadge kind="synthetic_actual" />
                  <span className="tabular text-muted-foreground">{formatDate(a.peak_ts ?? a.start_ts, locale, "datetime")}</span>
                  <Badge tone="outline">{a.status}</Badge>
                </div>
                <EvidencePanel evidence={a.evidence} factors={a.contributing_factors} />
              </li>
            ))}
          </ul>
        )}
      </QueryState>
    </Section>
  );
}

function WhatIfSection() {
  const t = useT(messages);
  const { locale } = useLocale();
  const [eff, setEff] = useState("5");
  const [idle, setIdle] = useState("10");
  const [grid, setGrid] = useState("0");
  const [tariff, setTariff] = useState("");
  const [biogas, setBiogas] = useState(false);
  const [days, setDays] = useState("30");
  const run = useApiMutation("/api/v1/energy/what-if");
  const n = { eff: Number(eff), idle: Number(idle), grid: Number(grid), days: Number(days), tariff: tariff.trim() === "" ? null : Number(tariff) };
  const valid =
    Number.isFinite(n.eff) && n.eff >= 0 && n.eff <= 50 &&
    Number.isFinite(n.idle) && n.idle >= 0 && n.idle <= 100 &&
    Number.isFinite(n.grid) && n.grid >= 0 && n.grid <= 100 &&
    Number.isInteger(n.days) && n.days >= 1 && n.days <= 366 &&
    (n.tariff === null || (Number.isFinite(n.tariff) && n.tariff >= 0));
  const r = run.data;
  const stats = useMemo(
    () =>
      r
        ? ([
            [t.wiBaseline, r.baseline_kwh, "kWh"],
            [t.wiScenario, r.scenario_kwh, "kWh"],
            [t.wiSaving, r.saving_kwh, "kWh"],
            [t.wiSavingThb, r.saving_thb, "THB"],
            [t.wiPerTBefore, r.kwh_per_t_before, "kWh/t"],
            [t.wiPerTAfter, r.kwh_per_t_after, "kWh/t"],
            [t.wiGridBefore, r.grid_import_before_kwh ?? null, "kWh"],
            [t.wiGridAfter, r.grid_import_after_kwh ?? null, "kWh"],
            [t.wiBiogas2, r.biogas_kwh ?? null, "kWh"],
          ] as const)
        : [],
    [r, t],
  );
  return (
    <Section title={t.whatIfTitle} description={t.whatIfDesc} id="energy-what-if" data-tour="energy-what-if">
      <form
        className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-[repeat(5,minmax(0,1fr))_auto_auto] xl:items-end"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid)
            run.mutate({
              body: { efficiency_improvement_pct: n.eff, idle_reduction_pct: n.idle, grid_import_reduction_pct: n.grid, electricity_tariff_thb_per_kwh: n.tariff, biogas_capture: biogas, days: n.days },
            });
        }}
      >
        <Field label={t.wiEfficiency}>{(id) => <NativeInput id={id} type="number" min={0} max={50} step={0.5} value={eff} onChange={(e) => setEff(e.target.value)} />}</Field>
        <Field label={t.wiIdle}>{(id) => <NativeInput id={id} type="number" min={0} max={100} step={1} value={idle} onChange={(e) => setIdle(e.target.value)} />}</Field>
        <Field label={t.wiGrid}>{(id) => <NativeInput id={id} type="number" min={0} max={100} step={1} value={grid} onChange={(e) => setGrid(e.target.value)} />}</Field>
        <Field label={t.wiTariff}>{(id) => <NativeInput id={id} type="number" min={0} step={0.1} value={tariff} onChange={(e) => setTariff(e.target.value)} />}</Field>
        <Field label={t.wiDays}>{(id) => <NativeInput id={id} type="number" min={1} max={366} value={days} onChange={(e) => setDays(e.target.value)} />}</Field>
        <label className="flex h-9 items-center gap-1.5 text-xs">
          <input type="checkbox" checked={biogas} onChange={(e) => setBiogas(e.target.checked)} className="size-3.5 accent-[var(--accent)]" />
          {t.wiBiogas}
        </label>
        <Button type="submit" variant="accent" disabled={!valid || run.isPending}>
          <Calculator aria-hidden /> {t.wiRun}
        </Button>
      </form>
      {run.isError ? <ErrorState error={run.error} compact /> : null}
      {!r && !run.isError ? <p className="text-xs text-muted-foreground">{t.wiEmpty}</p> : null}
      {r ? (
        <div className="flex flex-col gap-4" aria-live="polite">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-5">
            {stats.map(([label, v, unit]) => (
              <StatTile key={label} label={label} value={formatNumber(v, locale, { digits: unit === "kWh/t" ? 2 : undefined })} unit={unit} foot={<ProvenanceBadge provenance={r.provenance} />} />
            ))}
          </div>
          <Disclaimer kind="roi" variant="block" />
          <p role="note" className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-xs font-medium">
            {t.noEnv}
          </p>
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <FormulaPanel formulas={r.formulas} title={t.wiFormulas} />
            <div className="flex flex-col gap-4">
              <EvidencePanel assumptions={r.assumptions} title={t.wiAssumptions} />
              <section className="rounded-xl border border-border bg-surface p-4" aria-label={t.wiLimits}>
                <h3 className="mb-1.5 text-sm font-semibold">{t.wiLimits}</h3>
                <ul className="list-disc pl-5 text-xs text-muted-foreground">
                  {r.limits.map((l) => (
                    <li key={l} lang="en">
                      {l}
                    </li>
                  ))}
                </ul>
              </section>
            </div>
          </div>
        </div>
      ) : null}
      <p className="sr-only">{formatValue(0, "kWh", locale)}</p>
    </Section>
  );
}
