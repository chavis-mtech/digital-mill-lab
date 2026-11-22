"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, ChevronDown, Info } from "lucide-react";
import type { Schema } from "@dml/contracts";
import { useApiQuery } from "@/lib/api/hooks";
import { useDemo } from "@/lib/demo/context";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatDate, formatNumber, formatSigned, formatValue } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { SeverityPill } from "./shared/sev";
import { ProvenanceBadge } from "@/components/demo/provenance-badge";
import { Disclaimer } from "@/components/demo/disclaimer";
import { EvidencePanel } from "@/components/data/evidence-panel";
import { FormulaPanel } from "@/features/executive/shared/formulas";
import { DataTable, type DataTableColumn } from "@/components/data/data-table";
import { BarChart, TimeSeriesChart } from "@/components/charts/charts";
import { EmptyState, QueryState } from "@/components/states/states";
import messages from "./executive.i18n";
import { alertHref, alertSourceKind, KPI_ORDER, stageHref, teamKey } from "./shared/links";
import { ApiText, Section } from "./shared/section";
import { AlertDetailDialog } from "./shared/alert-detail-dialog";
import { useKpiLabel, useScenarioLabel } from "./use-labels";

type Insight = Schema<"AiInsightSummaryResponse">;
type ImpactCard = Schema<"ImpactCard">;

// ─── AI insight summary ────────────────────────────────────────────────────────

