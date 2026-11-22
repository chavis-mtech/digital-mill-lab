"use client";

import { useMemo, useState } from "react";
import { Play, TriangleAlert } from "lucide-react";
import type { Schema } from "@dml/contracts";
import { OperationsLayout } from "@/components/layouts/layouts";
import { useApiMutation, useApiQuery } from "@/lib/api/hooks";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatDate, formatNumber, formatValue } from "@/lib/format";
import { KpiCard } from "@/components/data/kpi-card";
import { DataTable, type DataTableColumn } from "@/components/data/data-table";
import { EvidencePanel } from "@/components/data/evidence-panel";
import { ProvenanceBadge } from "@/components/demo/provenance-badge";
import { Disclaimer } from "@/components/demo/disclaimer";
import { AreaBandChart, BarChart, HeatmapChart, TimeSeriesChart } from "@/components/charts/charts";
import { ErrorState, QueryState } from "@/components/states/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ApiText, Field, NativeInput, OpsSeverityPill, Section, StatTile } from "@/features/maintenance/shared/ops-ui";
import { ModelMetrics } from "@/features/maintenance/shared/model-metrics";
import messages from "./logistics.i18n";

type Ticket = Schema<"TicketOut">;
type Supplier = Schema<"SupplierOut">;
type Truck = Schema<"TruckInQueue">;

export function LogisticsPage() {
  const t = useT(messages);
  return (
    <OperationsLayout route="/demo/logistics">
      <KpiSection />
      <QueueSection />
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <PredictionSection />
        <ArrivalsSection />
      </div>
      <SimulationSection />
      <TicketsSection />
      <AnomaliesSection />
      <SuppliersSection />
      <p className="sr-only">{t.flagNote}</p>
    </OperationsLayout>
  );
}

function KpiSection() {
  const t = useT(messages);
  const q = useApiQuery("/api/v1/logistics/kpis", { params: { query: { period: "today" } } });
  const labels = t.kpiLabel as Record<string, string>;
  return (
    <Section title={t.kpisTitle} description={t.kpisDesc} id="logistics-kpis">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5">
        {q.isPending ? (
          Array.from({ length: 5 }, (_, i) => <KpiCard key={i} loading />)
        ) : q.isError ? (
          <div className="col-span-full">
            <ErrorState error={q.error} onRetry={() => void q.refetch()} compact />
          </div>
        ) : (
          q.data.kpis.map((k) => <KpiCard key={k.key} kpi={k} label={labels[k.key] ?? k.label} />)
        )}
      </div>
    </Section>
  );
}

