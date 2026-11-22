"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Calculator } from "lucide-react";
import { OperationsLayout } from "@/components/layouts/layouts";
import { useApiMutation, useApiQuery } from "@/lib/api/hooks";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatNumber, formatValue } from "@/lib/format";
import { AlertBadge } from "@/components/demo/severity";
import { ProvenanceBadge } from "@/components/demo/provenance-badge";
import { Disclaimer } from "@/components/demo/disclaimer";
import { EvidencePanel } from "@/components/data/evidence-panel";
import { FormulaPanel } from "@/components/data/formula-panel";
import { BarChart, TimeSeriesChart } from "@/components/charts/charts";
import { ErrorState, QueryState } from "@/components/states/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ApiText, Field, NativeInput, NativeSelect, Section, StatTile, TileSkeleton } from "./shared/ops-ui";
import { AnomalyEvidence, RecommendationCard, RiskNotice } from "./maintenance-parts";
import { pickRecommendations, sortByAttention, type HealthState } from "./helpers";
import messages from "./maintenance.i18n";

const TILE_STATES: { state: HealthState; key: "kpiCritical" | "kpiMaintReq" | "kpiWarning" | "kpiNormal" }[] = [
  { state: "critical", key: "kpiCritical" },
  { state: "maintenance_required", key: "kpiMaintReq" },
  { state: "warning", key: "kpiWarning" },
  { state: "normal", key: "kpiNormal" },
];