export function InsightSummary({ insight }: { insight: Insight | null }) {
  const t = useT(messages);
  if (!insight) return <EmptyState compact title={t.insight.empty} />;
  return (
    <Section
      id="exec-insights"
      title={t.insight.title}
      description={t.insight.generatedBy(insight.generated_by)}
      actions={<ProvenanceBadge provenance={insight.provenance} />}
    >
      <p className="text-sm">
        <ApiText>{insight.summary}</ApiText>
      </p>
      {insight.items.length === 0 ? (
        <p className="text-xs text-muted-foreground">{t.insight.empty}</p>
      ) : (
        <ol className="flex flex-col gap-2">
          {insight.items.map((it, i) => (
            <li key={`${it.headline}-${i}`} className="rounded-lg border border-border p-3">
              <div className="flex items-start gap-2">
                <SeverityPill severity={it.severity} className="mt-0.5" />
                <div className="min-w-0 flex-1">
                  <p className="text-[0.8125rem] font-medium">
                    <ApiText>{it.headline}</ApiText>
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    <ApiText>{it.detail}</ApiText>
                  </p>
                  <dl className="mt-2 flex flex-col gap-0.5 text-xs [&_dd]:mb-1">
                    <dt className="text-muted-foreground">{t.insight.suggestedTeam}</dt>
                    <dd className="font-medium">{t.team[teamKey(it.suggested_team)]}</dd>
                    {it.suggested_decision ? (
                      <>
                        <dt className="text-muted-foreground">{t.insight.suggestedDecision}</dt>
                        <dd>
                          <ApiText>{it.suggested_decision}</ApiText>
                        </dd>
                      </>
                    ) : null}
                  </dl>
                  <details className="group mt-2">
                    <summary className="inline-flex cursor-pointer items-center gap-1 text-xs font-medium text-accent-text">
                      <ChevronDown className="size-3.5 transition-transform group-open:rotate-180" aria-hidden />
                      {t.insight.evidenceFor} ({it.evidence.length})
                    </summary>
                    <EvidencePanel evidence={it.evidence} className="mt-2" />
                  </details>
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}
      <p className="flex items-start gap-1.5 rounded-md bg-warning-soft/50 px-2.5 py-2 text-2xs text-warning-fg">
        <Info className="mt-0.5 size-3 shrink-0" aria-hidden />
        {t.insight.factorsNote}
      </p>
      {insight.method ? (
        <p className="text-2xs text-subtle-foreground">
          {t.insight.method}: <ApiText>{insight.method}</ApiText>
        </p>
      ) : null}
    </Section>
  );
}

// ─── Prioritised alerts ───────────────────────────────────────────────────────

export function AlertPriority() {
  const t = useT(messages);
  const { locale } = useLocale();
  const [open, setOpen] = useState<number | null>(null);
  const [all, setAll] = useState(false);
  const q = useApiQuery("/api/v1/alerts", { params: { query: { active_only: true, limit: 50 } } });
  return (
    <Section id="exec-alerts" title={t.alerts.title} description={t.alerts.notDiagnosis}>
      <details className="rounded-md bg-surface-2 px-2.5 py-1.5 text-2xs text-muted-foreground">
        <summary className="cursor-pointer font-medium text-foreground">{t.alerts.ranking}</summary>
        <p className="mt-1">{t.alerts.rankingBody}</p>
      </details>
      <QueryState query={q} compact isEmpty={(d) => d.items.length === 0} empty={<EmptyState compact title={t.alerts.empty} />}>
        {(d) => {
          const list = all ? d.items : d.items.slice(0, 5);
          return (
            <>
              <div className="flex flex-wrap gap-1.5" aria-label={t.alerts.counts}>
                {(["critical", "high", "medium", "low", "info"] as const)
                  .filter((s) => (d.counts_by_severity[s] ?? 0) > 0)
                  .map((s) => (
                    <span key={s} className="inline-flex items-center gap-1 text-2xs">
                      <SeverityPill severity={s} />
                      <span className="tabular font-semibold">{d.counts_by_severity[s]}</span>
                    </span>
                  ))}
              </div>
              <ol className="flex flex-col divide-y divide-border">
                {list.map((a, i) => (
                  <li key={a.id} className="flex items-start gap-2 py-2">
                    <span className="tabular mt-0.5 w-5 shrink-0 text-right text-2xs text-subtle-foreground">{i + 1}</span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <SeverityPill severity={a.severity} />
                        <Badge tone="outline">{alertSourceKind(a.source) === "rule" ? t.alerts.sourceRule : t.alerts.sourceMl}</Badge>
                        {a.priority_score != null ? (
                          <span className="tabular text-2xs text-muted-foreground" title={t.alerts.rankingBody}>
                            {t.alerts.score} {formatNumber(a.priority_score, locale, { digits: 1 })}
                          </span>
                        ) : null}
                      </div>
                      <button
                        type="button"
                        onClick={() => setOpen(a.id)}
                        className="mt-1 block text-left text-xs font-medium hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                      >
                        <ApiText>{a.title}</ApiText>
                      </button>
                      <p className="mt-0.5 text-2xs text-muted-foreground">
                        {t.team[teamKey(a.suggested_team)]} · {formatDate(a.raised_at, locale, "datetime")} ·{" "}
                        <Link href={alertHref(a)} className="text-accent-text underline underline-offset-2">
                          {t.alerts.openModule}
                        </Link>
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
              {d.items.length > 5 ? (
                <Button variant="ghost" size="xs" className="self-start" onClick={() => setAll((v) => !v)}>
                  {all ? t.alerts.showLess : t.alerts.viewAll(d.items.length)}
                </Button>
              ) : null}
            </>
          );
        }}
      </QueryState>
      <AlertDetailDialog alertId={open} onOpenChange={(v) => !v && setOpen(null)} />
    </Section>
  );
}

// ─── KPI trend (drill-down chart) ─────────────────────────────────────────────

export function KpiTrend() {
  const t = useT(messages);
  const label = useKpiLabel();
  const { period } = useDemo();
  const [metric, setMetric] = useState<string>("oer_pct");
  const [gran, setGran] = useState<"hour" | "day">(period === "today" ? "hour" : "day");
  const effPeriod = period === "today" && gran === "day" ? "30d" : period;
  const q = useApiQuery("/api/v1/executive/series", { params: { query: { metric, period: effPeriod, granularity: gran } } });
  return (
    <Section
      id="exec-trend"
      title={t.trend.title}
      actions={
        <>
          <Select value={metric} onValueChange={setMetric}>
            <SelectTrigger size="sm" className="w-56" aria-label={t.trend.metric}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {KPI_ORDER.map((k) => (
                <SelectItem key={k} value={k}>
                  {label(k, k)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <ToggleGroup type="single" value={gran} onValueChange={(v) => v && setGran(v as "hour" | "day")} aria-label={t.trend.granularity}>
            <ToggleGroupItem value="hour">{t.trend.hour}</ToggleGroupItem>
            <ToggleGroupItem value="day">{t.trend.day}</ToggleGroupItem>
          </ToggleGroup>
        </>
      }
    >
      <TimeSeriesChart
        title={label(metric, q.data?.series[0]?.label ?? metric)}
        series={q.data?.series}
        loading={q.isPending}
        error={q.error}
        onRetry={() => void q.refetch()}
        empty={q.isSuccess && q.data.series.every((s) => s.points.length === 0)}
        timeStyle={gran === "day" ? "date" : "datetime"}
        actions={q.data?.series[0] ? <ProvenanceBadge provenance={q.data.series[0].provenance} /> : null}
      />
    </Section>
  );
}

// ─── Bottlenecks ──────────────────────────────────────────────────────────────

export function Bottlenecks() {
  const t = useT(messages);
  const { locale } = useLocale();
  const { period } = useDemo();
  const q = useApiQuery("/api/v1/executive/bottlenecks", { params: { query: { period } } });
  return (
    <Section id="exec-bottlenecks" title={t.bottleneck.title} actions={q.data ? <ProvenanceBadge provenance={q.data.provenance} /> : null}>
      <QueryState query={q} compact isEmpty={(d) => d.stages.length === 0}>
        {(d) => (
          <>
            <BarChart
              title={t.bottleneck.utilisation}
              horizontal
              height={240}
              unit="%"
              categories={d.stages.map((s) => s.label)}
              series={[{ key: "util", label: t.bottleneck.utilisation, values: d.stages.map((s) => s.utilisation_pct) }]}
            />
            <ul className="flex flex-col gap-1.5">
              {d.stages
                .filter((s) => s.is_bottleneck)
                .map((s) => (
                  <li key={s.stage_code} className="flex flex-wrap items-start gap-2 rounded-md border border-warning/40 bg-warning-soft/40 p-2 text-xs">
                    <Badge tone="warning">{t.bottleneck.isBottleneck}</Badge>
                    <Link href={stageHref(s.stage_code)} className="font-medium hover:underline">
                      {s.label}
                    </Link>
                    <span className="tabular">{formatValue(s.utilisation_pct, "%", locale)}</span>
                    <span className="w-full text-2xs text-muted-foreground">
                      <ApiText>{s.reason}</ApiText>
                    </span>
                  </li>
                ))}
              {d.stages.every((s) => !s.is_bottleneck) ? <li className="text-xs text-muted-foreground">{t.bottleneck.none}</li> : null}
            </ul>
            {d.method ? (
              <p className="text-2xs text-subtle-foreground">
                {t.bottleneck.method}: <ApiText>{d.method}</ApiText>
              </p>
            ) : null}
          </>
        )}
      </QueryState>
    </Section>
  );
}

// ─── Cost & productivity ──────────────────────────────────────────────────────

type CostLine = Schema<"CostLine">;

export function CostProductivity() {
  const t = useT(messages);
  const label = useKpiLabel();
  const { locale } = useLocale();
  const { period } = useDemo();
  const q = useApiQuery("/api/v1/executive/cost-productivity", { params: { query: { period } } });
  const cols = useMemo<DataTableColumn<CostLine>[]>(
    () => [
      { id: "line", header: t.cost.line, value: (r) => r.label, cell: (r) => <ApiText>{r.label}</ApiText> },
      { id: "perT", header: t.cost.perT, value: (r) => r.thb_per_t_ffb, cell: (r) => formatNumber(r.thb_per_t_ffb, locale, { digits: 2 }), align: "right" },
      { id: "total", header: t.cost.total, value: (r) => r.total_thb, cell: (r) => formatNumber(r.total_thb, locale, { digits: 0 }), align: "right" },
      { id: "share", header: t.cost.share, value: (r) => r.share_pct, cell: (r) => formatValue(r.share_pct, "%", locale, { digits: 1 }), align: "right" },
    ],
    [t, locale],
  );
  return (
    <Section id="exec-cost" title={t.cost.title} actions={q.data ? <ProvenanceBadge provenance={q.data.provenance} /> : null}>
      <QueryState query={q} compact>
        {(d) => (
          <>
            <ul className="grid grid-cols-1 gap-2 min-[420px]:grid-cols-2 sm:grid-cols-3">
              {d.productivity.map((k) => (
                <li key={k.key} className="min-w-0 rounded-lg bg-surface-2 p-2.5">
                  <p className="text-2xs text-muted-foreground">{label(k.key, k.label)}</p>
                  <p className="tabular text-sm font-semibold">{formatValue(k.value, k.unit, locale)}</p>
                  <ProvenanceBadge provenance={k.provenance} compact />
                </li>
              ))}
            </ul>
            {/* overflow-hidden wrapper: the kit table's sr-only caption otherwise widens the page on phones */}
            <div className="relative min-w-0 overflow-hidden">
              <DataTable data={d.cost_lines} columns={cols} caption={t.cost.chart} exportName="cost-lines" pageSize={10} />
            </div>
            <p className="text-2xs text-muted-foreground">
              <ApiText>{d.note}</ApiText>
            </p>
            <Disclaimer kind="roi" />
          </>
        )}
      </QueryState>
    </Section>
  );
}

// ─── Scenario comparison ──────────────────────────────────────────────────────

export function ScenarioComparison() {
  const t = useT(messages);
  const label = useKpiLabel();
  const scen = useScenarioLabel();
  const { locale } = useLocale();
  const { scenarioId } = useDemo();
  const [metric, setMetric] = useState("oer_pct");
  const q = useApiQuery("/api/v1/executive/scenario-comparison");
  return (
    <Section id="exec-comparison" title={t.comparison.title}>
      <QueryState query={q} compact isEmpty={(d) => d.rows.length === 0}>
        {(d) => {
          const keys = d.rows[0]?.kpis.map((k) => ({ key: k.key, label: k.label })) ?? [];
          const values = d.rows.map((r) => r.kpis.find((k) => k.key === metric));
          const unit = values.find(Boolean)?.unit;
          return (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <Select value={metric} onValueChange={setMetric}>
                  <SelectTrigger size="sm" className="w-60" aria-label={t.comparison.choose}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {keys.map((k) => (
                      <SelectItem key={k.key} value={k.key}>
                        {label(k.key, k.label)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {values.find(Boolean) ? <ProvenanceBadge provenance={values.find(Boolean)!.provenance} /> : null}
              </div>
              <BarChart
                title={t.comparison.chartTitle(label(metric, metric))}
                horizontal
                height={240}
                unit={unit}
                categories={d.rows.map((r) => scen(r.scenario_code, r.label))}
                series={[{ key: metric, label: label(metric, metric), values: values.map((v) => v?.value ?? null) }]}
              />
              <div className="relative overflow-x-auto" tabIndex={0} role="region" aria-label={t.comparison.title}>
                <table className="w-full min-w-[28rem] text-xs">
                  <caption className="sr-only">{t.comparison.title}</caption>
                  <thead>
                    <tr className="border-b border-border text-left text-muted-foreground">
                      <th scope="col" className="py-1.5 pr-2 font-medium">{t.comparison.scenario}</th>
                      <th scope="col" className="py-1.5 pr-2 font-medium">{t.comparison.focusDay}</th>
                      <th scope="col" className="py-1.5 pr-2 text-right font-medium">{label(metric, metric)}</th>
                      <th scope="col" className="py-1.5 text-right font-medium">Δ {scen(d.baseline)}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.rows.map((r, i) => {
                      const v = values[i];
                      return (
                        <tr key={r.scenario_code} className={cn("border-b border-border/60", r.scenario_code === scenarioId && "bg-accent-soft/40")}>
                          <th scope="row" className="py-1.5 pr-2 text-left font-medium">
                            {scen(r.scenario_code, r.label)}
                            {r.scenario_code === scenarioId ? <span className="sr-only"> ({t.comparison.current})</span> : null}
                          </th>
                          <td className="py-1.5 pr-2">{r.focus_day ? formatDate(r.focus_day, locale) : "—"}</td>
                          <td className="tabular py-1.5 pr-2 text-right">{formatValue(v?.value ?? null, v?.unit, locale)}</td>
                          <td className="tabular py-1.5 text-right">{v?.delta != null ? formatSigned(v.delta, locale, 2) : "—"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              {d.note ? (
                <p className="text-2xs text-muted-foreground">
                  <ApiText>{d.note}</ApiText>
                </p>
              ) : null}
            </>
          );
        }}
      </QueryState>
    </Section>
  );
}

// ─── Business impact cards ────────────────────────────────────────────────────

function ImpactCardView({ card }: { card: ImpactCard }) {
  const t = useT(messages);
  const { locale } = useLocale();
  const [show, setShow] = useState(false);
  return (
    <li className="flex flex-col gap-2 rounded-lg border border-border p-3">
      <p className="text-xs text-muted-foreground">
        <ApiText>{card.label}</ApiText>
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <span className="tabular text-xl font-semibold">{formatValue(card.value, card.unit, locale)}</span>
        <ProvenanceBadge provenance={card.provenance} />
      </div>
      <code tabIndex={0} className="block overflow-x-auto rounded bg-surface-2 px-2 py-1 font-mono text-2xs whitespace-pre text-accent-text">{card.formula.expression}</code>
      <Button variant="ghost" size="xs" className="self-start" aria-expanded={show} onClick={() => setShow((v) => !v)}>
        {show ? t.impact.hideFormula : t.impact.showFormula}
      </Button>
      {show ? <FormulaPanel formulas={[card.formula]} /> : null}
    </li>
  );
}

export function ImpactCards({ cards }: { cards: ImpactCard[] }) {
  const t = useT(messages);
  return (
    <Section
      id="exec-impact"
      title={t.impact.title}
      description={t.impact.subtitle}
      actions={
        <Button asChild variant="outline" size="sm">
          <Link href="/demo/business-impact">
            {t.impact.toRoi} <ArrowRight aria-hidden />
          </Link>
        </Button>
      }
    >
      {cards.length === 0 ? (
        <EmptyState compact title={t.impact.empty} />
      ) : (
        <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
          {cards.map((c) => (
            <ImpactCardView key={c.key} card={c} />
          ))}
        </ul>
      )}
      <Disclaimer kind="roi" />
    </Section>
  );
}