function QueueSection() {
  const t = useT(messages);
  const { locale } = useLocale();
  const q = useApiQuery("/api/v1/logistics/queue");
  const stageLabel = t.stage as Record<string, string>;
  const columns = useMemo<DataTableColumn<Truck>[]>(
    () => [
      { id: "code", header: t.colTruck, value: (r) => r.code, cell: (r) => <span className="font-mono text-xs">{r.code}</span> },
      { id: "supplier", header: t.colSupplier, value: (r) => r.supplier_code },
      { id: "plate", header: t.colPlate, value: (r) => r.plate_masked, cell: (r) => <span className="font-mono text-xs">{r.plate_masked}</span> },
      { id: "status", header: t.colStatus, value: (r) => stageLabel[r.status] ?? r.status, cell: (r) => <Badge tone="outline">{stageLabel[r.status] ?? r.status}</Badge> },
      { id: "arrival", header: t.colArrival, value: (r) => r.arrival_ts, cell: (r) => <span className="whitespace-nowrap">{formatDate(r.arrival_ts, locale, "datetime")}</span> },
      { id: "wait", header: t.colWaiting, value: (r) => r.waiting_min, align: "right", cell: (r) => <span className="tabular">{formatNumber(r.waiting_min, locale, { digits: 1 })}</span> },
      { id: "pos", header: t.colPosition, value: (r) => r.position ?? "", align: "right" },
    ],
    [t, locale, stageLabel],
  );
  return (
    <Section title={t.queueTitle} description={t.queueDesc} id="queue-now" data-tour="logistics-queue">
      <QueryState query={q}>
        {(d) => (
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <StatTile label={t.waiting} value={formatNumber(d.trucks_waiting, locale)} unit={t.trucks} foot={<ProvenanceBadge provenance={d.provenance} />} />
              <StatTile label={t.unloading} value={formatNumber(d.trucks_unloading, locale)} unit={t.trucks} foot={<ProvenanceBadge provenance={d.provenance} />} />
              <StatTile label={t.avgWait} value={formatNumber(d.avg_wait_min, locale, { digits: 1 })} unit={t.min} foot={<ProvenanceBadge provenance={d.provenance} />} />
              <StatTile label={t.maxWait} value={formatNumber(d.max_wait_min, locale, { digits: 1 })} unit={t.min} foot={<ProvenanceBadge provenance={d.provenance} />} />
            </div>
            {d.by_stage ? (
              <div className="flex flex-wrap items-center gap-1.5 text-xs" aria-label={t.byStage}>
                <span className="text-muted-foreground">{t.byStage}:</span>
                {Object.entries(d.by_stage).map(([k, v]) => (
                  <Badge key={k} tone="outline">
                    {stageLabel[k] ?? k} <span className="tabular font-semibold text-foreground">{v}</span>
                  </Badge>
                ))}
              </div>
            ) : null}
            {d.note ? (
              <p className="text-xs text-muted-foreground">
                <ApiText>{d.note}</ApiText>
              </p>
            ) : null}
            <TimeSeriesChart title={t.queueSeries} series={[d.queue_length_series]} height={220} />
            <DataTable data={d.trucks} columns={columns} caption={t.trucksTable} getRowId={(r) => String(r.truck_trip_id)} pageSize={8} exportName="trucks-in-queue" />
          </div>
        )}
      </QueryState>
    </Section>
  );
}

