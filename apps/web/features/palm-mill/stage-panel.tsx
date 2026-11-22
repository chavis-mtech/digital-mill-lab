"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ChevronDown } from "lucide-react";
import type { Schema } from "@dml/contracts";
import { useApiQuery } from "@/lib/api/hooks";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatDate, formatNumber, formatValue } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AlertBadge } from "@/components/demo/severity";
import { ProvenanceBadge } from "@/components/demo/provenance-badge";
import { Disclaimer } from "@/components/demo/disclaimer";
import { KpiCard } from "@/components/data/kpi-card";
import { TimeSeriesChart, type Threshold } from "@/components/charts/charts";
import { QueryState } from "@/components/states/states";
import { SeverityPill } from "@/features/executive/shared/sev";
import { AlertDetailDialog } from "@/features/executive/shared/alert-detail-dialog";
import { ApiText, Section } from "@/features/executive/shared/section";
import { alertSourceKind } from "@/features/executive/shared/links";
import exec from "@/features/executive/executive.i18n";
import messages from "./palm-mill.i18n";
import { HEALTH_RANK, type HealthState } from "./twin-model";

type StageCode = Schema<"StageCode">;
type Equipment = Schema<"EquipmentSummary">;
type Variable = Schema<"ProcessVariable">;

function statusWord(words: unknown, s: string) {
  return (words as Readonly<Record<string, string>>)[s] ?? s;
}

