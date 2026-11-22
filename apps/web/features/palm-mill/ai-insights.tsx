"use client";

import { useState } from "react";
import Link from "next/link";
import { ShieldAlert } from "lucide-react";
import type { Schema } from "@dml/contracts";
import { useApiMutation, useApiQuery } from "@/lib/api/hooks";
import { isApiRequestError } from "@/lib/api/errors";
import { useDemo } from "@/lib/demo/context";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatDate, formatNumber, formatSigned, formatValue } from "@/lib/format";
import { cn } from "@/lib/utils";
import { OperationsLayout } from "@/components/layouts/layouts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toast";
import { ProvenanceBadge } from "@/components/demo/provenance-badge";
import { Disclaimer } from "@/components/demo/disclaimer";
import { EvidencePanel } from "@/components/data/evidence-panel";
import { ConfirmDialog } from "@/components/data/confirm-dialog";
import { AreaBandChart } from "@/components/charts/charts";
import { EmptyState, QueryState } from "@/components/states/states";
import { SeverityPill } from "@/features/executive/shared/sev";
import { ApiText, Section } from "@/features/executive/shared/section";
import messages from "./palm-mill.i18n";

type Anomaly = Schema<"AnomalyOut">;
type AnomalyStatus = Schema<"AnomalyStatus">;
type ModelInfo = Schema<"ModelInfo">;

const ACTIONS: AnomalyStatus[] = ["acknowledged", "verified", "dismissed"];

function VerifyActions({ a }: { a: Anomaly }) {
  const t = useT(messages);
  const m = useApiMutation("/api/v1/ai/anomalies/{anomaly_id}/status", {
    invalidate: ["/api/v1/ai/anomalies/production", "/api/v1/ai/anomalies/equipment"],
  });
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-2xs text-muted-foreground">{t.ai.verification}:</span>
      <Badge tone={a.status === "verified" ? "critical" : a.status === "dismissed" ? "outline" : a.status === "acknowledged" ? "info" : "neutral"}>{t.ai.status[a.status]}</Badge>
      {ACTIONS.filter((s) => s !== a.status).map((to) => (
        <ConfirmDialog
          key={to}
          trigger={
            <Button size="xs" variant="outline">
              {t.ai.action[to as "acknowledged" | "verified" | "dismissed"]}
            </Button>
          }
          title={t.ai.confirmTitle(t.ai.action[to as "acknowledged" | "verified" | "dismissed"])}
          description={t.ai.confirmBody(a.code, t.ai.status[a.status], t.ai.status[to])}
          onConfirm={async () => {
            try {
              await m.mutateAsync({ params: { path: { anomaly_id: a.id } }, body: { to_status: to } });
              toast.success(t.ai.changed);
            } catch (e) {
              toast.error(isApiRequestError(e) && e.isForbidden ? t.ai.forbidden : t.ai.failed, {
                description: isApiRequestError(e) && !e.isForbidden ? e.message : undefined,
              });
              throw e;
            }
          }}
        />
      ))}
    </div>
  );
}

