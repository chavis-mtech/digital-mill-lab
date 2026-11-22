"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ClipboardPlus } from "lucide-react";
import type { Schema } from "@dml/contracts";
import { OperationsLayout } from "@/components/layouts/layouts";
import { useApiQuery } from "@/lib/api/hooks";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatDate, formatNumber, formatValue } from "@/lib/format";
import { AlertBadge } from "@/components/demo/severity";
import { ProvenanceBadge } from "@/components/demo/provenance-badge";
import { DataTable, type DataTableColumn } from "@/components/data/data-table";
import { TimeSeriesChart } from "@/components/charts/charts";
import { QueryState } from "@/components/states/states";
import { Button } from "@/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { ApiText, NativeSelect, Section } from "./shared/ops-ui";
import { AnomalyEvidence, HealthCriteria, HistoryPanel, RiskBreakdown } from "./maintenance-parts";
import { chartSensorCodes, limitsToThresholds, parseIdParam, sortByAttention, toChartMarkers, type HealthState } from "./helpers";
import messages from "./maintenance.i18n";

type Summary = Schema<"EquipmentSummary">;

const STATES: readonly HealthState[] = ["critical", "maintenance_required", "warning", "normal"];
const RANGES = { "3": 3, "10": 10, "30": 30 } as const;

