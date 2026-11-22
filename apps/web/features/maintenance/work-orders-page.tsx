"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ClipboardPlus, UserRoundCheck } from "lucide-react";
import type { Schema } from "@dml/contracts";
import { OperationsLayout } from "@/components/layouts/layouts";
import { useApiMutation, useApiQuery } from "@/lib/api/hooks";
import { isApiRequestError } from "@/lib/api/errors";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatDate } from "@/lib/format";
import { ProvenanceBadge } from "@/components/demo/provenance-badge";
import { Disclaimer } from "@/components/demo/disclaimer";
import { DataTable, type DataTableColumn } from "@/components/data/data-table";
import { ConfirmDialog } from "@/components/data/confirm-dialog";
import { QueryState } from "@/components/states/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toast";
import { Field, NativeInput, NativeSelect, RoleGate, Section, TextArea, usePermissions } from "./shared/ops-ui";
import { AuditTrail, StatusStepper, WoPriorityBadge, WoStatusBadge, useStatusLabel } from "./work-order-parts";
import { parseIdParam, pickRecommendations, priorityForWorkOrder, transitionActions, transitionProblem, WO_STATUSES, type WorkOrderStatus } from "./helpers";
import messages from "./maintenance.i18n";

type WoOut = Schema<"WorkOrderOut">;
type Priority = Schema<"WorkOrderPriority">;
type Source = Schema<"WorkOrderSource">;

const WO_INVALIDATE = ["/api/v1/work-orders", "/api/v1/work-orders/{work_order_id}", "/api/v1/work-orders/{work_order_id}/audit", "/api/v1/maintenance/equipment", "/api/v1/alerts", "/api/v1/maintenance/technicians", "/api/v1/maintenance/recommendations"] as const;

/** Statuses in which the API accepts an assignment (409 otherwise) — used only to disable the button. */
const ASSIGNABLE: readonly WorkOrderStatus[] = ["open", "assigned", "on_hold"];

function errText(e: unknown) {
  return isApiRequestError(e) ? e.message : e instanceof Error ? e.message : String(e);
}

export function WorkOrdersPage() {
  const t = useT(messages);
  const params = useSearchParams();
  const [selected, setSelected] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState<WorkOrderStatus | "all">("all");
  const [mineOnly, setMineOnly] = useState(false);

  const list = useApiQuery("/api/v1/work-orders", {
    params: { query: { limit: 200, ...(statusFilter !== "all" ? { status: statusFilter } : {}), ...(mineOnly ? { mine_only: true } : {}) } },
  });
  const statusLabel = useStatusLabel();
  const { locale } = useLocale();

  const columns = useMemo<DataTableColumn<WoOut>[]>(
    () => [
      {
        id: "code",
        header: t.wo.colCode,
        value: (r) => r.code,
        cell: (r) => (
          <button type="button" onClick={() => setSelected(r.id)} aria-pressed={selected === r.id} className="rounded font-mono text-[0.8125rem] font-semibold text-accent-text underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
            {r.code}
          </button>
        ),
      },
      { id: "title", header: t.wo.colTitle, value: (r) => r.title, cell: (r) => <span className="line-clamp-2 min-w-48">{r.title}</span> },
      { id: "equipment", header: t.wo.colEquipment, value: (r) => r.equipment.code ?? "" },
      { id: "status", header: t.wo.colStatus, value: (r) => statusLabel(r.status), cell: (r) => <WoStatusBadge status={r.status} /> },
      { id: "priority", header: t.wo.colPriority, value: (r) => r.priority, cell: (r) => <WoPriorityBadge priority={r.priority} /> },
      { id: "tech", header: t.wo.colTech, value: (r) => r.assigned_technician?.label ?? "" },
      { id: "source", header: t.wo.colSource, value: (r) => r.source_type },
      { id: "created", header: t.wo.colCreated, value: (r) => r.created_at, cell: (r) => <span className="whitespace-nowrap">{formatDate(r.created_at, locale, "datetime")}</span> },
      { id: "scope", header: "", value: (r) => (r.is_baseline ? t.wo.baseline : t.wo.mine), sortable: false, cell: (r) => <Badge tone={r.is_baseline ? "outline" : "accent"}>{r.is_baseline ? t.wo.baseline : t.wo.mine}</Badge> },
    ],
    [t, statusLabel, locale, selected],
  );

  return (
    <OperationsLayout route="/demo/maintenance/work-orders">
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
        <CreatePanel
          presetEquipment={parseIdParam(params.get("equipment_id"))}
          presetAlert={parseIdParam(params.get("alert_id"))}
          presetRecommendation={parseIdParam(params.get("recommendation_id"))}
          onCreated={(id) => setSelected(id)}
        />
        <Section
          title={t.wo.listTitle}
          description={t.wo.listDesc}
          actions={
            <>
              <label className="flex items-center gap-1.5 text-xs">
                <span className="text-muted-foreground">{t.wo.filterStatus}</span>
                <NativeSelect value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as WorkOrderStatus | "all")} className="h-8 w-auto text-[0.8125rem]">
                  <option value="all">{t.wo.filterAll}</option>
                  {WO_STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {statusLabel(s)}
                    </option>
                  ))}
                </NativeSelect>
              </label>
              <label className="flex items-center gap-1.5 text-xs">
                <input type="checkbox" checked={mineOnly} onChange={(e) => setMineOnly(e.target.checked)} className="size-3.5 accent-[var(--accent)]" />
                {t.wo.mineOnly}
              </label>
            </>
          }
        >
          <QueryState query={list} isEmpty={(d) => d.items.length === 0}>
            {(d) => (
              <>
                <div className="flex flex-wrap items-center gap-1.5 text-xs" aria-label={t.wo.counts}>
                  {WO_STATUSES.map((s) => (
                    <Badge key={s} tone="outline">
                      {statusLabel(s)} <span className="tabular font-semibold text-foreground">{d.counts_by_status[s] ?? 0}</span>
                    </Badge>
                  ))}
                </div>
                <DataTable data={d.items} columns={columns} caption={t.wo.listTitle} getRowId={(r) => String(r.id)} pageSize={8} exportName="work-orders" initialSort={[{ id: "created", desc: true }]} />
              </>
            )}
          </QueryState>
        </Section>
      </div>
      {selected ? <WorkOrderDetail id={selected} /> : <Section title={t.wo.detail}><p className="text-sm text-muted-foreground">{t.wo.pickOne}</p></Section>}
    </OperationsLayout>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Create