function AnomalyCard({ a, tour }: { a: Anomaly; tour?: boolean }) {
  const t = useT(messages);
  const { locale } = useLocale();
  const who = a.equipment?.code ?? a.entity?.code ?? a.process_stage_code ?? "";
  return (
    <li className="flex flex-col gap-3 rounded-lg border border-border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <SeverityPill severity={a.severity} />
        <span className="font-mono text-xs font-semibold">{a.code}</span>
        {who ? <Badge tone="outline">{who}</Badge> : null}
        <span className="tabular ml-auto text-xs" title={t.ai.scoreNote}>
          {t.ai.score} <span className="font-semibold">{formatNumber(a.score, locale, { digits: 2 })}</span>
        </span>
      </div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
        <dt className="text-muted-foreground">{t.ai.window}</dt>
        <dd>
          {formatDate(a.start_ts, locale, "datetime")} – {a.end_ts ? formatDate(a.end_ts, locale, "datetime") : t.ai.ongoing}
        </dd>
        {a.peak_ts ? (
          <>
            <dt className="text-muted-foreground">{t.ai.peak}</dt>
            <dd>{formatDate(a.peak_ts, locale, "datetime")}</dd>
          </>
        ) : null}
        <dt className="text-muted-foreground">{t.ai.detector}</dt>
        <dd className="font-mono text-2xs">
          {a.detector}
          {a.model_version ? ` · ${a.model_version}` : ""}
        </dd>
        {a.contributing_sensors?.length ? (
          <>
            <dt className="text-muted-foreground">{t.ai.sensors}</dt>
            <dd className="font-mono text-2xs">{a.contributing_sensors.join(", ")}</dd>
          </>
        ) : null}
      </dl>
      <div data-tour={tour ? "palm-anomaly-evidence" : undefined}>
        <EvidencePanel evidence={a.evidence} factors={a.contributing_factors ?? []} />
      </div>
      {a.recommended_investigation?.length ? (
        <div>
          <h4 className="text-xs font-semibold">{t.ai.investigate}</h4>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs">
            {a.recommended_investigation.map((r) => (
              <li key={r}>
                <ApiText>{r}</ApiText>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <VerifyActions a={a} />
    </li>
  );
}

function AnomalyList({ items, none, tourFirst }: { items: Anomaly[]; none: string; tourFirst: boolean }) {
  const t = useT(messages);
  const [all, setAll] = useState(false);
  if (!items.length) return <EmptyState compact title={none} body={t.ai.scoreNote} />;
  const shown = all ? items : items.slice(0, 3);
  return (
    <>
      <ul className="flex flex-col gap-3">
        {shown.map((a, i) => (
          <AnomalyCard key={a.id} a={a} tour={tourFirst && i === 0} />
        ))}
      </ul>
      {items.length > 3 ? (
        <Button variant="ghost" size="xs" className="self-start" onClick={() => setAll((v) => !v)}>
          {all ? t.ai.less : t.ai.more(items.length - 3)}
        </Button>
      ) : null}
    </>
  );
}

function Detectors() {
  const t = useT(messages);
  const { period } = useDemo();
  const eq = useApiQuery("/api/v1/ai/anomalies/equipment", { params: { query: { period, limit: 50 } } });
  const pr = useApiQuery("/api/v1/ai/anomalies/production", { params: { query: { period, limit: 50 } } });
  const eqItems = eq.data?.items ?? [];
  const prItems = pr.data?.items ?? [];
  // The tour highlights the first evidence panel that exists (production first, else equipment).
  const tourOnProduction = prItems.length > 0;
  return (
    <Section id="ai-detectors" title={t.ai.lead} description={t.ai.leadDesc}>
      <div className="grid grid-cols-1 gap-5 2xl:grid-cols-2">
        <div className="flex min-w-0 flex-col gap-2">
          <h3 className="text-sm font-semibold">{t.ai.production}</h3>
          <QueryState query={pr} compact>
            {(d) => <AnomalyList items={d.items} none={t.ai.noneProduction} tourFirst={tourOnProduction} />}
          </QueryState>
        </div>
        <div className="flex min-w-0 flex-col gap-2">
          <h3 className="text-sm font-semibold">{t.ai.equipment}</h3>
          <QueryState query={eq} compact>
            {(d) => <AnomalyList items={d.items} none={t.ai.noneEquipment} tourFirst={!tourOnProduction && eqItems.length > 0} />}
          </QueryState>
        </div>
      </div>
      <Disclaimer kind="advisory" />
    </Section>
  );
}

function ObservedDrivers() {
  const t = useT(messages);
  const { locale } = useLocale();
  const q = useApiQuery("/api/v1/production/process-state");
  return (
    <Section id="ai-observed" title={t.ai.observed} description={t.ai.observedDesc} actions={q.data ? <span className="text-2xs text-muted-foreground">{formatDate(q.data.ts, locale, "datetime")}</span> : null}>
      <QueryState query={q} compact>
        {(d) => {
          const off = d.variables.filter((v) => v.status !== "normal");
          if (!off.length) return <p className="text-xs text-muted-foreground">{t.ai.allNormal}</p>;
          return (
            <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {off.map((v) => (
                <li key={v.key} className={cn("rounded-md border p-2 text-xs", v.status === "critical" ? "border-critical/40 bg-critical-soft/40" : "border-warning/40 bg-warning-soft/40")}>
                  <p className="font-medium">
                    <ApiText>{v.label}</ApiText>
                  </p>
                  <p className="tabular mt-0.5 flex flex-wrap items-center gap-1">
                    <span className="font-semibold">{formatValue(v.value.value, v.value.unit, locale)}</span>
                    <ProvenanceBadge provenance={v.value.provenance} compact />
                    {v.normal_range ? (
                      <span className="text-muted-foreground" title={v.normal_range.basis}>
                        ({formatNumber(v.normal_range.low ?? null, locale)} – {formatNumber(v.normal_range.high ?? null, locale)})
                      </span>
                    ) : null}
                  </p>
                  <p className={cn("mt-0.5 text-2xs font-semibold", v.status === "critical" ? "text-critical-fg" : "text-warning-fg")}>
                    {(t.panel.statusWord as Readonly<Record<string, string>>)[v.status] ?? v.status}
                  </p>
                </li>
              ))}
            </ul>
          );
        }}
      </QueryState>
    </Section>
  );
}

function MetricsTable({ model }: { model: ModelInfo }) {
  const t = useT(messages);
  const { locale } = useLocale();
  return (
    <div className="relative overflow-x-auto" tabIndex={0} role="region" aria-label={t.ai.card}>
      <table className="w-full min-w-[28rem] text-xs">
        <caption className="sr-only">{t.ai.card}</caption>
        <thead>
          <tr className="border-b border-border text-left text-muted-foreground">
            <th scope="col" className="py-1 pr-2 font-medium">{t.ai.metric}</th>
            <th scope="col" className="py-1 pr-2 text-right font-medium">{t.ai.model}</th>
            <th scope="col" className="py-1 pr-2 text-right font-medium">{t.ai.baseline}</th>
            <th scope="col" className="py-1 font-medium" />
          </tr>
        </thead>
        <tbody>
          {model.metrics.map((m) => (
            <tr key={m.name} className="border-b border-border/60">
              <th scope="row" className="py-1 pr-2 text-left font-mono font-normal">{m.name}</th>
              <td className="tabular py-1 pr-2 text-right">{formatNumber(m.model, locale, { digits: 3 })}</td>
              <td className="tabular py-1 pr-2 text-right">
                {formatNumber(m.baseline ?? null, locale, { digits: 3 })}
                {m.baseline_name ? <span className="ml-1 font-mono text-2xs text-muted-foreground">{m.baseline_name}</span> : null}
              </td>
              <td className="py-1">
                {m.beats_baseline == null ? (
                  <span className="text-muted-foreground">{t.ai.na}</span>
                ) : (
                  <Badge tone={m.beats_baseline ? "success" : "warning"}>{m.beats_baseline ? t.ai.beats : t.ai.loses}</Badge>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-2xs text-muted-foreground">
        <dt>{t.ai.version}</dt>
        <dd className="font-mono">
          {model.name}@{model.version} · {model.algorithm}
        </dd>
        <dt>{t.ai.trainWindow}</dt>
        <dd>{model.train_window.map((x) => formatDate(x, locale)).join(" – ")}</dd>
        <dt>{t.ai.testWindow}</dt>
        <dd>{model.test_window.map((x) => formatDate(x, locale)).join(" – ")}</dd>
        <dt>{t.ai.dataKind}</dt>
        <dd>{model.data_kind}</dd>
      </dl>
    </div>
  );
}

function OerSection() {
  const t = useT(messages);
  const { locale } = useLocale();
  const fc = useApiQuery("/api/v1/ai/oer/forecast");
  const ex = useApiQuery("/api/v1/ai/oer/explanation");
  const n = ex.data?.nowcast;
  return (
    <>
      <Section id="ai-nowcast" title={t.ai.nowcast} description={t.ai.nowcastDesc}>
        <QueryState query={ex} compact isEmpty={(d) => !d.nowcast}>
          {(d) =>
            n ? (
              <>
                <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5">
                  {(
                    [
                      [t.ai.actual, formatValue(n.actual_oer_pct, "%", locale, { digits: 2 }), "synthetic_actual"],
                      [t.ai.expected, formatValue(n.expected_oer_pct, "%", locale, { digits: 2 }), "forecast"],
                      [t.ai.typical, formatValue(n.typical_conditions_oer_pct ?? null, "%", locale, { digits: 2 }), "forecast"],
                      [t.ai.residual, n.residual_pp != null ? `${formatSigned(n.residual_pp, locale, 2)} pp` : "—", "forecast"],
                      [t.ai.band, n.residual_band_pp != null ? `± ${formatNumber(n.residual_band_pp, locale, { digits: 2 })} pp` : "—", "forecast"],
                    ] as const
                  ).map(([label, value, kind]) => (
                    <div key={label} className="rounded-lg bg-surface-2 p-2.5">
                      <dt className="text-2xs text-muted-foreground">{label}</dt>
                      <dd className="tabular flex flex-wrap items-center gap-1 text-sm font-semibold">
                        {value}
                        <ProvenanceBadge
                          provenance={{ kind, source: kind === "synthetic_actual" ? "process_hourly" : "oer nowcast (ridge)", as_of: n.period_end, model_version: kind === "forecast" ? `${d.model.name}@${d.model.version}` : null }}
                          compact
                        />
                      </dd>
                    </div>
                  ))}
                </dl>
                {n.outside_band != null ? (
                  <p className={cn("text-xs font-semibold", n.outside_band ? "text-critical-fg" : "text-success-fg")}>{n.outside_band ? t.ai.outside : t.ai.inside}</p>
                ) : null}
                <p className="text-2xs text-muted-foreground">
                  <ApiText>{n.note}</ApiText>
                </p>
                {n.contributions?.length ? (
                  <details className="rounded-md border border-dashed border-warning/60 p-2">
                    <summary className="flex cursor-pointer items-center gap-1.5 text-xs font-semibold text-warning-fg">
                      <ShieldAlert className="size-3.5" aria-hidden /> {t.ai.attribution}
                    </summary>
                    <p className="mt-1 text-2xs text-warning-fg">{t.ai.attributionWarn}</p>
                    <div className="relative mt-2 overflow-x-auto" tabIndex={0} role="region" aria-label={t.ai.attribution}>
                      <table className="w-full min-w-[26rem] text-xs">
                        <thead>
                          <tr className="border-b border-border text-left text-muted-foreground">
                            <th scope="col" className="py-1 pr-2 font-medium">{t.ai.feature}</th>
                            <th scope="col" className="py-1 pr-2 text-right font-medium">{t.ai.value}</th>
                            <th scope="col" className="py-1 text-right font-medium">{t.ai.contribution}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {n.contributions.map((c) => (
                            <tr key={c.feature} className="border-b border-border/60">
                              <th scope="row" className="py-1 pr-2 text-left font-normal">
                                <ApiText>{c.label}</ApiText>
                              </th>
                              <td className="tabular py-1 pr-2 text-right">{formatNumber(c.value, locale)}</td>
                              <td className="tabular py-1 text-right">{c.contribution != null ? formatSigned(c.contribution, locale, 2) : "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <p className="mt-1 text-2xs text-muted-foreground">
                      <ApiText>{d.caveat}</ApiText>
                    </p>
                  </details>
                ) : null}
              </>
            ) : null
          }
        </QueryState>
      </Section>

      <Section id="ai-forecast" title={t.ai.forecast} description={t.ai.forecastDesc}>
        <AreaBandChart
          title={t.ai.forecast}
          band={fc.data?.forecast}
          actual={fc.data?.actual}
          baseline={fc.data?.baseline}
          loading={fc.isPending}
          error={fc.error}
          onRetry={() => void fc.refetch()}
          actions={fc.data ? <ProvenanceBadge provenance={fc.data.forecast.provenance} /> : null}
        />
        {fc.data?.granularity_note ? (
          <p className="rounded-md bg-warning-soft/50 p-2 text-xs text-warning-fg">
            <ApiText>{fc.data.granularity_note}</ApiText>
          </p>
        ) : null}
        {fc.data ? (
          <div>
            <h3 className="mb-1 text-xs font-semibold">{t.ai.card}</h3>
            <MetricsTable model={fc.data.model} />
          </div>
        ) : null}
        <Link href="/docs/ai-methodology" className="self-start text-xs text-accent-text underline underline-offset-2">
          {t.ai.methodology}
        </Link>
      </Section>
    </>
  );
}

/** AI insights (AI-B01/B02): detectors first, observed conditions, then the honest OER nowcast/forecast view. */
export function AiInsights() {
  return (
    <OperationsLayout route="/demo/palm-mill/ai-insights">
      <Detectors />
      <ObservedDrivers />
      <OerSection />
    </OperationsLayout>
  );
}
