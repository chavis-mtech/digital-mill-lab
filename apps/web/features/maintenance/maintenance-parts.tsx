"use client";

/** Building blocks shared by the maintenance overview and equipment pages. */
import { useMemo, useState } from "react";
import Link from "next/link";
import { Check, ClipboardPlus, ThumbsDown } from "lucide-react";
import type { Schema } from "@dml/contracts";
import { useApiMutation, useApiQuery } from "@/lib/api/hooks";
import { isApiRequestError } from "@/lib/api/errors";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatDate, formatNumber, formatValue } from "@/lib/format";
import { AlertBadge } from "@/components/demo/severity";
import { ProvenanceBadge } from "@/components/demo/provenance-badge";
import { Disclaimer } from "@/components/demo/disclaimer";
import { EvidencePanel } from "@/components/data/evidence-panel";
import { ConfirmDialog } from "@/components/data/confirm-dialog";
import { QueryState } from "@/components/states/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toast";
import { ApiText, Field, NativeInput, OpsSeverityPill, RoleGate, Section, usePermissions } from "./shared/ops-ui";
import { recommendationOrigin } from "./helpers";
import messages from "./maintenance.i18n";

type Health = Schema<"EquipmentHealth">;
type Reco = Schema<"RecommendationOut">;

function errText(e: unknown) {
  return isApiRequestError(e) ? e.message : e instanceof Error ? e.message : String(e);
}

/** The "relative index, not a probability" text — mandatory next to every risk number. */
export function RiskNotice({ className }: { className?: string }) {
  const t = useT(messages);
  return (
    <div className={className}>
      <p className="text-xs font-medium text-foreground">{t.common.relativeIndex}</p>
      <Disclaimer kind="riskScore" className="mt-1" />
    </div>
  );
}