function PredictionSection() {
  const t = useT(messages);
  const { locale } = useLocale();
  const pred = useApiQuery("/api/v1/ai/logistics/queue-prediction");
  const queue = useApiQuery("/api/v1/logistics/queue");
  return (
    <Section title={t.predTitle} description={t.predDesc} id="queue-prediction">
      <QueryState query={pred}>
        {(d) => (
          <div className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-3">
              <StatTile label={t.predAvg} value={formatNumber(d.predicted_avg_wait_min, locale, { digits: 1 })} unit={t.min} foot={<ProvenanceBadge provenance={d.provenance} />} />
              <StatTile label={t.predObserved} value={formatNumber(queue.data?.avg_wait_min ?? null, locale, { digits: 1 })} unit={t.min} foot={queue.data ? <ProvenanceBadge provenance={queue.data.provenance} /> : undefined} />
            </div>
            <p className="text-xs text-muted-foreground">{t.predNote}</p>
            {d.items.length > 0 ? (
              <div className="max-h-60 overflow-auto rounded-lg border border-border" tabIndex={0} role="region" aria-label={t.predTitle}>
                <table className="tabular w-full border-collapse text-left text-xs">
                  <caption className="sr-only">{t.predTitle}</caption>
                  <thead className="sticky top-0 bg-surface-2 text-muted-foreground">
                    <tr>
                      {[t.colPos, t.colTruck, t.colPred, t.colInterval].map((h) => (
                        <th key={h} scope="col" className="border-b border-border px-2.5 py-2 font-semibold whitespace-nowrap">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {d.items.map((it) => (
                      <tr key={it.position} className="border-b border-border last:border-0">
                        <td className="px-2.5 py-1.5">{it.position}</td>
                        <td className="px-2.5 py-1.5 font-mono">{it.truck_trip_id ?? "—"}</td>
                        <td className="px-2.5 py-1.5 font-semibold">{formatNumber(it.predicted_wait_min, locale, { digits: 1 })}</td>
                        <td className="px-2.5 py-1.5">{it.lower_min != null && it.upper_min != null ? `${formatNumber(it.lower_min, locale, { digits: 1 })} – ${formatNumber(it.upper_min, locale, { digits: 1 })}` : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
            <ModelMetrics model={d.model} />
          </div>
        )}
      </QueryState>
    </Section>
  );
}

function ArrivalsSection() {
  const t = useT(messages);
  const { locale } = useLocale();
  const pattern = useApiQuery("/api/v1/logistics/arrival-pattern");
  const forecast = useApiQuery("/api/v1/ai/logistics/arrival-forecast", { params: { query: { horizon_h: 24 } } });
  const hours = useMemo(() => Array.from({ length: 24 }, (_, h) => String(h).padStart(2, "0")), []);
  return (
    <Section title={t.arrivalsTitle} description={t.arrivalsDesc} id="arrivals">
      <QueryState query={pattern}>
        {(d) => (
          <div className="flex flex-col gap-4">
            <TimeSeriesChart title={t.byHour} series={[d.by_hour, d.typical_by_hour]} height={220} timeStyle="short" actions={<ProvenanceBadge provenance={d.provenance} />} />
            {d.heatmap && d.heatmap.length > 0 ? (
              <>
                <HeatmapChart
                  title={t.heatTitle}
                  x={hours}
                  y={[...t.weekday]}
                  values={d.heatmap.map((c) => [c.hour, c.weekday, c.avg_arrivals] as [number, number, number | null])}
                  unit={t.heatUnit}
                  height={240}
                  summary={t.heatTitle}
                />
                {d.heatmap_note ? (
                  <p className="text-2xs text-muted-foreground">
                    <ApiText>{d.heatmap_note}</ApiText>
                  </p>
                ) : null}
              </>
            ) : null}
          </div>
        )}
      </QueryState>
      <QueryState query={forecast}>
        {(d) => (
          <div className="flex flex-col gap-3">
            <AreaBandChart title={t.forecastTitle} band={d.forecast} actual={d.actual} baseline={d.baseline ?? undefined} height={240} actions={<ProvenanceBadge provenance={d.forecast.provenance} />} />
            <ModelMetrics model={d.model} />
            <p className="sr-only">{formatNumber(d.forecast.points.length, locale)}</p>
          </div>
        )}
      </QueryState>
    </Section>
  );
}

const SIM_ROWS = [
  ["simAvgWait", "avg_wait_min", "avg_wait_min"],
  ["simP90", "p90_wait_min", null],
  ["simMaxWait", "max_wait_min", null],
  ["simMaxQ", "max_queue_length", null],
  ["simTurn", "avg_turnaround_min", "avg_turnaround_min"],
  ["simBridgeU", "bridge_utilisation_pct", null],
  ["simRampU", "unloading_utilisation_pct", null],
  ["simDeferral", "avg_deferral_min", null],
  ["simTotalDelay", "avg_total_delay_min", null],
] as const;

function SimulationSection() {
  const t = useT(messages);
  const { locale } = useLocale();
  const [bridges, setBridges] = useState("2");
  const [slotMin, setSlotMin] = useState("30");
  const [perSlot, setPerSlot] = useState("6");
  const [ramps, setRamps] = useState("4");
  const [seed, setSeed] = useState("42");
  const [rampCap, setRampCap] = useState("600");
  const [replay, setReplay] = useState(true);
  const run = useApiMutation("/api/v1/logistics/queue-simulation");
  const nums = { bridges: Number(bridges), slotMin: Number(slotMin), perSlot: Number(perSlot), ramps: Number(ramps), seed: Number(seed) };
  const valid =
    Number.isInteger(nums.bridges) && nums.bridges >= 1 && nums.bridges <= 6 &&
    Number.isInteger(nums.slotMin) && nums.slotMin >= 5 && nums.slotMin <= 240 &&
    Number.isInteger(nums.perSlot) && nums.perSlot >= 1 && nums.perSlot <= 50 &&
    Number.isInteger(nums.ramps) && nums.ramps >= 1 && nums.ramps <= 20 &&
    Number.isInteger(nums.seed) && nums.seed >= 0 &&
    (rampCap.trim() === "" || (Number.isFinite(Number(rampCap)) && Number(rampCap) >= 50 && Number(rampCap) <= 5000));
  const r = run.data;
  const fifo = r?.results.find((x) => x.policy === "fifo");
  const slot = r?.results.find((x) => x.policy === "slot_based");

  return (
    <Section title={t.simTitle} description={t.simDesc} id="queue-simulation" data-tour="logistics-simulation">
      <form
        className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-[repeat(6,minmax(0,1fr))_auto_auto] xl:items-end"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid)
            run.mutate({
              body: { policies: ["fifo", "slot_based"], weighbridges: nums.bridges, slot_minutes: nums.slotMin, trucks_per_slot: nums.perSlot, unloading_ramps: nums.ramps, seed: nums.seed, replay_observed_outages: replay, ramp_capacity_t: rampCap.trim() === "" ? null : Number(rampCap) },
            });
        }}
      >
        <Field label={t.simWeighbridges}>{(id) => <NativeInput id={id} type="number" min={1} max={6} value={bridges} onChange={(e) => setBridges(e.target.value)} />}</Field>
        <Field label={t.simSlotMin}>{(id) => <NativeInput id={id} type="number" min={5} max={240} value={slotMin} onChange={(e) => setSlotMin(e.target.value)} />}</Field>
        <Field label={t.simPerSlot}>{(id) => <NativeInput id={id} type="number" min={1} max={50} value={perSlot} onChange={(e) => setPerSlot(e.target.value)} />}</Field>
        <Field label={t.simRamps}>{(id) => <NativeInput id={id} type="number" min={1} max={20} value={ramps} onChange={(e) => setRamps(e.target.value)} />}</Field>
        <Field label={t.simRampCap}>{(id) => <NativeInput id={id} type="number" min={50} max={5000} value={rampCap} onChange={(e) => setRampCap(e.target.value)} />}</Field>
        <Field label={t.simSeed}>{(id) => <NativeInput id={id} type="number" min={0} value={seed} onChange={(e) => setSeed(e.target.value)} />}</Field>
        <label className="flex h-9 items-center gap-1.5 text-xs">
          <input type="checkbox" checked={replay} onChange={(e) => setReplay(e.target.checked)} className="size-3.5 accent-[var(--accent)]" />
          {t.simReplay}
        </label>
        <Button type="submit" variant="accent" disabled={!valid || run.isPending}>
          <Play aria-hidden /> {t.simRun}
        </Button>
      </form>
      {run.isError ? <ErrorState error={run.error} compact /> : null}
      {!r && !run.isError ? <p className="text-xs text-muted-foreground">{t.simEmpty}</p> : null}
      {r && fifo && slot ? (
        <div className="flex flex-col gap-4" aria-live="polite">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <ProvenanceBadge provenance={r.provenance} />
            <Badge tone="outline">{t.simTrucks(r.trucks_simulated)}</Badge>
            {r.business_date ? <span className="tabular text-muted-foreground">{r.business_date}</span> : null}
          </div>
          <div role="note" className="flex items-start gap-2 rounded-lg border border-warning/50 bg-warning-soft/50 p-3 text-xs">
            <TriangleAlert className="mt-0.5 size-4 shrink-0 text-warning-fg" aria-hidden />
            <div>
              <p className="font-semibold text-foreground">{t.simGapTitle}</p>
              <p className="mt-0.5 text-muted-foreground">{t.simGapBody}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
            <StatTile label={`${t.simObserved} — ${t.simAvgWait}`} value={formatNumber(r.observed?.avg_wait_min ?? null, locale, { digits: 1 })} unit={t.min} foot={<ProvenanceBadge kind="synthetic_actual" />} />
            <StatTile label={`${t.simFifo} — ${t.simAvgWait}`} value={formatNumber(fifo.avg_wait_min, locale, { digits: 1 })} unit={t.min} foot={<ProvenanceBadge kind="what_if" />} />
            <StatTile label={`${t.simSlot} — ${t.simAvgWait}`} value={formatNumber(slot.avg_wait_min, locale, { digits: 1 })} unit={t.min} foot={<ProvenanceBadge kind="what_if" />} />
          </div>
          <BarChart
            title={t.simChart}
            categories={[t.simAvgWait, t.simTurn]}
            series={[
              { key: "obs", label: t.simObserved, values: [r.observed?.avg_wait_min ?? null, r.observed?.avg_turnaround_min ?? null], kind: "synthetic_actual" },
              { key: "fifo", label: t.simFifo, values: [fifo.avg_wait_min, fifo.avg_turnaround_min], kind: "what_if" },
              { key: "slot", label: t.simSlot, values: [slot.avg_wait_min, slot.avg_turnaround_min], kind: "what_if" },
            ]}
            unit={t.min}
            height={240}
          />
          <div className="relative overflow-x-auto rounded-lg border border-border" tabIndex={0} role="region" aria-label={t.simTitle}>
            <table className="tabular w-full border-collapse text-left text-xs">
              <caption className="sr-only">{t.simTitle}</caption>
              <thead className="bg-surface-2 text-muted-foreground">
                <tr>
                  {[t.simMetric, t.simObserved, t.simFifo, t.simSlot].map((h) => (
                    <th key={h} scope="col" className="border-b border-border px-2.5 py-2 font-semibold whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {SIM_ROWS.map(([label, key, obsKey]) => (
                  <tr key={key} className="border-b border-border last:border-0">
                    <th scope="row" className="px-2.5 py-2 text-left font-medium">
                      {t[label]}
                    </th>
                    <td className="px-2.5 py-2">{obsKey ? formatNumber(r.observed?.[obsKey] ?? null, locale, { digits: 1 }) : "—"}</td>
                    <td className="px-2.5 py-2">{formatNumber((fifo[key] as number | null | undefined) ?? null, locale, { digits: 1 })}</td>
                    <td className="px-2.5 py-2">{formatNumber((slot[key] as number | null | undefined) ?? null, locale, { digits: 1 })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <TimeSeriesChart
            title={t.simQueueSeries}
            series={[
              { ...fifo.queue_length_series, key: "fifo", label: t.simFifo },
              { ...slot.queue_length_series, key: "slot", label: t.simSlot },
            ]}
            height={220}
          />
          <p className="text-2xs text-muted-foreground">{t.simBestEffort}</p>
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <section className="rounded-xl border border-border bg-surface p-4" aria-label={t.simLimits}>
              <h3 className="mb-1.5 text-sm font-semibold">{t.simLimits}</h3>
              <ul className="list-disc pl-5 text-xs text-muted-foreground">
                {r.limitations.map((l) => (
                  <li key={l} lang="en">
                    {l}
                  </li>
                ))}
              </ul>
              {r.inferred_outages && r.inferred_outages.length > 0 ? (
                <div className="mt-3">
                  <p className="text-2xs font-semibold text-muted-foreground uppercase">{t.simOutages}</p>
                  <ul className="mt-1 text-xs">
                    {(r.inferred_outages as Record<string, unknown>[]).map((o, i) => (
                      <li key={i} className="font-mono text-2xs">
                        {String(o.unit)} · {formatDate(String(o.start), locale, "datetime")} → {formatDate(String(o.end), locale, "datetime")} · {t.simWaiting}: {String(o.min_waiting)}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </section>
            <EvidencePanel assumptions={r.assumptions} title={t.simAssumptions} />
          </div>
        </div>
      ) : null}
    </Section>
  );
}

function TicketsSection() {
  const t = useT(messages);
  const { locale } = useLocale();
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const q = useApiQuery("/api/v1/logistics/tickets", { params: { query: { period: "7d", limit: 200, flagged_only: flaggedOnly } } });
  const flagLabel = t.flag as Record<string, string>;
  const columns = useMemo<DataTableColumn<Ticket>[]>(
    () => [
      { id: "no", header: t.colTicket, value: (r) => r.ticket_no, cell: (r) => <span className="font-mono text-xs whitespace-nowrap">{r.ticket_no}</span> },
      { id: "sup", header: t.colSupplier, value: (r) => r.supplier_code },
      { id: "bridge", header: t.colBridge, value: (r) => r.bridge_code },
      { id: "in", header: t.colIn, value: (r) => r.weigh_in_ts, cell: (r) => <span className="whitespace-nowrap">{formatDate(r.weigh_in_ts, locale, "datetime")}</span> },
      { id: "gross", header: t.colGross, value: (r) => r.gross_kg, align: "right", cell: (r) => formatNumber(r.gross_kg, locale) },
      { id: "tare", header: t.colTare, value: (r) => r.tare_kg ?? "", align: "right", cell: (r) => formatNumber(r.tare_kg ?? null, locale) },
      { id: "net", header: t.colNet, value: (r) => r.net_kg ?? "", align: "right", cell: (r) => formatNumber(r.net_kg ?? null, locale) },
      { id: "grade", header: t.colGrade, value: (r) => r.grade ?? "" },
      { id: "ded", header: t.colDeduction, value: (r) => r.deduction_pct ?? "", align: "right", cell: (r) => formatNumber(r.deduction_pct ?? null, locale, { digits: 1 }) },
      {
        id: "flags",
        header: t.colFlags,
        value: (r) => (r.flags ?? []).join(", "),
        sortable: false,
        cell: (r) =>
          r.flags && r.flags.length > 0 ? (
            <ul className="flex min-w-44 flex-col gap-1">
              {r.flags.map((f) => (
                <li key={f}>
                  <Badge tone="warning" title={t.flagNote}>
                    {t.flagPrefix}: {flagLabel[f] ?? f}
                  </Badge>
                </li>
              ))}
            </ul>
          ) : (
            t.none
          ),
      },
    ],
    [t, locale, flagLabel],
  );
  return (
    <Section
      title={t.ticketsTitle}
      description={t.ticketsDesc}
      id="tickets"
      actions={
        <label className="flex items-center gap-1.5 text-xs">
          <input type="checkbox" checked={flaggedOnly} onChange={(e) => setFlaggedOnly(e.target.checked)} className="size-3.5 accent-[var(--accent)]" />
          {t.flaggedOnly}
        </label>
      }
    >
      <p className="text-xs text-muted-foreground">{t.flagNote}</p>
      <QueryState query={q} isEmpty={(d) => d.items.length === 0}>
        {(d) => (
          <>
            <ProvenanceBadge kind="synthetic_actual" />
            {d.note ? (
              <p className="text-2xs text-muted-foreground">
                <ApiText>{d.note}</ApiText>
              </p>
            ) : null}
            <DataTable data={d.items} columns={columns} caption={t.ticketsTitle} getRowId={(r) => String(r.id)} pageSize={10} exportName="weighbridge-tickets" initialSort={[{ id: "in", desc: true }]} />
          </>
        )}
      </QueryState>
    </Section>
  );
}

function AnomaliesSection() {
  const t = useT(messages);
  const { locale } = useLocale();
  const q = useApiQuery("/api/v1/ai/logistics/anomalies", { params: { query: { period: "7d" } } });
  const [pick, setPick] = useState<number | null>(null);
  return (
    <Section title={t.anomaliesTitle} description={t.anomaliesDesc} id="logistics-anomalies">
      <Disclaimer kind="advisory" />
      <QueryState query={q} isEmpty={(d) => d.items.length === 0} empty={<p className="text-xs text-muted-foreground">{t.anomalyNone}</p>} compact>
        {(d) => {
          const items = [...d.items].sort((a, b) => Date.parse(b.peak_ts ?? b.start_ts) - Date.parse(a.peak_ts ?? a.start_ts));
          const sel = items.find((a) => a.id === pick) ?? items[0]!;
          return (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]">
              <ul className="flex max-h-72 flex-col gap-1.5 overflow-y-auto">
                {items.map((a) => (
                  <li key={a.id}>
                    <button type="button" aria-pressed={a.id === sel.id} onClick={() => setPick(a.id)} className={`flex w-full flex-col gap-1 rounded-lg border px-3 py-2 text-left text-xs focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none ${a.id === sel.id ? "border-accent bg-accent-soft/40" : "border-border hover:bg-surface-2"}`}>
                      <span className="flex items-center justify-between gap-2">
                        <span className="font-mono font-semibold">{a.code}</span>
                        <OpsSeverityPill severity={a.severity} />
                      </span>
                      <span className="tabular text-muted-foreground">{formatDate(a.peak_ts ?? a.start_ts, locale, "datetime")}</span>
                      <span lang="en">{a.detector}</span>
                    </button>
                  </li>
                ))}
              </ul>
              <div className="flex min-w-0 flex-col gap-2">
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <ProvenanceBadge kind="synthetic_actual" />
                  <Badge tone="warning">{t.flagPrefix}</Badge>
                  <span className="font-mono text-2xs text-subtle-foreground">{sel.model_version}</span>
                </div>
                <EvidencePanel evidence={sel.evidence} factors={sel.contributing_factors} />
                {sel.recommended_investigation?.map((x) => (
                  <p key={x} lang="en" className="text-xs text-muted-foreground">
                    {x}
                  </p>
                ))}
              </div>
            </div>
          );
        }}
      </QueryState>
    </Section>
  );
}

function SuppliersSection() {
  const t = useT(messages);
  const { locale } = useLocale();
  const q = useApiQuery("/api/v1/logistics/suppliers");
  const columns = useMemo<DataTableColumn<Supplier>[]>(
    () => [
      { id: "code", header: t.colCode, value: (r) => r.code, cell: (r) => <span className="font-mono text-xs">{r.code}</span> },
      { id: "name", header: t.colName, value: (r) => r.name, cell: (r) => <span lang="en">{r.name}</span> },
      { id: "type", header: t.colType, value: (r) => r.supplier_type },
      { id: "prov", header: t.colProvince, value: (r) => r.province ?? "", cell: (r) => <span lang="en">{r.province ?? "—"}</span> },
      { id: "del", header: t.colDeliveries, value: (r) => r.deliveries_30d ?? "", align: "right" },
      { id: "ffb", header: t.colFfb, value: (r) => r.ffb_30d_t ?? "", align: "right", cell: (r) => formatValue(r.ffb_30d_t ?? null, undefined, locale, { digits: 1 }) },
      { id: "ripe", header: t.colRipe, value: (r) => r.avg_ripe_pct ?? "", align: "right", cell: (r) => formatNumber(r.avg_ripe_pct ?? null, locale, { digits: 1 }) },
      { id: "wait", header: t.colWait, value: (r) => r.avg_wait_min ?? "", align: "right", cell: (r) => formatNumber(r.avg_wait_min ?? null, locale, { digits: 1 }) },
      { id: "sus", header: t.colSustain, value: (r) => r.sustainability_status },
    ],
    [t, locale],
  );
  return (
    <Section title={t.suppliersTitle} description={t.suppliersDesc} id="suppliers">
      <ProvenanceBadge kind="synthetic_actual" />
      <QueryState query={q} isEmpty={(d) => d.items.length === 0}>
        {(d) => <DataTable data={d.items} columns={columns} caption={t.suppliersTitle} getRowId={(r) => String(r.id)} pageSize={10} exportName="suppliers" initialSort={[{ id: "ffb", desc: true }]} />}
      </QueryState>
    </Section>
  );
}