function EquipmentRow({ eq }: { eq: Equipment }) {
  const t = useT(messages);
  const { locale } = useLocale();
  const [open, setOpen] = useState(eq.health_state !== "normal");
  const q = useApiQuery("/api/v1/maintenance/equipment/{equipment_id}/health", { params: { path: { equipment_id: eq.id } } }, { enabled: open });
  return (
    <li className="py-2">
      <div className="flex flex-wrap items-center gap-2">
        <AlertBadge state={eq.health_state} />
        <span className="font-mono text-xs font-semibold">{eq.code}</span>
        <span className="text-xs text-muted-foreground">{eq.name}</span>
        {eq.risk_score != null ? (
          <span className="tabular ml-auto text-2xs text-muted-foreground">
            {t.panel.risk} {formatNumber(eq.risk_score, locale, { digits: 1 })}/100
          </span>
        ) : null}
        <Button variant="ghost" size="xs" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
          <ChevronDown className={cn("transition-transform", open && "rotate-180")} aria-hidden />
          {open ? t.panel.hideCriteria : t.panel.showCriteria}
        </Button>
      </div>
      {open ? (
        <div className="mt-2 rounded-lg bg-surface-2 p-2.5">
          <QueryState query={q} compact>
            {(h) => {
              const shown = h.criteria.filter((c) => c.affects_state && (c.breached || c.kind !== "sensor_limit" || h.state === "normal"));
              const info = h.criteria.filter((c) => !c.affects_state);
              return (
                <div className="flex flex-col gap-2 text-xs">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">{t.panel.criteria}</span>
                    <ProvenanceBadge provenance={h.provenance} />
                  </div>
                  {h.state_rule ? (
                    <p className="text-2xs text-muted-foreground">
                      <ApiText>{h.state_rule}</ApiText>
                    </p>
                  ) : null}
                  <ul className="flex flex-col gap-1">
                    {(shown.length ? shown : h.criteria.filter((c) => c.affects_state).slice(0, 4)).map((c, i) => (
                      <li key={`${c.sensor_code}-${c.rule}-${i}`} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                        <Badge tone={c.breached ? (c.state_if_breached === "critical" ? "critical" : "warning") : "success"}>{c.breached ? t.panel.breached : t.panel.ok}</Badge>
                        <span className="min-w-0 flex-1">
                          <ApiText>{c.rule}</ApiText>
                        </span>
                        <span className="tabular text-muted-foreground">
                          {t.panel.observed} {formatValue(c.observed, c.unit, locale)}
                          {c.iso_zone ? ` · ${t.panel.zone(c.iso_zone)}` : ""}
                        </span>
                      </li>
                    ))}
                  </ul>
                  {info.length ? (
                    <details>
                      <summary className="cursor-pointer text-2xs font-medium text-muted-foreground">
                        {t.panel.informational} ({info.length})
                      </summary>
                      <ul className="mt-1 flex flex-col gap-0.5 text-2xs text-muted-foreground">
                        {info.map((c, i) => (
                          <li key={`${c.rule}-${i}`}>
                            <ApiText>{c.rule}</ApiText>
                            {c.note ? (
                              <>
                                {" — "}
                                <ApiText>{c.note}</ApiText>
                              </>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    </details>
                  ) : null}
                  {h.risk_score != null ? <p className="text-2xs text-muted-foreground"><ApiText>{h.risk_meaning}</ApiText></p> : null}
                  <Link href={`/demo/maintenance/equipment?equipment_id=${eq.id}`} className="text-2xs text-accent-text underline underline-offset-2">
                    {t.panel.openEquipment}
                  </Link>
                </div>
              );
            }}
          </QueryState>
        </div>
      ) : null}
    </li>
  );
}

function SensorTrend({ equipment, variables }: { equipment: Equipment[]; variables: Variable[] }) {
  const t = useT(messages);
  const rank = (s: string) => (s === "critical" ? 3 : s === "warning" ? 2 : s === "normal" ? 0 : 1);
  // Sensor-level variables carry the equipment code as prefix (e.g. PRS-03-VIB-DE).
  const sensorVars = useMemo(() => variables.filter((v) => equipment.some((e) => v.key.startsWith(`${e.code}-`))), [variables, equipment]);
  const worstEq = [...equipment].sort((a, b) => HEALTH_RANK[b.health_state as HealthState] - HEALTH_RANK[a.health_state as HealthState] || (b.risk_score ?? 0) - (a.risk_score ?? 0))[0];
  // Default sensor: worst state first, then the riskiest equipment, then vibration (the PRS-03 tour signal).
  const score = (v: Variable) => rank(v.status) * 10 + (worstEq && v.key.startsWith(`${worstEq.code}-`) ? 5 : 0) + (v.key.includes("VIB") ? 1 : 0);
  const defaultKey = [...sensorVars].sort((a, b) => score(b) - score(a))[0]?.key;
  const [picked, setPicked] = useState<string | null>(null);
  const key = picked && sensorVars.some((v) => v.key === picked) ? picked : defaultKey;
  const eq = equipment.find((e) => key?.startsWith(`${e.code}-`));
  const q = useApiQuery(
    "/api/v1/maintenance/equipment/{equipment_id}/sensors",
    { params: { path: { equipment_id: eq?.id ?? 0 }, query: { sensor_codes: key ? [key] : undefined, resolution: "hour", agg: "max" } } },
    { enabled: !!eq && !!key },
  );
  if (!key || !eq) return null;
  const lim = q.data?.limits?.[key];
  const thresholds: Threshold[] = [];
  if (lim?.warn_limit != null) thresholds.push({ value: lim.warn_limit, label: t.panel.warn, tone: "warning" });
  if (lim?.crit_limit != null) thresholds.push({ value: lim.crit_limit, label: t.panel.crit, tone: "critical" });
  return (
    <TimeSeriesChart
      title={t.panel.sensorTrend(key)}
      series={q.data?.series}
      normalRange={q.data?.normal_ranges[key]}
      thresholds={thresholds}
      anomalies={(q.data?.anomaly_markers ?? []).map((m) => ({ t: m.peak_ts ?? m.start_ts, label: m.code }))}
      loading={q.isPending}
      error={q.error}
      empty={q.isSuccess && q.data.series.every((s) => s.points.length === 0)}
      height={220}
      actions={
        <Select value={key} onValueChange={setPicked}>
          <SelectTrigger size="sm" className="w-44" aria-label={t.panel.pickSensor}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {sensorVars.map((v) => (
              <SelectItem key={v.key} value={v.key}>
                {v.key}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      }
    />
  );
}

/** Side panel for one stage (GET /process/stages/{code}): equipment + criteria, KPIs, sensors, trends, alerts, recommendations. */
export function StagePanel({ code, name }: { code: StageCode; name: string }) {
  const t = useT(messages);
  const te = useT(exec);
  const { locale } = useLocale();
  const [alertId, setAlertId] = useState<number | null>(null);
  const q = useApiQuery("/api/v1/process/stages/{stage_code}", { params: { path: { stage_code: code } } });
  return (
    <Section id="twin-panel" title={t.panel.title(name)} actions={q.data ? <AlertBadge state={q.data.stage.status} count={q.data.stage.active_alerts} /> : null}>
      <QueryState query={q}>
        {(d) => (
          <div className="flex min-w-0 flex-col gap-4">
            {d.equipment.length ? (
              <div>
                <h3 className="text-xs font-semibold">{t.panel.equipment}</h3>
                <ul className="divide-y divide-border">
                  {[...d.equipment]
                    .sort((a, b) => HEALTH_RANK[b.health_state as HealthState] - HEALTH_RANK[a.health_state as HealthState])
                    .map((e) => (
                      <EquipmentRow key={`${code}-${e.id}`} eq={e} />
                    ))}
                </ul>
                <Disclaimer kind="riskScore" className="mt-1 text-2xs" />
              </div>
            ) : null}
            {d.kpis.length ? (
              <div>
                <h3 className="mb-2 text-xs font-semibold">{t.panel.kpis}</h3>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {d.kpis.map((k) => (
                    <KpiCard key={k.key} kpi={k} className="p-3" />
                  ))}
                </div>
              </div>
            ) : null}
            <SensorTrend equipment={d.equipment} variables={d.variables} />
            {d.variables.length ? (
              <div className="relative overflow-x-auto" tabIndex={0} role="region" aria-label={t.panel.sensors}>
                <table className="w-full min-w-[30rem] text-xs">
                  <caption className="mb-1 text-left text-xs font-semibold">{t.panel.sensors}</caption>
                  <thead>
                    <tr className="border-b border-border text-left text-muted-foreground">
                      <th scope="col" className="py-1 pr-2 font-medium">{t.panel.variable}</th>
                      <th scope="col" className="py-1 pr-2 text-right font-medium">{t.panel.value}</th>
                      <th scope="col" className="py-1 pr-2 text-right font-medium">{t.panel.normal}</th>
                      <th scope="col" className="py-1 font-medium">{t.panel.state}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.variables.map((v) => (
                      <tr key={v.key} className="border-b border-border/60">
                        <th scope="row" className="py-1 pr-2 text-left font-normal">
                          <span className="font-mono text-2xs">{v.key}</span>
                          <span className="block text-2xs text-muted-foreground">
                            <ApiText>{v.label}</ApiText>
                          </span>
                        </th>
                        <td className="tabular py-1 pr-2 text-right">
                          <span className="inline-flex items-center gap-1">
                            {formatValue(v.value.value, v.value.unit, locale)}
                            <ProvenanceBadge provenance={v.value.provenance} compact />
                          </span>
                        </td>
                        <td className="tabular py-1 pr-2 text-right" title={v.normal_range?.basis}>
                          {v.normal_range ? `${formatNumber(v.normal_range.low ?? null, locale)} – ${formatNumber(v.normal_range.high ?? null, locale)}` : t.panel.none}
                        </td>
                        <td className={cn("py-1", v.status === "critical" ? "font-semibold text-critical-fg" : v.status === "warning" ? "font-semibold text-warning-fg" : "text-muted-foreground")}>
                          {statusWord(t.panel.statusWord, v.status)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
            {d.trends.length ? (
              <div className="grid grid-cols-1 gap-4 2xl:grid-cols-2">
                {d.trends.map((s) => (
                  <TimeSeriesChart key={s.key} title={`${t.panel.trend}: ${s.label}`} series={[s]} height={180} timeStyle="datetime" actions={<ProvenanceBadge provenance={s.provenance} compact />} />
                ))}
              </div>
            ) : null}
            <div>
              <h3 className="mb-1 text-xs font-semibold">{t.panel.alertsTitle}</h3>
              {d.alerts.length === 0 ? (
                <p className="text-xs text-muted-foreground">{t.panel.noAlerts}</p>
              ) : (
                <ul className="flex flex-col gap-1.5">
                  {d.alerts.map((a) => (
                    <li key={a.id} className="flex flex-wrap items-center gap-1.5 text-xs">
                      <SeverityPill severity={a.severity} />
                      <Badge tone="outline">{alertSourceKind(a.source) === "rule" ? te.alerts.sourceRule : te.alerts.sourceMl}</Badge>
                      <button type="button" className="min-w-0 flex-1 text-left underline-offset-2 hover:underline" onClick={() => setAlertId(a.id)}>
                        <ApiText>{a.title}</ApiText>
                      </button>
                      <span className="text-2xs text-muted-foreground">{formatDate(a.raised_at, locale, "datetime")}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <h3 className="mb-1 text-xs font-semibold">{t.panel.recsTitle}</h3>
              {d.recommendations.length === 0 ? (
                <p className="text-xs text-muted-foreground">{t.panel.noRecs}</p>
              ) : (
                <ul className="flex flex-col gap-1.5">
                  {d.recommendations.slice(0, 5).map((r) => (
                    <li key={r.id} className="rounded-md border border-border p-2 text-xs">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <SeverityPill severity={r.priority} />
                        <span className="font-medium">
                          <ApiText>{r.title}</ApiText>
                        </span>
                      </div>
                      <p className="mt-0.5 text-2xs text-muted-foreground">
                        {t.panel.recCreated} {formatDate(r.created_at, locale, "datetime")} · <ApiText>{r.advisory_notice}</ApiText>
                      </p>
                    </li>
                  ))}
                </ul>
              )}
              <Disclaimer kind="advisory" className="mt-1 text-2xs" />
            </div>
          </div>
        )}
      </QueryState>
      <AlertDetailDialog alertId={alertId} onOpenChange={(v) => !v && setAlertId(null)} />
    </Section>
  );
}