/** Explicit criteria that produced a health state (AI-C01): never just a colour. */
export function HealthCriteria({ health }: { health: Health }) {
  const t = useT(messages);
  const { locale } = useLocale();
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <AlertBadge state={health.state} />
        <ProvenanceBadge provenance={health.provenance} />
        {health.health_rules_version ? <span className="font-mono text-2xs text-subtle-foreground">{health.health_rules_version}</span> : null}
      </div>
      <div>
        <p className="text-2xs font-semibold text-muted-foreground uppercase">{t.equipment.triggered}</p>
        {health.triggered_by && health.triggered_by.length > 0 ? (
          <ul className="mt-1 list-disc pl-5 text-xs">
            {health.triggered_by.map((x) => (
              <li key={x}>
                <ApiText>{x}</ApiText>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-xs text-muted-foreground">{t.equipment.noTrigger}</p>
        )}
      </div>
      {health.state_rule ? (
        <div className="rounded-lg bg-surface-2 p-3">
          <p className="text-2xs font-semibold text-muted-foreground uppercase">{t.equipment.howRule}</p>
          <p lang="en" className="mt-1 text-xs leading-relaxed">
            {health.state_rule}
          </p>
        </div>
      ) : null}
      <div className="relative overflow-x-auto rounded-lg border border-border" tabIndex={0} role="region" aria-label={t.equipment.criteriaTitle}>
        <table className="tabular w-full border-collapse text-left text-xs">
          <caption className="sr-only">{t.equipment.criteriaTitle}</caption>
          <thead className="bg-surface-2 text-muted-foreground">
            <tr>
              {[t.equipment.colSensor, t.equipment.colRule, t.equipment.colObserved, t.equipment.colLimit, t.equipment.colBreached, t.equipment.colWindow, t.equipment.colSamples, t.equipment.colZone, t.equipment.colAffects].map((h) => (
                <th key={h} scope="col" className="border-b border-border px-2.5 py-2 font-semibold whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {health.criteria.map((c, i) => (
              <tr key={`${c.sensor_code}-${i}`} className="border-b border-border last:border-0 align-top">
                <td className="px-2.5 py-2 font-mono whitespace-nowrap">{c.sensor_code}</td>
                <td className="min-w-56 px-2.5 py-2" lang="en">
                  {c.rule}
                  {c.note ? <span className="block text-muted-foreground">{c.note}</span> : null}
                </td>
                <td className={`px-2.5 py-2 font-semibold whitespace-nowrap ${c.breached ? "text-critical-fg" : ""}`}>{formatValue(c.observed, c.unit, locale)}</td>
                <td className="px-2.5 py-2 whitespace-nowrap">{formatValue(c.limit, c.unit, locale)}</td>
                <td className="px-2.5 py-2 whitespace-nowrap">
                  <Badge tone={c.breached ? "critical" : "success"}>{c.breached ? t.equipment.breachedYes : t.equipment.breachedNo}</Badge>
                </td>
                <td className="px-2.5 py-2 whitespace-nowrap">{c.window_min != null && c.window_max != null ? `${formatNumber(c.window_min, locale)} – ${formatNumber(c.window_max, locale)}` : "—"}</td>
                <td className="px-2.5 py-2 whitespace-nowrap">{c.samples_in_breach != null && c.samples_evaluated != null ? `${c.samples_in_breach}/${c.samples_evaluated}` : "—"}</td>
                <td className="px-2.5 py-2">{c.iso_zone ?? "—"}</td>
                <td className="px-2.5 py-2 whitespace-nowrap">{c.affects_state === false ? t.equipment.no : t.equipment.yes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {health.data_quality_notes && health.data_quality_notes.length > 0 ? (
        <div>
          <p className="text-2xs font-semibold text-muted-foreground uppercase">{t.equipment.dataQuality}</p>
          <ul className="mt-1 list-disc pl-5 text-xs text-muted-foreground">
            {health.data_quality_notes.map((n) => (
              <li key={n} lang="en">
                {n}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

/** Failure-risk index with components, meaning and limits (AI-C03). */
export function RiskBreakdown({ health }: { health: Health }) {
  const t = useT(messages);
  const { locale } = useLocale();
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <p className="tabular text-3xl leading-none font-semibold">
          {formatNumber(health.risk_score ?? null, locale, { digits: 1 })}
          <span className="ml-1 text-sm font-medium text-muted-foreground">/ 100</span>
        </p>
        {health.risk_band ? (
          <Badge tone="outline">
            {t.equipment.riskBand}: <span lang="en">{health.risk_band.replace(/_/g, " ")}</span>
          </Badge>
        ) : null}
        <ProvenanceBadge provenance={health.provenance} />
      </div>
      <RiskNotice />
      {health.risk_meaning ? (
        <p lang="en" className="text-xs text-muted-foreground">
          <span className="font-semibold text-foreground">{t.equipment.riskMeaning}: </span>
          {health.risk_meaning}
        </p>
      ) : null}
      {health.risk_limits ? (
        <p lang="en" className="text-xs text-muted-foreground">
          <span className="font-semibold text-foreground">{t.equipment.riskLimits}: </span>
          {health.risk_limits}
        </p>
      ) : null}
      {health.risk_components && health.risk_components.length > 0 ? (
        <div className="relative overflow-x-auto rounded-lg border border-border" tabIndex={0} role="region" aria-label={t.equipment.riskComponents}>
          <table className="tabular w-full border-collapse text-left text-xs">
            <caption className="sr-only">{t.equipment.riskComponents}</caption>
            <thead className="bg-surface-2 text-muted-foreground">
              <tr>
                {[t.equipment.colComponent, t.equipment.colWeight, t.equipment.colSub, t.equipment.colPoints, t.equipment.colBasis].map((h) => (
                  <th key={h} scope="col" className="border-b border-border px-2.5 py-2 font-semibold whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {health.risk_components.map((c) => (
                <tr key={c.key} className="border-b border-border last:border-0 align-top">
                  <th scope="row" className="px-2.5 py-2 font-medium whitespace-nowrap" lang="en">
                    {c.label}
                  </th>
                  <td className="px-2.5 py-2">{formatNumber(c.weight, locale)}</td>
                  <td className="px-2.5 py-2">{formatNumber(c.sub_score, locale, { digits: 2 })}</td>
                  <td className="px-2.5 py-2 font-semibold">{formatNumber(c.points, locale, { digits: 1 })}</td>
                  <td className="min-w-56 px-2.5 py-2 text-muted-foreground" lang="en">
                    {c.basis}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {health.risk_method ? (
        <p lang="en" className="font-mono text-2xs break-words text-subtle-foreground">
          {t.equipment.riskMethod}: {health.risk_method}
        </p>
      ) : null}
    </div>
  );
}

/** ML anomaly events with evidence, contributing factors and the human-verification status (AI-C02). */
export function AnomalyEvidence({ equipmentId, limit = 6, tour }: { equipmentId?: number | null; limit?: number; tour?: string }) {
  const t = useT(messages);
  const { locale } = useLocale();
  const q = useApiQuery("/api/v1/ai/anomalies/equipment", { params: { query: { period: "30d", limit, ...(equipmentId ? { equipment_id: equipmentId } : {}) } } });
  const [pick, setPick] = useState<number | null>(null);
  return (
    <QueryState query={q} isEmpty={(d) => d.items.length === 0} empty={<p className="text-xs text-muted-foreground">{t.overview.anomalyNone}</p>} compact>
      {(d) => {
        const items = [...d.items].sort((a, b) => Date.parse(b.peak_ts ?? b.start_ts) - Date.parse(a.peak_ts ?? a.start_ts));
        const selected = items.find((a) => a.id === pick) ?? [...items].sort((a, b) => b.score - a.score)[0]!;
        return (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]" data-tour={tour}>
            <ul className="flex max-h-80 flex-col gap-1.5 overflow-y-auto" aria-label={t.overview.anomalyPick}>
              {items.map((a) => (
                <li key={a.id}>
                  <button
                    type="button"
                    aria-pressed={a.id === selected.id}
                    onClick={() => setPick(a.id)}
                    className={`flex w-full flex-col gap-1 rounded-lg border px-3 py-2 text-left text-xs transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none ${a.id === selected.id ? "border-accent bg-accent-soft/40" : "border-border hover:bg-surface-2"}`}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="font-mono font-semibold">{a.equipment?.code ?? a.code}</span>
                      <OpsSeverityPill severity={a.severity} />
                    </span>
                    <span className="tabular text-muted-foreground">{formatDate(a.peak_ts ?? a.start_ts, locale, "datetime")}</span>
                    <span className="tabular">
                      {t.overview.anomalyScore}: <b>{formatNumber(a.score, locale, { digits: 2 })}</b>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            <div className="flex min-w-0 flex-col gap-3">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="font-mono font-semibold">{selected.code}</span>
                <ProvenanceBadge kind="synthetic_actual" />
                <Badge tone="outline">
                  {t.overview.anomalyDetector}: <span lang="en">{selected.detector}</span>
                </Badge>
                <Badge tone="info">
                  {t.overview.anomalyStatus}: <span lang="en">{selected.status}</span>
                </Badge>
                {selected.model_version ? <span className="font-mono text-2xs text-subtle-foreground">{selected.model_version}</span> : null}
              </div>
              <EvidencePanel evidence={selected.evidence} factors={selected.contributing_factors} />
              {selected.contributing_sensors && selected.contributing_sensors.length > 0 ? (
                <p className="text-xs text-muted-foreground">
                  {t.overview.anomalySensors}: <span className="font-mono">{selected.contributing_sensors.join(", ")}</span>
                </p>
              ) : null}
              {selected.recommended_investigation && selected.recommended_investigation.length > 0 ? (
                <div>
                  <p className="text-2xs font-semibold text-muted-foreground uppercase">{t.overview.anomalyInvestigate}</p>
                  <ul className="mt-1 list-disc pl-5 text-xs">
                    {selected.recommended_investigation.map((x) => (
                      <li key={x} lang="en">
                        {x}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          </div>
        );
      }}
    </QueryState>
  );
}

const STATUS_TONE: Record<string, "info" | "success" | "critical" | "neutral"> = { proposed: "info", approved: "success", rejected: "critical", superseded: "neutral" };

/** One advisory recommendation with evidence and the human approve / reject / create-WO decision. */
export function RecommendationCard({ rec, tour, defaultOpen = false }: { rec: Reco; tour?: string; defaultOpen?: boolean }) {
  const t = useT(messages);
  const { locale } = useLocale();
  const perms = usePermissions();
  const canDecide = perms.can("recommendation:decide");
  const [open, setOpen] = useState<null | "approve" | "approve_wo" | "reject">(null);
  const [note, setNote] = useState("");
  const [showEvidence, setShowEvidence] = useState(defaultOpen);
  const decide = useApiMutation("/api/v1/maintenance/recommendations/{recommendation_id}/decision", {
    invalidate: ["/api/v1/maintenance/recommendations", "/api/v1/work-orders", "/api/v1/maintenance/equipment", "/api/v1/alerts"],
  });
  const label = open === "reject" ? t.overview.reject : open === "approve_wo" ? t.overview.approveWo : t.overview.approve;

  async function run() {
    if (!open) return;
    try {
      const res = await decide.mutateAsync({
        params: { path: { recommendation_id: rec.id } },
        body: { decision: open === "reject" ? "rejected" : "approved", note: note.trim() || null, create_work_order: open === "approve_wo" },
      });
      toast.success(res.work_order_id ? t.overview.woCreated(`#${res.work_order_id}`) : t.overview.decisionDone);
      setNote("");
    } catch (e) {
      toast.error(t.overview.decisionFailed, { description: errText(e) });
    }
  }

  const origin = recommendationOrigin(rec.id);
  const statusLabel: Record<string, string> = { proposed: t.overview.statusProposed, approved: t.overview.statusApproved, rejected: t.overview.statusRejected, superseded: t.overview.statusSuperseded };
  return (
    <article className="flex flex-col gap-2.5 rounded-xl border border-border bg-surface p-4" data-tour={tour} aria-label={rec.title}>
      <div className="flex flex-wrap items-center gap-1.5">
        <OpsSeverityPill severity={rec.priority} />
        <Badge tone="outline">{t.overview.recoOrigin[origin]}</Badge>
        <Badge tone={STATUS_TONE[rec.status] ?? "neutral"}>{statusLabel[rec.status] ?? rec.status}</Badge>
        {rec.equipment ? (
          <Link href={`/demo/maintenance/equipment?equipment_id=${rec.equipment.id}`} className="font-mono text-xs font-semibold text-accent-text hover:underline">
            {rec.equipment.code}
          </Link>
        ) : null}
        <span className="font-mono text-2xs text-subtle-foreground">{rec.code}</span>
        {rec.risk_score != null ? (
          <span className="tabular ml-auto text-xs">
            {t.common.risk}: <b>{formatNumber(rec.risk_score, locale, { digits: 1 })}</b>
          </span>
        ) : null}
      </div>
      <h3 className="text-sm font-semibold" lang="en">
        {rec.title}
      </h3>
      <p className="text-xs leading-relaxed text-muted-foreground" lang="en">
        {rec.rationale}
      </p>
      <p role="note" className="rounded-md border border-dashed border-warning/50 bg-warning-soft/40 px-2.5 py-1.5 text-xs font-medium text-foreground">
        {t.common.advisory}
      </p>
      {rec.corroborating_sensors && rec.corroborating_sensors.length > 0 ? (
        <p className="text-xs text-muted-foreground">
          {t.overview.recoCorroborating}: <span className="font-mono">{rec.corroborating_sensors.join(", ")}</span>
        </p>
      ) : null}
      {rec.evidence && rec.evidence.length > 0 ? (
        <>
          <Button variant="ghost" size="xs" className="self-start" aria-expanded={showEvidence} onClick={() => setShowEvidence((v) => !v)}>
            {t.overview.recoEvidence} ({rec.evidence.length})
          </Button>
          {showEvidence ? (
            <div className="flex flex-col gap-2">
              <EvidencePanel evidence={rec.evidence} title={t.overview.recoEvidence} className="border-dashed" />
              {rec.assumptions && rec.assumptions.length > 0 ? (
                <div className="rounded-lg border border-dashed border-border p-3">
                  <p className="text-2xs font-semibold text-muted-foreground uppercase">{t.overview.recoAssumptions}</p>
                  <ul className="mt-1 list-disc pl-5 text-xs text-muted-foreground">
                    {rec.assumptions.map((a) => (
                      <li key={a} lang="en">
                        {a}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : null}
        </>
      ) : null}
      <div className="flex flex-wrap items-center gap-2 border-t border-border pt-2.5">
        <ProvenanceBadge kind="synthetic_actual" />
        {rec.model_version ? <span className="font-mono text-2xs text-subtle-foreground">{rec.model_version}</span> : null}
        {rec.status === "proposed" ? (
          <div className="ml-auto flex flex-wrap items-center gap-1.5">
            <Button size="sm" variant="accent" disabled={!canDecide} onClick={() => setOpen("approve_wo")}>
              <ClipboardPlus aria-hidden /> {t.overview.approveWo}
            </Button>
            <Button size="sm" variant="outline" disabled={!canDecide} onClick={() => setOpen("approve")}>
              <Check aria-hidden /> {t.overview.approve}
            </Button>
            <Button size="sm" variant="outline" disabled={!canDecide} onClick={() => setOpen("reject")}>
              <ThumbsDown aria-hidden /> {t.overview.reject}
            </Button>
          </div>
        ) : (
          <p className="ml-auto text-xs text-muted-foreground">{t.overview.decided(statusLabel[rec.status] ?? rec.status)}</p>
        )}
      </div>
      {rec.status === "proposed" && perms.ready && !canDecide ? (
        <RoleGate allowed={false} permission="recommendation:decide" message={t.roleGate.message} switchLabel={t.roleGate.switch} />
      ) : null}
      <ConfirmDialog
        open={open !== null}
        onOpenChange={(o) => !o && setOpen(null)}
        title={t.overview.decisionTitle(label)}
        description={t.overview.decisionBody}
        details={
          <div className="flex flex-col gap-2">
            <p lang="en" className="font-medium">
              {rec.title}
            </p>
            <Field label={t.overview.decisionNote}>{(id) => <NativeInput id={id} value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />}</Field>
          </div>
        }
        onConfirm={run}
      />
    </article>
  );
}

/** MTBF / MTTR and event history for one equipment (DML-057). */
export function HistoryPanel({ equipmentId }: { equipmentId: number }) {
  const t = useT(messages);
  const { locale } = useLocale();
  const q = useApiQuery("/api/v1/maintenance/equipment/{equipment_id}/history", { params: { path: { equipment_id: equipmentId }, query: { period: "30d" } } });
  const stats = useMemo(() => (d: Schema<"MaintenanceHistoryResponse">) => [
    { k: t.equipment.historyMtbf, v: formatValue(d.mtbf_h ?? null, t.common.hours, locale) },
    { k: t.equipment.historyMttr, v: formatValue(d.mttr_h ?? null, t.common.hours, locale) },
    { k: t.equipment.historyFailures, v: formatNumber(d.failures ?? null, locale) },
    { k: t.equipment.historyDowntime, v: formatValue(d.total_downtime_h, t.common.hours, locale) },
    { k: t.equipment.historyCost, v: formatValue(d.total_cost_thb ?? null, "THB", locale) },
  ], [t, locale]);
  return (
    <QueryState query={q} compact>
      {(d) => (
        <div className="flex flex-col gap-3">
          <dl className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            {stats(d).map((s) => (
              <div key={s.k} className="rounded-lg border border-border p-2.5">
                <dt className="text-2xs text-muted-foreground">{s.k}</dt>
                <dd className="tabular text-sm font-semibold">{s.v}</dd>
              </div>
            ))}
          </dl>
          <div className="flex flex-wrap items-center gap-2 text-2xs text-muted-foreground">
            {d.provenance ? <ProvenanceBadge provenance={d.provenance} /> : null}
            {d.mtbf_basis ? (
              <span lang="en">
                {t.equipment.historyBasis}: {d.mtbf_basis}
              </span>
            ) : null}
          </div>
          {d.items.length === 0 ? (
            <p className="text-xs text-muted-foreground">{t.equipment.historyNone}</p>
          ) : (
            <div className="relative overflow-x-auto rounded-lg border border-border" tabIndex={0} role="region" aria-label={t.equipment.historyTitle}>
              <table className="tabular w-full border-collapse text-left text-xs">
                <caption className="sr-only">{t.equipment.historyTitle}</caption>
                <thead className="bg-surface-2 text-muted-foreground">
                  <tr>
                    {[t.equipment.colEvent, t.equipment.colStart, t.equipment.colEnd, t.equipment.colDowntime, t.equipment.colPlanned, t.equipment.colCost].map((h) => (
                      <th key={h} scope="col" className="border-b border-border px-2.5 py-2 font-semibold whitespace-nowrap">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {d.items.map((e) => (
                    <tr key={e.id} className="border-b border-border last:border-0 align-top">
                      <td className="px-2.5 py-2" lang="en">
                        <span className="font-medium">{e.event_type}</span>
                        {e.description ? <span className="block text-muted-foreground">{e.description}</span> : null}
                      </td>
                      <td className="px-2.5 py-2 whitespace-nowrap">{formatDate(e.start_ts, locale, "datetime")}</td>
                      <td className="px-2.5 py-2 whitespace-nowrap">{formatDate(e.end_ts, locale, "datetime")}</td>
                      <td className="px-2.5 py-2">{formatNumber(e.downtime_min, locale)}</td>
                      <td className="px-2.5 py-2">{e.planned ? t.equipment.yes : "—"}</td>
                      <td className="px-2.5 py-2">{formatNumber(e.cost_thb ?? null, locale)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </QueryState>
  );
}

export { Section };