export function MaintenanceOverviewPage() {
  const t = useT(messages);
  const { locale } = useLocale();
  const eq = useApiQuery("/api/v1/maintenance/equipment");
  const recs = useApiQuery("/api/v1/maintenance/recommendations");
  const [showAllRecs, setShowAllRecs] = useState(false);

  const attention = useMemo(() => sortByAttention((eq.data?.items ?? []).filter((i) => i.health_state !== "normal")), [eq.data]);
  const picked = useMemo(() => pickRecommendations(recs.data?.items ?? []), [recs.data]);
  const visibleRecs = showAllRecs ? picked : picked.slice(0, 4);

  return (
    <OperationsLayout route="/demo/maintenance">
      <section aria-label={t.overview.kpiNote} className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        {eq.isPending
          ? Array.from({ length: 5 }, (_, i) => <TileSkeleton key={i} />)
          : eq.isError
            ? <div className="col-span-full"><ErrorState error={eq.error} onRetry={() => void eq.refetch()} compact /></div>
            : (
              <>
                <StatTile label={t.overview.kpiTotal} value={formatNumber(eq.data.total, locale)} foot={eq.data.provenance ? <ProvenanceBadge provenance={eq.data.provenance} /> : undefined} />
                {TILE_STATES.map(({ state, key }) => (
                  <StatTile key={state} label={t.overview[key]} value={formatNumber(eq.data.counts_by_state[state] ?? 0, locale)} foot={<><AlertBadge state={state} />{eq.data.provenance ? <ProvenanceBadge provenance={eq.data.provenance} compact /> : null}</>} />
                ))}
              </>
            )}
      </section>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <Section title={t.overview.recoTitle} description={t.overview.recoDesc} id="recommendations">
          <QueryState query={recs} isEmpty={() => picked.length === 0} empty={<p className="text-sm text-muted-foreground">{t.overview.recoNone}</p>}>
            {() => (
              <div className="flex flex-col gap-3">
                {visibleRecs.map((r, i) => (
                  <RecommendationCard key={r.id} rec={r} defaultOpen={i === 0} tour={i === 0 ? "maintenance-recommendation" : undefined} />
                ))}
                {picked.length > 4 ? (
                  <Button variant="outline" size="sm" className="self-start" onClick={() => setShowAllRecs((v) => !v)}>
                    {showAllRecs ? t.common.showLess : t.common.showAll(picked.length)}
                  </Button>
                ) : null}
              </div>
            )}
          </QueryState>
        </Section>

        <div className="flex min-w-0 flex-col gap-5">
          <Section title={t.overview.attentionTitle} description={t.overview.attentionDesc}>
            <QueryState query={eq} isEmpty={() => attention.length === 0} empty={<p className="text-sm text-muted-foreground">{t.overview.attentionNone}</p>} compact>
              {() => (
                <ul className="flex flex-col gap-2">
                  {attention.map((e) => (
                    <li key={e.id} className="rounded-lg border border-border p-3 text-xs">
                      <div className="flex flex-wrap items-center gap-2">
                        <Link href={`/demo/maintenance/equipment?equipment_id=${e.id}`} className="font-mono text-[0.8125rem] font-semibold text-accent-text hover:underline">
                          {e.code}
                        </Link>
                        <AlertBadge state={e.health_state} />
                        <span className="tabular ml-auto">
                          {t.common.risk}: <b>{formatNumber(e.risk_score ?? null, locale, { digits: 1 })}</b>
                        </span>
                      </div>
                      <p className="mt-1 text-muted-foreground" lang="en">
                        {e.name}
                      </p>
                      {e.triggered_by && e.triggered_by.length > 0 ? (
                        <ul className="mt-1 list-disc pl-4">
                          {e.triggered_by.map((x) => (
                            <li key={x} lang="en">
                              {x}
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </QueryState>
          </Section>
          <RiskRanking />
        </div>
      </div>

      <Section title={t.overview.anomalyTitle} description={t.overview.anomalyDesc} id="anomalies">
        <AnomalyEvidence />
      </Section>

      <DowntimeSection />
      <ImpactSection />
    </OperationsLayout>
  );
}

function RiskRanking() {
  const t = useT(messages);
  const { locale } = useLocale();
  const q = useApiQuery("/api/v1/ai/failure-risk", { params: { query: { limit: 6 } } });
  return (
    <Section title={t.overview.riskTitle} description={t.overview.riskDesc}>
      <RiskNotice />
      <QueryState query={q} isEmpty={(d) => d.items.length === 0} compact>
        {(d) => (
          <>
            <ol className="flex flex-col gap-1.5">
              {d.items.map((it) => (
                <li key={it.equipment.id} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-xs">
                  <span>
                    <span className="tabular mr-2 text-muted-foreground">#{it.rank}</span>
                    <Link href={`/demo/maintenance/equipment?equipment_id=${it.equipment.id}`} className="font-mono font-semibold text-accent-text hover:underline">
                      {it.equipment.code}
                    </Link>
                  </span>
                  <span className="flex items-center gap-2">
                    <b className="tabular">{formatNumber(it.risk_score, locale, { digits: 2 })}</b>
                    <ProvenanceBadge kind="forecast" compact />
                  </span>
                </li>
              ))}
            </ol>
            {d.meaning ? (
              <p lang="en" className="text-xs text-muted-foreground">
                {d.meaning}
              </p>
            ) : null}
            <details className="text-xs">
              <summary className="cursor-pointer text-accent-text">{t.overview.riskLimits}</summary>
              <ul className="mt-1 list-disc pl-5 text-muted-foreground">
                {d.limitations.map((l) => (
                  <li key={l} lang="en">
                    {l}
                  </li>
                ))}
              </ul>
              <p className="mt-1 font-mono text-2xs text-subtle-foreground">
                {t.overview.riskModel}: {d.model.name} {d.model.version} · {d.model.algorithm}
              </p>
            </details>
          </>
        )}
      </QueryState>
    </Section>
  );
}

function DowntimeSection() {
  const t = useT(messages);
  const { locale } = useLocale();
  const q = useApiQuery("/api/v1/maintenance/downtime", { params: { query: { period: "30d" } } });
  // Plant downtime is a DIFFERENT quantity (process_hourly): fetched from the executive KPIs, never derived here.
  const kpis = useApiQuery("/api/v1/executive/kpis", { params: { query: { period: "30d" } } });
  const plant = kpis.data?.kpis.find((k) => k.key === "plant_downtime_h");
  return (
    <Section title={t.overview.downtimeTitle} description={t.overview.downtimeDesc} id="downtime">
      <QueryState query={q}>
        {(d) => {
          const top = d.by_equipment.slice(0, 8);
          const hours = [...d.by_hour_of_day].sort((a, b) => Number(a.key) - Number(b.key));
          return (
            <div className="flex flex-col gap-5">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <StatTile
                  label={t.overview.downtimeTotal}
                  value={formatNumber(d.total_downtime_h, locale)}
                  unit={t.overview.downtimeUnit}
                  foot={
                    <>
                      <ProvenanceBadge provenance={d.provenance} />
                      <span className="basis-full text-2xs text-muted-foreground">{t.overview.downtimeEventNote}</span>
                    </>
                  }
                />
                {plant ? (
                  <StatTile
                    label={t.overview.downtimePlant}
                    value={formatNumber(plant.value, locale)}
                    unit={t.overview.downtimeUnit}
                    foot={
                      <>
                        <ProvenanceBadge provenance={plant.provenance} />
                        <span className="basis-full text-2xs text-muted-foreground">{t.overview.downtimePlantNote}</span>
                      </>
                    }
                  />
                ) : null}
                <StatTile label={t.overview.downtimeAvail} value={formatNumber(d.availability_pct, locale, { digits: 1 })} unit="%" foot={<ProvenanceBadge provenance={d.provenance} />} />
              </div>
              <p role="note" className="rounded-lg border border-warning/50 bg-warning-soft/50 px-3 py-2 text-xs font-medium text-foreground">
                {t.overview.downtimeNotSame}
              </p>
              <p className="text-2xs text-muted-foreground">{t.overview.downtimeSplitNote}</p>
              <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
                <BarChart title={t.overview.downtimeByEquipment} categories={top.map((b) => b.key)} series={[{ key: "h", label: t.overview.downtimeUnit, values: top.map((b) => b.downtime_h) }]} unit={t.overview.downtimeUnit} horizontal height={260} />
                <BarChart title={t.overview.downtimeByCause} categories={d.by_cause.slice(0, 8).map((b) => b.label)} series={[{ key: "h", label: t.overview.downtimeUnit, values: d.by_cause.slice(0, 8).map((b) => b.downtime_h) }]} unit={t.overview.downtimeUnit} horizontal height={260} />
                <BarChart title={t.overview.downtimeByHour} categories={hours.map((b) => b.label)} series={[{ key: "h", label: t.overview.downtimeUnit, values: hours.map((b) => b.downtime_h) }]} unit={t.overview.downtimeUnit} height={260} />
              </div>
              <TimeSeriesChart title={t.overview.downtimeSeries} series={[d.series]} height={220} timeStyle="date" />
            </div>
          );
        }}
      </QueryState>
    </Section>
  );
}

function ImpactSection() {
  const t = useT(messages);
  const { locale } = useLocale();
  const eq = useApiQuery("/api/v1/maintenance/equipment");
  const [equipmentId, setEquipmentId] = useState<number | null>(null);
  const [downtime, setDowntime] = useState("8");
  const [recovery, setRecovery] = useState("4");
  const [planned, setPlanned] = useState(false);
  const run = useApiMutation("/api/v1/maintenance/impact");

  const items = eq.data?.items;
  const effectiveId = equipmentId ?? (items ? (sortByAttention(items)[0]?.id ?? null) : null);
  const dt = Number(downtime);
  const rc = Number(recovery);
  const valid = effectiveId != null && Number.isFinite(dt) && dt > 0 && dt <= 720 && Number.isFinite(rc) && rc >= 0;
  const r = run.data;

  return (
    <Section title={t.overview.impactTitle} description={t.overview.impactDesc} id="impact" data-tour="maintenance-impact">
      <form
        className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-[minmax(0,2fr)_1fr_1fr_auto_auto] xl:items-end"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid) run.mutate({ body: { equipment_id: effectiveId, downtime_hours: dt, recovery_hours: rc, planned } });
        }}
      >
        <Field label={t.overview.impactEquipment}>
          {(id) => (
            <NativeSelect id={id} value={effectiveId ?? ""} onChange={(e) => setEquipmentId(Number(e.target.value) || null)}>
              {sortByAttention(items ?? []).map((e) => (
                <option key={e.id} value={e.id}>
                  {e.code} — {e.name} ({e.health_state})
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
        <Field label={t.overview.impactDowntime}>{(id) => <NativeInput id={id} type="number" min={0.5} max={720} step={0.5} value={downtime} onChange={(e) => setDowntime(e.target.value)} />}</Field>
        <Field label={t.overview.impactRecovery}>{(id) => <NativeInput id={id} type="number" min={0} max={720} step={0.5} value={recovery} onChange={(e) => setRecovery(e.target.value)} />}</Field>
        <label className="flex h-9 items-center gap-1.5 text-xs">
          <input type="checkbox" checked={planned} onChange={(e) => setPlanned(e.target.checked)} className="size-3.5 accent-[var(--accent)]" />
          {t.overview.impactPlanned}
        </label>
        <Button type="submit" variant="accent" disabled={!valid || run.isPending}>
          <Calculator aria-hidden /> {t.overview.impactRun}
        </Button>
      </form>

      {run.isError ? <ErrorState error={run.error} compact /> : null}
      {!r && !run.isError ? <p className="text-xs text-muted-foreground">{t.overview.impactEmpty}</p> : null}
      {r ? (
        <div className="flex flex-col gap-4" aria-live="polite">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            {(
              [
                [t.overview.impactLost, r.lost_ffb_processing_t, "t"],
                [t.overview.impactCpo, r.lost_cpo_opportunity_t, "t"],
                [t.overview.impactValue, r.lost_value_thb, "THB"],
                [t.overview.impactCost, r.maintenance_cost_thb, "THB"],
                [t.overview.impactTotal, r.total_impact_thb, "THB"],
              ] as const
            ).map(([label, v, unit]) => (
              <StatTile key={label} label={label} value={formatNumber(v, locale)} unit={unit} foot={<ProvenanceBadge provenance={r.provenance} />} />
            ))}
          </div>
          <Disclaimer kind="roi" variant="block" />
          <p className="text-xs">
            <span className="font-semibold">{t.overview.impactRecoveryScenario}: </span>
            <ApiText>{r.recovery_scenario}</ApiText>
          </p>
          {r.comparison && r.comparison.length > 0 ? (
            <div className="relative overflow-x-auto rounded-lg border border-border" tabIndex={0} role="region" aria-label={t.overview.impactCompare}>
              <table className="tabular w-full border-collapse text-left text-xs">
                <caption className="sr-only">{t.overview.impactCompare}</caption>
                <thead className="bg-surface-2 text-muted-foreground">
                  <tr>
                    {[t.overview.thScenario, t.overview.impactLost, t.overview.impactCpo, t.overview.impactValue, t.overview.impactCost, t.overview.impactTotal].map((h) => (
                      <th key={h} scope="col" className="border-b border-border px-2.5 py-2 font-semibold whitespace-nowrap">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {r.comparison.map((c) => (
                    <tr key={c.key} className="border-b border-border last:border-0 align-top">
                      <th scope="row" className="px-2.5 py-2 text-left font-medium" lang="en">
                        {c.label}
                        <span className="block font-normal text-muted-foreground">{c.description}</span>
                      </th>
                      <td className="px-2.5 py-2">{formatValue(c.lost_ffb_processing_t, "t", locale)}</td>
                      <td className="px-2.5 py-2">{formatValue(c.lost_cpo_opportunity_t, "t", locale)}</td>
                      <td className="px-2.5 py-2">{formatValue(c.lost_value_thb, "THB", locale)}</td>
                      <td className="px-2.5 py-2">{formatValue(c.maintenance_cost_thb, "THB", locale)}</td>
                      <td className="px-2.5 py-2 font-semibold">{formatValue(c.total_impact_thb, "THB", locale)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <FormulaPanel formulas={r.formulas} title={t.overview.impactFormulas} />
            <div className="flex flex-col gap-4">
              <EvidencePanel assumptions={r.assumptions} title={t.overview.impactAssumptions} />
              {r.required_real_data.length > 0 ? (
                <section className="rounded-xl border border-border bg-surface p-4" aria-label={t.overview.impactNeeded}>
                  <h3 className="mb-1.5 text-sm font-semibold">{t.overview.impactNeeded}</h3>
                  <ul className="list-disc pl-5 text-xs text-muted-foreground">
                    {r.required_real_data.map((x) => (
                      <li key={x} lang="en">
                        {x}
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
            </div>
          </div>
          {r.notice ? (
            <p lang="en" className="text-xs text-muted-foreground">
              <Badge tone="outline">{t.common.apiTextNote}</Badge> {r.notice}
            </p>
          ) : null}
        </div>
      ) : null}
    </Section>
  );
}