export function EquipmentPage() {
  const t = useT(messages);
  const { locale } = useLocale();
  const params = useSearchParams();
  const rawPreset = params.get("equipment_id");
  const list = useApiQuery("/api/v1/maintenance/equipment");
  // Numeric id (links from other pages) or an equipment code such as PRS-03 (typed / shared links).
  const preset =
    parseIdParam(rawPreset) ??
    (rawPreset && /^[A-Za-z0-9-]{2,20}$/.test(rawPreset)
      ? (list.data?.items.find((i) => i.code.toLowerCase() === rawPreset.toLowerCase())?.id ?? null)
      : null);
  const [picked, setPicked] = useState<number | null>(null);
  const [state, setState] = useState<HealthState | "all">("all");
  const [stage, setStage] = useState("all");

  const items = list.data?.items;
  const effectiveId = picked ?? preset ?? (items ? (sortByAttention(items)[0]?.id ?? null) : null);

  const stages = useMemo(() => Array.from(new Set((items ?? []).map((i) => i.process_stage_code))), [items]);
  const filtered = useMemo(() => sortByAttention((items ?? []).filter((i) => (state === "all" || i.health_state === state) && (stage === "all" || i.process_stage_code === stage))), [items, state, stage]);

  const columns = useMemo<DataTableColumn<Summary>[]>(
    () => [
      {
        id: "code",
        header: t.common.code,
        value: (r) => r.code,
        cell: (r) => (
          <button type="button" aria-pressed={r.id === effectiveId} onClick={() => setPicked(r.id)} className="rounded font-mono text-[0.8125rem] font-semibold text-accent-text underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
            {r.code}
          </button>
        ),
      },
      { id: "name", header: "", value: (r) => r.name, cell: (r) => <span lang="en">{r.name}</span> },
      { id: "state", header: t.common.state, value: (r) => r.health_state, cell: (r) => <AlertBadge state={r.health_state} /> },
      { id: "risk", header: t.common.risk, value: (r) => r.risk_score ?? -1, align: "right", cell: (r) => <span className="tabular">{r.risk_score != null ? formatNumber(r.risk_score, locale, { digits: 1 }) : "—"}</span> },
      {
        id: "why",
        header: t.equipment.triggered,
        value: (r) => (r.triggered_by ?? []).join("; "),
        sortable: false,
        cell: (r) => (
          <ul className="min-w-44 text-xs">
            {(r.triggered_by ?? []).slice(0, 2).map((x) => (
              <li key={x} lang="en">
                {x}
              </li>
            ))}
          </ul>
        ),
      },
      { id: "wo", header: t.equipment.openWo, value: (r) => r.open_work_orders ?? 0, align: "right" },
      { id: "stage", header: t.common.stage, value: (r) => r.process_stage_code, cell: (r) => <span className="font-mono text-2xs">{r.process_stage_code}</span> },
    ],
    [t, effectiveId, locale],
  );

  return (
    <OperationsLayout route="/demo/maintenance/equipment">
      <Section
        title={t.equipment.listTitle}
        description={t.equipment.listDesc}
        actions={
          <>
            <label className="flex items-center gap-1.5 text-xs">
              <span className="text-muted-foreground">{t.equipment.filterState}</span>
              <NativeSelect value={state} onChange={(e) => setState(e.target.value as HealthState | "all")} className="h-8 w-auto text-[0.8125rem]">
                <option value="all">{t.equipment.filterAll}</option>
                {STATES.map((s) => (
                  <option key={s} value={s}>
                    {s} ({list.data?.counts_by_state[s] ?? 0})
                  </option>
                ))}
              </NativeSelect>
            </label>
            <label className="flex items-center gap-1.5 text-xs">
              <span className="text-muted-foreground">{t.equipment.filterStage}</span>
              <NativeSelect value={stage} onChange={(e) => setStage(e.target.value)} className="h-8 w-auto text-[0.8125rem]">
                <option value="all">{t.equipment.filterStageAll}</option>
                {stages.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </NativeSelect>
            </label>
          </>
        }
      >
        <QueryState query={list} isEmpty={(d) => d.items.length === 0}>
          {(d) => (
            <>
              <div className="flex flex-wrap items-center gap-2">
                {d.provenance ? <ProvenanceBadge provenance={d.provenance} /> : null}
                <span className="text-xs text-muted-foreground">{formatDate(d.as_of, locale, "datetime")}</span>
              </div>
              <DataTable data={filtered} columns={columns} caption={t.equipment.listTitle} getRowId={(r) => String(r.id)} pageSize={8} exportName="equipment-health" />
            </>
          )}
        </QueryState>
      </Section>
      {effectiveId != null ? <EquipmentDetailView id={effectiveId} asOf={list.data?.as_of} /> : null}
    </OperationsLayout>
  );
}

function EquipmentDetailView({ id, asOf }: { id: number; asOf?: string }) {
  const t = useT(messages);
  const { locale } = useLocale();
  const detail = useApiQuery("/api/v1/maintenance/equipment/{equipment_id}", { params: { path: { equipment_id: id } } });
  return (
    <QueryState query={detail}>
      {(eq) => (
        <>
          <Section title={`${eq.code} — ${eq.name}`} description={`${eq.equipment_type} · ${eq.process_stage_code} · ${t.common.criticality}: ${eq.criticality}`} actions={<WoLink id={id} />} id="equipment-detail">
            <div className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
              <Fact label={t.common.state} value={<AlertBadge state={eq.health.state} />} />
              <Fact label={t.equipment.maintStatus} value={<span lang="en">{eq.maintenance_status ?? "—"}</span>} />
              <Fact label={t.equipment.runningHours} value={formatValue(eq.running_hours ?? null, t.common.hours, locale)} />
              <Fact label={t.equipment.lastService} value={formatDate(eq.last_maintenance_at, locale, "date")} />
              <Fact label={t.equipment.daysSince} value={formatNumber(eq.days_since_last_service ?? null, locale, { digits: 0 })} />
              <Fact label={t.equipment.service} value={<span lang="en">{eq.service_interval ?? "—"}</span>} />
              <Fact label={t.equipment.openWo} value={formatNumber(eq.active_work_order_ids?.length ?? 0, locale)} />
            </div>
          </Section>

          <SensorTrends id={id} sensors={eq.sensors} asOf={asOf ?? eq.health.as_of ?? undefined} />

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            <Section title={t.equipment.howTitle} description={t.equipment.criteriaTitle}>
              <HealthCriteria health={eq.health} />
            </Section>
            <Section title={t.equipment.riskTitle}>
              <RiskBreakdown health={eq.health} />
            </Section>
          </div>

          <Section title={t.equipment.sensorInfo}>
            <div className="relative overflow-x-auto rounded-lg border border-border" tabIndex={0} role="region" aria-label={t.equipment.sensorInfo}>
              <table className="tabular w-full border-collapse text-left text-xs">
                <caption className="sr-only">{t.equipment.sensorInfo}</caption>
                <thead className="bg-surface-2 text-muted-foreground">
                  <tr>
                    {[t.equipment.colSensor, t.common.type, t.equipment.colLatest, t.equipment.colWarn, t.equipment.colCrit, t.equipment.colNormal].map((h) => (
                      <th key={h} scope="col" className="border-b border-border px-2.5 py-2 font-semibold whitespace-nowrap">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {eq.sensors.map((s) => (
                    <tr key={s.id} className="border-b border-border last:border-0">
                      <td className="px-2.5 py-2">
                        <span className="font-mono">{s.code}</span>
                        <span className="block text-muted-foreground" lang="en">
                          {s.name}
                        </span>
                      </td>
                      <td className="px-2.5 py-2">{s.sensor_type}</td>
                      <td className="px-2.5 py-2">
                        <span className="font-semibold">{formatValue(s.latest?.value ?? null, s.unit, locale)}</span> {s.latest ? <ProvenanceBadge provenance={s.latest.provenance} compact /> : null}
                      </td>
                      <td className="px-2.5 py-2">{s.warn_limit != null ? formatValue(s.warn_limit, s.unit, locale) : "—"}</td>
                      <td className="px-2.5 py-2">{s.crit_limit != null ? formatValue(s.crit_limit, s.unit, locale) : "—"}</td>
                      <td className="px-2.5 py-2" title={s.normal_range?.basis}>
                        {s.normal_range ? `${formatNumber(s.normal_range.low ?? null, locale)} – ${formatValue(s.normal_range.high ?? null, s.unit, locale)}` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>

          <Section title={t.equipment.anomalyTitle} description={t.overview.anomalyDesc}>
            <AnomalyEvidence equipmentId={id} />
          </Section>

          <Section title={t.equipment.historyTitle}>
            <HistoryPanel equipmentId={id} />
          </Section>
        </>
      )}
    </QueryState>
  );
}

function WoLink({ id }: { id: number }) {
  const t = useT(messages);
  return (
    <Button asChild variant="outline" size="sm">
      <Link href={`/demo/maintenance/work-orders?equipment_id=${id}`}>
        <ClipboardPlus aria-hidden /> {t.common.createWo}
      </Link>
    </Button>
  );
}

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border p-2.5">
      <p className="text-2xs text-muted-foreground">{label}</p>
      <div className="tabular mt-0.5 text-sm font-semibold">{value}</div>
    </div>
  );
}

function SensorTrends({ id, sensors, asOf }: { id: number; sensors: Schema<"SensorInfo">[]; asOf?: string }) {
  const t = useT(messages);
  const { locale } = useLocale();
  const [range, setRange] = useState<keyof typeof RANGES>("10");
  const start = useMemo(() => (asOf ? new Date(Date.parse(asOf) - RANGES[range] * 86_400_000).toISOString() : undefined), [asOf, range]);
  const q = useApiQuery(
    "/api/v1/maintenance/equipment/{equipment_id}/sensors",
    { params: { path: { equipment_id: id }, query: { resolution: "hour", ...(start ? { start } : {}) } } },
    { enabled: Boolean(asOf) },
  );
  const codes = chartSensorCodes(sensors);
  return (
    <Section
      title={t.equipment.trendTitle}
      description={t.equipment.trendDesc}
      data-tour="equipment-sensor-trend"
      id="equipment-trend"
      actions={
        <ToggleGroup type="single" value={range} onValueChange={(v) => v && setRange(v as keyof typeof RANGES)} aria-label={t.equipment.trendRange}>
          <ToggleGroupItem value="3" className="px-2.5 text-xs">
            {t.equipment.range3}
          </ToggleGroupItem>
          <ToggleGroupItem value="10" className="px-2.5 text-xs">
            {t.equipment.range10}
          </ToggleGroupItem>
          <ToggleGroupItem value="30" className="px-2.5 text-xs">
            {t.equipment.range30}
          </ToggleGroupItem>
        </ToggleGroup>
      }
    >
      <QueryState query={q} isEmpty={(d) => d.series.length === 0}>
        {(d) => (
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            {codes.map((code) => {
              const s = d.series.find((x) => x.key === code);
              if (!s) return null;
              const last = [...s.points].reverse().find((p) => p.v != null)?.v ?? null;
              return (
                <div key={code} className="min-w-0 rounded-lg border border-border p-3">
                  <TimeSeriesChart
                    title={s.label}
                    description={`${code} · ${s.unit}`}
                    series={[s]}
                    height={220}
                    thresholds={limitsToThresholds(d.limits?.[code], { warn: t.equipment.warnLimit, crit: t.equipment.critLimit })}
                    normalRange={d.normal_ranges[code]}
                    anomalies={toChartMarkers(d.anomaly_markers, code)}
                    summary={t.equipment.trendSummary(s.label, formatNumber(last, locale), s.unit)}
                    actions={<ProvenanceBadge provenance={s.provenance} />}
                  />
                </div>
              );
            })}
            {d.note ? (
              <p className="text-xs text-muted-foreground xl:col-span-2">
                <ApiText>{d.note}</ApiText>
              </p>
            ) : null}
          </div>
        )}
      </QueryState>
    </Section>
  );
}