// ─────────────────────────────────────────────────────────────────────────────

function CreatePanel({
  presetEquipment,
  presetAlert,
  presetRecommendation,
  onCreated,
}: {
  presetEquipment: number | null;
  presetAlert: number | null;
  presetRecommendation: number | null;
  onCreated: (id: number) => void;
}) {
  const t = useT(messages);
  const perms = usePermissions();
  const canCreate = perms.can("workorder:create");
  const equipment = useApiQuery("/api/v1/maintenance/equipment");
  const alerts = useApiQuery("/api/v1/alerts", { params: { query: { active_only: true } } });
  const recs = useApiQuery("/api/v1/maintenance/recommendations");

  const [equipmentId, setEquipmentId] = useState<number | null>(presetEquipment);
  const [source, setSource] = useState<Source>(presetAlert ? "alert" : presetRecommendation ? "recommendation" : "alert");
  const [sourceId, setSourceId] = useState<number | null>(presetAlert ?? presetRecommendation);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<Priority>("medium");
  const [confirmOpen, setConfirmOpen] = useState(false);

  // Default equipment = most urgent non-normal one (the API orders by state in the registry response we sort here).
  const items = equipment.data?.items;
  useEffect(() => {
    if (equipmentId != null || !items) return;
    const first = [...items].sort((a, b) => ["critical", "maintenance_required", "warning", "normal"].indexOf(a.health_state) - ["critical", "maintenance_required", "warning", "normal"].indexOf(b.health_state) || (b.risk_score ?? 0) - (a.risk_score ?? 0))[0];
    // eslint-disable-next-line react-hooks/set-state-in-effect -- default selection once the registry has loaded
    if (first) setEquipmentId(first.id);
  }, [items, equipmentId]);

  const alertOptions = useMemo(() => (alerts.data?.items ?? []).filter((a) => a.equipment && Number(a.equipment.id) === equipmentId && a.status !== "resolved" && a.status !== "dismissed"), [alerts.data, equipmentId]);
  const recOptions = useMemo(() => pickRecommendations(recs.data?.items ?? [], { equipmentId }), [recs.data, equipmentId]);

  // Source item → prefill title / description / priority (user can still edit).
  function applySource(kind: Source, id: number | null, eq: number | null = equipmentId) {
    setSource(kind);
    setSourceId(id);
    if (kind === "alert") {
      const a = (alerts.data?.items ?? []).find((x) => x.id === id && (eq == null || Number(x.equipment?.id) === eq));
      if (a) {
        setTitle(a.title.length > 120 ? `${a.title.slice(0, 117)}…` : a.title);
        setDescription(a.message);
        setPriority(priorityForWorkOrder(a.severity));
      }
    } else if (kind === "recommendation") {
      const r = (recs.data?.items ?? []).find((x) => x.id === id);
      if (r) {
        setTitle(r.title);
        setDescription(r.rationale);
        setPriority(priorityForWorkOrder(r.priority));
      }
    }
  }

  // A deep link (?alert_id= / ?recommendation_id=) presets the form once both lists have loaded
  // ("adjust state while rendering": runs once, no effect needed).
  const [presetDone, setPresetDone] = useState(false);
  if (!presetDone && alerts.data && recs.data) {
    setPresetDone(true);
    if (presetAlert) {
      const a = alerts.data.items.find((x) => x.id === presetAlert);
      const eqId = a?.equipment ? Number(a.equipment.id) : null;
      if (eqId != null) setEquipmentId(eqId);
      applySource("alert", presetAlert, eqId);
    } else if (presetRecommendation) {
      const r = recs.data.items.find((x) => x.id === presetRecommendation);
      if (r?.equipment) setEquipmentId(Number(r.equipment.id));
      applySource("recommendation", presetRecommendation);
    }
  }

  const create = useApiMutation("/api/v1/work-orders", { invalidate: [...WO_INVALIDATE] });
  const eq = items?.find((e) => e.id === equipmentId);
  const valid = canCreate && equipmentId != null && title.trim().length >= 3;

  async function submit() {
    if (equipmentId == null) return;
    try {
      const wo = await create.mutateAsync({
        body: {
          source_type: source,
          equipment_id: equipmentId,
          title: title.trim(),
          description: description.trim() || null,
          priority,
          alert_id: source === "alert" ? sourceId : null,
          recommendation_id: source === "recommendation" ? sourceId : null,
          confirm: true,
        },
      });
      toast.success(t.wo.created(wo.code));
      onCreated(wo.id);
      setTitle("");
      setDescription("");
      setSourceId(null);
    } catch (e) {
      toast.error(t.wo.createFailed, { description: errText(e) });
    }
  }

  const sourceItems = source === "alert" ? alertOptions.map((a) => ({ id: a.id, label: `${a.code} · ${a.title.slice(0, 70)}` })) : source === "recommendation" ? recOptions.map((r) => ({ id: r.id, label: `${r.code} · ${r.title.slice(0, 70)}` })) : [];

  return (
    <Section title={t.wo.createTitle} description={t.wo.createDesc} data-tour="work-order-create" id="wo-create">
      <RoleGate allowed={canCreate || !perms.ready} permission="workorder:create" message={t.roleGate.message} switchLabel={t.roleGate.switch} />
      <form
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid) setConfirmOpen(true);
        }}
      >
        <Field label={t.wo.equipment}>
          {(id) => (
            <NativeSelect
              id={id}
              value={equipmentId ?? ""}
              onChange={(e) => {
                setEquipmentId(Number(e.target.value) || null);
                setSourceId(null);
              }}
              disabled={!canCreate}
            >
              <option value="" disabled>
                {t.wo.pickEquipment}
              </option>
              {(items ?? []).map((e) => (
                <option key={e.id} value={e.id}>
                  {e.code} — {e.name} ({e.health_state})
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
        <Field label={t.wo.source}>
          {(id) => (
            <NativeSelect id={id} value={source} onChange={(e) => applySource(e.target.value as Source, null)} disabled={!canCreate}>
              <option value="alert">{t.wo.sourceAlert}</option>
              <option value="recommendation">{t.wo.sourceRecommendation}</option>
              <option value="manual">{t.wo.sourceManual}</option>
            </NativeSelect>
          )}
        </Field>
        {source !== "manual" ? (
          <Field label={t.wo.sourceItem} hint={sourceItems.length === 0 ? t.wo.noSourceItems : undefined}>
            {(id) => (
              <NativeSelect id={id} value={sourceId ?? ""} onChange={(e) => applySource(source, Number(e.target.value) || null)} disabled={!canCreate || sourceItems.length === 0}>
                <option value="">—</option>
                {sourceItems.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.label}
                  </option>
                ))}
              </NativeSelect>
            )}
          </Field>
        ) : null}
        <Field label={t.wo.title}>{(id) => <NativeInput id={id} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} disabled={!canCreate} required />}</Field>
        <Field label={t.wo.description}>{(id) => <TextArea id={id} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={2000} disabled={!canCreate} />}</Field>
        <Field label={t.wo.priority}>
          {(id) => (
            <NativeSelect id={id} value={priority} onChange={(e) => setPriority(e.target.value as Priority)} disabled={!canCreate}>
              {(["low", "medium", "high", "urgent"] as const).map((p) => (
                <option key={p} value={p}>
                  {t.wo[`p_${p}` as const]}
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
        <Button type="submit" variant="accent" disabled={!valid || create.isPending}>
          <ClipboardPlus aria-hidden /> {t.wo.create}
        </Button>
        <p className="text-2xs text-muted-foreground">{t.common.sandbox}</p>
      </form>
      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={t.wo.confirmTitle}
        description={t.wo.confirmBody}
        confirmLabel={t.wo.confirmLabel}
        details={
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
            <dt className="text-muted-foreground">{t.wo.equipment}</dt>
            <dd>{eq ? `${eq.code} — ${eq.name}` : "—"}</dd>
            <dt className="text-muted-foreground">{t.wo.source}</dt>
            <dd>{source}{sourceId ? ` #${sourceId}` : ""}</dd>
            <dt className="text-muted-foreground">{t.wo.title}</dt>
            <dd>{title}</dd>
            <dt className="text-muted-foreground">{t.wo.priority}</dt>
            <dd>{t.wo[`p_${priority}` as const]}</dd>
          </dl>
        }
        onConfirm={submit}
      />
    </Section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Detail: stepper, assign, transitions, history, audit
// ─────────────────────────────────────────────────────────────────────────────

function WorkOrderDetail({ id }: { id: number }) {
  const t = useT(messages);
  const { locale } = useLocale();
  const statusLabel = useStatusLabel();
  const perms = usePermissions();
  const q = useApiQuery("/api/v1/work-orders/{work_order_id}", { params: { path: { work_order_id: id } } });
  const technicians = useApiQuery("/api/v1/maintenance/technicians");
  const [techId, setTechId] = useState<number | null>(null);
  const [assignOpen, setAssignOpen] = useState(false);
  const [pending, setPending] = useState<WorkOrderStatus | null>(null);
  const [resolution, setResolution] = useState("");
  const [note, setNote] = useState("");
  const [downtime, setDowntime] = useState("");

  const assign = useApiMutation("/api/v1/work-orders/{work_order_id}/assign", { invalidate: [...WO_INVALIDATE] });
  const transition = useApiMutation("/api/v1/work-orders/{work_order_id}/transition", { invalidate: [...WO_INVALIDATE] });
  const canAssign = perms.can("workorder:assign");
  const canTransition = perms.can("workorder:transition");

  async function doAssign() {
    if (techId == null) return;
    try {
      const wo = await assign.mutateAsync({ params: { path: { work_order_id: id } }, body: { technician_id: techId } });
      toast.success(t.wo.assigned(wo.assigned_technician?.label ?? String(techId)));
    } catch (e) {
      toast.error(t.wo.assignFailed, { description: errText(e) });
    }
  }

  async function doTransition(to: WorkOrderStatus) {
    try {
      const downtimeMin = downtime.trim() === "" ? null : Number(downtime);
      await transition.mutateAsync({
        params: { path: { work_order_id: id } },
        body: {
          to_status: to,
          note: note.trim() || null,
          resolution_notes: to === "resolved" ? resolution.trim() : null,
          downtime_min: to === "resolved" && downtimeMin != null && Number.isFinite(downtimeMin) ? downtimeMin : null,
        },
      });
      toast.success(t.wo.transitioned(statusLabel(to)));
      setResolution("");
      setNote("");
      setDowntime("");
    } catch (e) {
      toast.error(t.wo.transitionFailed, { description: errText(e) });
    }
  }

  return (
    <Section title={t.wo.detail} id="wo-detail">
      <QueryState query={q}>
        {(wo) => {
          const actions = transitionActions(wo.allowed_transitions, canTransition);
          const reached = wo.history.map((h) => h.to_status);
          const act = actions.find((a) => a.to === pending);
          const problem = act ? transitionProblem(act, resolution) : null;
          return (
            <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
              <div className="flex min-w-0 flex-col gap-4">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-mono text-base font-semibold">{wo.code}</h3>
                    <WoStatusBadge status={wo.status} />
                    <WoPriorityBadge priority={wo.priority} />
                    <Badge tone={wo.is_baseline ? "outline" : "accent"}>{wo.is_baseline ? t.wo.baseline : t.wo.mine}</Badge>
                  </div>
                  <p className="mt-1 text-sm font-medium">{wo.title}</p>
                  {wo.description ? <p lang="en" className="mt-0.5 text-xs text-muted-foreground">{wo.description}</p> : null}
                  <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
                    <dt className="text-muted-foreground">{t.wo.colEquipment}</dt>
                    <dd>
                      <Link href={`/demo/maintenance/equipment?equipment_id=${wo.equipment.id}`} className="text-accent-text hover:underline">
                        {wo.equipment.code} — {wo.equipment.label}
                      </Link>
                    </dd>
                    <dt className="text-muted-foreground">{t.wo.colTech}</dt>
                    <dd>{wo.assigned_technician?.label ?? "—"}</dd>
                    <dt className="text-muted-foreground">{t.wo.colSource}</dt>
                    <dd>
                      {wo.source_type}
                      {wo.alert_code ? ` · ${t.wo.linkedAlert}: ${wo.alert_code}${wo.alert_status ? ` (${wo.alert_status})` : ""}` : ""}
                      {wo.recommendation_id ? ` · ${t.wo.linkedRecommendation}: #${wo.recommendation_id}` : ""}
                    </dd>
                    <dt className="text-muted-foreground">{t.wo.colCreated}</dt>
                    <dd className="tabular">{formatDate(wo.created_at, locale, "datetime")}</dd>
                    {wo.resolution_notes ? (
                      <>
                        <dt className="text-muted-foreground">{t.wo.resolutionShown}</dt>
                        <dd lang="en">{wo.resolution_notes}</dd>
                      </>
                    ) : null}
                  </dl>
                </div>

                <div>
                  <h3 className="mb-1.5 text-xs font-semibold">{t.wo.flowTitle}</h3>
                  <StatusStepper current={wo.status} reached={reached} />
                  <p className="mt-1.5 text-2xs text-muted-foreground">{t.wo.flowNote}</p>
                </div>

                {wo.read_only_reason ? (
                  <p role="note" className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-xs text-muted-foreground">
                    <ApiTextInline>{wo.read_only_reason}</ApiTextInline> {wo.is_baseline ? t.wo.readOnly : null}
                  </p>
                ) : null}

                <div className="rounded-lg border border-border p-3">
                  <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold">
                    <UserRoundCheck className="size-3.5" aria-hidden /> {t.wo.assignTitle}
                  </h3>
                  <RoleGate allowed={canAssign || !perms.ready} permission="workorder:assign" message={t.roleGate.message} switchLabel={t.roleGate.switch} className="mb-2" />
                  <div className="flex flex-wrap items-end gap-2">
                    <Field label={t.wo.pickTech} className="min-w-52 flex-1">
                      {(fid) => (
                        <NativeSelect id={fid} value={techId ?? ""} onChange={(e) => setTechId(Number(e.target.value) || null)} disabled={!canAssign || technicians.isPending}>
                          <option value="">—</option>
                          {(technicians.data?.items ?? []).map((tc) => (
                            <option key={tc.id} value={tc.id}>
                              {tc.display_name} · {tc.skill} · {t.wo.openAssignments(tc.open_assignments ?? 0)}
                            </option>
                          ))}
                        </NativeSelect>
                      )}
                    </Field>
                    <Button variant="outline" disabled={!canAssign || techId == null || !ASSIGNABLE.includes(wo.status)} onClick={() => setAssignOpen(true)}>
                      {t.wo.assign}
                    </Button>
                  </div>
                  <ConfirmDialog
                    open={assignOpen}
                    onOpenChange={setAssignOpen}
                    title={t.wo.assignConfirm}
                    description={`${wo.code} → ${technicians.data?.items.find((x) => x.id === techId)?.display_name ?? ""}`}
                    onConfirm={doAssign}
                  />
                </div>

                <div className="rounded-lg border border-border p-3">
                  <h3 className="mb-2 text-xs font-semibold">{t.wo.transitionTitle}</h3>
                  <RoleGate allowed={canTransition || !perms.ready} permission="workorder:transition" message={t.roleGate.message} switchLabel={t.roleGate.switch} className="mb-2" />
                  {actions.length === 0 ? (
                    <p className="text-xs text-muted-foreground">{t.wo.transitionNone}</p>
                  ) : (
                    <div className="flex flex-col gap-2">
                      <div className="grid gap-2 sm:grid-cols-2">
                        <Field label={t.wo.note}>{(fid) => <NativeInput id={fid} value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />}</Field>
                        {actions.some((a) => a.needsResolutionNotes) ? (
                          <Field label={t.wo.downtimeMin}>{(fid) => <NativeInput id={fid} type="number" min={0} value={downtime} onChange={(e) => setDowntime(e.target.value)} />}</Field>
                        ) : null}
                      </div>
                      {actions.some((a) => a.needsResolutionNotes) ? (
                        <Field label={t.wo.resolutionNotes} hint={t.wo.resolutionRequired}>
                          {(fid) => <TextArea id={fid} value={resolution} onChange={(e) => setResolution(e.target.value)} maxLength={1000} />}
                        </Field>
                      ) : null}
                      <div className="flex flex-wrap gap-2" role="group" aria-label={t.wo.transitionTitle}>
                        {actions.map((a) => (
                          <Button key={a.to} size="sm" variant={a.tone === "primary" ? "default" : a.tone === "destructive" ? "destructive" : "outline"} disabled={transitionProblem(a, resolution) !== null} onClick={() => setPending(a.to)} data-transition={a.to}>
                            {t.wo.goTo(statusLabel(a.to))}
                          </Button>
                        ))}
                      </div>
                    </div>
                  )}
                  <ConfirmDialog
                    open={pending !== null && !problem}
                    onOpenChange={(o) => !o && setPending(null)}
                    title={t.wo.transitionConfirm(pending ? statusLabel(pending) : "")}
                    description={t.wo.transitionBody}
                    details={
                      pending === "resolved" ? (
                        <p lang="en">
                          <span className="text-muted-foreground">{t.wo.resolutionShown}: </span>
                          {resolution}
                        </p>
                      ) : undefined
                    }
                    onConfirm={async () => {
                      if (pending) await doTransition(pending);
                      setPending(null);
                    }}
                  />
                </div>
              </div>

              <div className="flex min-w-0 flex-col gap-4">
                <div>
                  <h3 className="mb-1.5 text-xs font-semibold">{t.wo.history}</h3>
                  <ol className="flex flex-col gap-1.5">
                    {wo.history.map((h, i) => (
                      <li key={i} className="rounded-lg border border-border px-3 py-2 text-xs">
                        <div className="flex flex-wrap items-center gap-1.5">
                          {h.from_status ? <WoStatusBadge status={h.from_status} /> : <span className="text-muted-foreground">∅</span>}
                          <span aria-hidden>→</span>
                          <WoStatusBadge status={h.to_status} />
                          <span className="tabular ml-auto text-muted-foreground">{formatDate(h.changed_at, locale, "datetime")}</span>
                        </div>
                        <p className="mt-0.5 text-muted-foreground">
                          {t.wo.colRole}: <span className="font-mono">{h.actor_role}</span>
                          {h.note ? <> · <span lang="en">{h.note}</span></> : null}
                        </p>
                      </li>
                    ))}
                  </ol>
                </div>
                <div>
                  <h3 className="mb-1.5 flex items-center gap-2 text-xs font-semibold">{t.wo.auditTitle}</h3>
                  <AuditTrail workOrderId={wo.id} />
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <ProvenanceBadge kind="synthetic_actual" />
                  <Disclaimer kind="advisory" />
                </div>
              </div>
            </div>
          );
        }}
      </QueryState>
    </Section>
  );
}

function ApiTextInline({ children }: { children: React.ReactNode }) {
  return <span lang="en">{children}</span>;
}
