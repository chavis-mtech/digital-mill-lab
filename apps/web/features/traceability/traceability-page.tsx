"use client";

import { useMemo, useState, type KeyboardEvent } from "react";
import { Printer, ShieldCheck } from "lucide-react";
import type { Schema } from "@dml/contracts";
import { OperationsLayout } from "@/components/layouts/layouts";
import { apiGet } from "@/lib/api/client";
import { useApiQuery } from "@/lib/api/hooks";
import { useDemo } from "@/lib/demo/context";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatDate, formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";
import { DataTable, type DataTableColumn } from "@/components/data/data-table";
import { ProvenanceBadge } from "@/components/demo/provenance-badge";
import { Disclaimer } from "@/components/demo/disclaimer";
import { QueryState } from "@/components/states/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toast";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { ApiText, Field, NativeSelect, Section } from "@/features/maintenance/shared/ops-ui";
import { COL_GAP, NODE_H, NODE_W, connectedEdges, edgePath, edgeWidth, layoutGraph, parseNodeId, truncateLabel } from "./graph-layout";
import messages from "./traceability.i18n";

type Graph = Schema<"TraceGraphResponse">;
type Delivery = Schema<"DeliveryOut">;
type Lot = Schema<"LotOut">;

type Mode = "backward" | "forward";

export function TraceabilityPage() {
  const t = useT(messages);
  const [mode, setMode] = useState<Mode>("backward");
  const [lotId, setLotId] = useState<number | null>(null);
  const [supplierId, setSupplierId] = useState<number | null>(null);
  const [deliveryId, setDeliveryId] = useState<number | null>(null);
  const [maxNodes, setMaxNodes] = useState<60 | 400>(60);
  const [reportLot, setReportLot] = useState<number | null>(null);

  const lots = useApiQuery("/api/v1/traceability/lots", { params: { query: { limit: 50 } } });
  const suppliers = useApiQuery("/api/v1/logistics/suppliers");

  const effLot = lotId ?? lots.data?.items[0]?.id ?? null;
  const effSupplier = supplierId ?? suppliers.data?.items[0]?.id ?? null;

  const backward = useApiQuery(
    "/api/v1/traceability/backward",
    { params: { query: { lot_id: effLot ?? undefined, max_nodes: maxNodes } } },
    { enabled: mode === "backward" && effLot != null },
  );
  const forward = useApiQuery(
    "/api/v1/traceability/forward",
    { params: { query: deliveryId != null ? { delivery_id: deliveryId, max_nodes: maxNodes } : { supplier_id: effSupplier ?? undefined, max_nodes: maxNodes } } },
    { enabled: mode === "forward" && (deliveryId != null || effSupplier != null) },
  );
  const graph = mode === "backward" ? backward : forward;
  const effReport = mode === "backward" ? effLot : reportLot;

  return (
    <OperationsLayout route="/demo/traceability">
      <MethodBanner method={graph.data?.method} explanation={graph.data?.method_explanation} />

      <Section
        title={t.graphTitle}
        description={t.graphDesc}
        id="trace-graph"
        data-tour="traceability-graph"
        actions={
          <ToggleGroup type="single" value={mode} onValueChange={(v) => v && setMode(v as Mode)} aria-label={t.graphTitle}>
            <ToggleGroupItem value="backward" className="px-3 text-xs">
              {t.modeBackward}
            </ToggleGroupItem>
            <ToggleGroupItem value="forward" className="px-3 text-xs">
              {t.modeForward}
            </ToggleGroupItem>
          </ToggleGroup>
        }
      >
        <div className="flex flex-wrap items-end gap-3">
          {mode === "backward" ? (
            <Field label={t.pickLot} className="min-w-64">
              {(id) => (
                <NativeSelect id={id} value={effLot ?? ""} onChange={(e) => setLotId(Number(e.target.value) || null)}>
                  {(lots.data?.items ?? []).map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.code} · {formatNumber(l.quantity_t, "en", { digits: 1 })} t · {l.status}
                    </option>
                  ))}
                </NativeSelect>
              )}
            </Field>
          ) : (
            <>
              <Field label={t.pickSupplier} className="min-w-64">
                {(id) => (
                  <NativeSelect
                    id={id}
                    value={effSupplier ?? ""}
                    onChange={(e) => {
                      setSupplierId(Number(e.target.value) || null);
                      setDeliveryId(null);
                    }}
                    disabled={deliveryId != null}
                  >
                    {(suppliers.data?.items ?? []).map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.code} — {s.name}
                      </option>
                    ))}
                  </NativeSelect>
                )}
              </Field>
              {deliveryId != null ? (
                <p className="flex items-center gap-2 text-xs">
                  {t.pickDelivery}: <span className="font-mono font-semibold">#{deliveryId}</span>
                  <Button size="xs" variant="outline" onClick={() => setDeliveryId(null)}>
                    {t.clearDelivery}
                  </Button>
                </p>
              ) : null}
            </>
          )}
          <Field label={t.graphDetail}>
            {(id) => (
              <NativeSelect id={id} value={maxNodes} onChange={(e) => setMaxNodes(Number(e.target.value) as 60 | 400)}>
                <option value={60}>{t.compact}</option>
                <option value={400}>{t.full}</option>
              </NativeSelect>
            )}
          </Field>
          <ProvenanceBadge kind="synthetic_actual" />
        </div>
        <QueryState query={graph} isEmpty={(d) => d.nodes.length === 0}>
          {(g) => <TraceGraph graph={g} mode={mode} onSelectLot={(id) => setReportLot(id)} />}
        </QueryState>
      </Section>

      {effReport != null ? <ReportPanel lotId={effReport} /> : null}

      <Section title={t.deliveriesTitle} description={t.deliveriesDesc} id="deliveries">
        <DeliveriesTable
          onTrace={(d) => {
            setMode("forward");
            setDeliveryId(d.id);
            document.getElementById("trace-graph")?.scrollIntoView({ behavior: "smooth" });
          }}
        />
      </Section>
      <Section title={t.lotsTitle} id="lots">
        <LotsTable
          onPick={(l) => {
            setMode("backward");
            setLotId(l.id);
            document.getElementById("trace-graph")?.scrollIntoView({ behavior: "smooth" });
          }}
        />
      </Section>
    </OperationsLayout>
  );
}

function MethodBanner({ method, explanation }: { method?: string; explanation?: string }) {
  const t = useT(messages);
  return (
    <section aria-label={t.methodTitle} className="flex flex-col gap-2 rounded-xl border border-info/40 bg-info-soft/40 p-4" data-tour="traceability-method">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="info">
          <ShieldCheck aria-hidden /> {t.methodBadge}
        </Badge>
        <Badge tone="warning">{t.notCert}</Badge>
        {method ? <span className="font-mono text-2xs text-subtle-foreground">{method}</span> : null}
      </div>
      <h2 className="text-sm font-semibold">{t.methodTitle}</h2>
      <p className="text-xs leading-relaxed text-foreground">{t.methodShort}</p>
      {explanation ? (
        <details className="text-xs">
          <summary className="cursor-pointer text-accent-text">{t.methodFromApi}</summary>
          <p lang="en" className="mt-1 leading-relaxed text-muted-foreground">
            {explanation}
          </p>
        </details>
      ) : null}
    </section>
  );
}

function TraceGraph({ graph, mode, onSelectLot }: { graph: Graph; mode: Mode; onSelectLot: (id: number) => void }) {
  const t = useT(messages);
  const { locale } = useLocale();
  const layout = useMemo(() => layoutGraph(graph.nodes), [graph.nodes]);
  const [selected, setSelected] = useState<string | null>(null);
  const sel = selected ? layout.byId.get(selected) : undefined;
  const touching = useMemo(() => connectedEdges(graph.edges, selected), [graph.edges, selected]);
  const touchSet = useMemo(() => new Set(touching.map((e) => `${e.source}>${e.target}`)), [touching]);
  const layerLabel = t.layer as Record<string, string>;
  const label = (id: string) => layout.byId.get(id)?.label ?? id;

  function pick(id: string) {
    setSelected(id);
    const lot = parseNodeId(id, "cpo_lot");
    if (lot != null) onSelectLot(lot);
  }
  function onKey(e: KeyboardEvent, id: string) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      pick(id);
    }
  }

  const edgeColumns = useMemo<DataTableColumn<Graph["edges"][number]>[]>(
    () => [
      { id: "from", header: t.colFrom, value: (e) => label(e.source) },
      { id: "to", header: t.colTo, value: (e) => label(e.target) },
      { id: "mass", header: t.colMass, value: (e) => e.mass ?? "", align: "right", cell: (e) => (e.mass != null ? `${formatNumber(e.mass, locale)} ${e.unit ?? ""}` : "—") },
      { id: "share", header: t.colShare, value: (e) => (e.share != null ? e.share * 100 : ""), align: "right", cell: (e) => (e.share != null ? formatNumber(e.share * 100, locale, { digits: 2 }) : "—") },
      { id: "method", header: t.colMethod, value: (e) => e.method ?? "" },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `label` reads layout, which changes with the graph
    [t, locale, layout],
  );

  return (
    <div className="flex flex-col gap-4">
      {graph.truncated ? (
        <p role="note" className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-xs text-muted-foreground">
          {mode === "backward" ? t.graphTruncated : t.graphTruncatedForward}
        </p>
      ) : null}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="min-w-0 overflow-auto rounded-lg border border-border bg-surface-2/40" tabIndex={0} role="region" aria-label={t.graphAria(graph.nodes.length, graph.edges.length)} style={{ maxHeight: 560 }}>
          <svg width={layout.width} height={layout.height} role="group" aria-label={t.graphAria(graph.nodes.length, graph.edges.length)}>
            {layout.layers.map((ty, i) => (
              <text key={ty} x={12 + i * (NODE_W + COL_GAP)} y={20} className="fill-muted-foreground text-[11px] font-semibold">
                {layerLabel[ty] ?? ty}
              </text>
            ))}
            <defs>
              <clipPath id="trace-node-clip" clipPathUnits="userSpaceOnUse">
                <rect x={4} y={0} width={NODE_W - 10} height={NODE_H} />
              </clipPath>
            </defs>
            <g fill="none">
              {graph.edges.map((e, i) => {
                const a = layout.byId.get(e.source);
                const b = layout.byId.get(e.target);
                if (!a || !b) return null;
                const on = touchSet.has(`${e.source}>${e.target}`);
                return <path key={i} d={edgePath(a, b)} strokeWidth={edgeWidth(e.share)} className={on ? "stroke-accent" : "stroke-border-strong"} strokeOpacity={on || !selected ? 0.85 : 0.25} />;
              })}
            </g>
            {layout.nodes.map((n) => {
              const isSel = n.id === selected;
              return (
                <g
                  key={n.id}
                  transform={`translate(${n.x},${n.y})`}
                  role="button"
                  tabIndex={0}
                  aria-pressed={isSel}
                  aria-label={`${layerLabel[n.type] ?? n.type}: ${n.label}`}
                  onClick={() => pick(n.id)}
                  onKeyDown={(e) => onKey(e, n.id)}
                  className="cursor-pointer outline-none [&:focus-visible>rect]:stroke-ring [&:focus-visible>rect]:stroke-2"
                >
                  <rect width={NODE_W} height={NODE_H} rx={6} className={cn(isSel ? "fill-accent-soft stroke-accent" : "fill-surface stroke-border-strong")} strokeWidth={isSel ? 2 : 1} />
                  {/* Full label clipped to the node box (not string-truncated) so the visible text stays part of the
                      accessible name (axe label-content-name-mismatch); the full text is also in a <title> tooltip. */}
                  <title>{n.label}</title>
                  <text x={8} y={NODE_H / 2 + 4} className="fill-foreground text-[11px]" clipPath="url(#trace-node-clip)">
                    {n.label}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
        <aside className="flex min-w-0 flex-col gap-2 rounded-lg border border-border p-3 text-xs" aria-live="polite" aria-label={t.nodeSelected}>
          <h3 className="text-sm font-semibold">{t.nodeSelected}</h3>
          {sel ? (
            <>
              <p className="font-mono font-semibold break-all">{sel.label}</p>
              <dl className="grid grid-cols-[fit-content(45%)_minmax(0,1fr)] gap-x-3 gap-y-0.5 [overflow-wrap:anywhere]">
                <dt className="text-muted-foreground">{t.nodeType}</dt>
                <dd>{(t.layer as Record<string, string>)[sel.type] ?? sel.type}</dd>
                {(sel as { quantity?: number | null }).quantity != null ? (
                  <>
                    <dt className="text-muted-foreground">{t.nodeQty}</dt>
                    <dd className="tabular">
                      {formatNumber((sel as { quantity?: number | null }).quantity ?? null, locale)} {(sel as { unit?: string | null }).unit ?? ""}
                    </dd>
                  </>
                ) : null}
                {(sel as { ts?: string | null }).ts ? (
                  <>
                    <dt className="text-muted-foreground">{t.nodeTs}</dt>
                    <dd className="tabular">{formatDate((sel as { ts?: string | null }).ts, locale, "datetime")}</dd>
                  </>
                ) : null}
                {Object.entries((sel as { attributes?: Record<string, unknown> }).attributes ?? {}).map(([k, v]) => (
                  <div key={k} className="contents">
                    <dt className="font-mono text-muted-foreground">{k}</dt>
                    <dd lang="en">{typeof v === "number" ? formatNumber(v, locale) : String(v)}</dd>
                  </div>
                ))}
              </dl>
              <p className="mt-1 text-2xs font-semibold text-muted-foreground uppercase">{t.connected}</p>
              <ul className="max-h-40 overflow-auto">
                {touching.map((e, i) => (
                  <li key={i} className="tabular border-b border-border py-1 last:border-0">
                    <span className="font-mono">{truncateLabel(label(e.source), 20)}</span> → <span className="font-mono">{truncateLabel(label(e.target), 20)}</span>
                    {e.share != null ? <b> · {formatNumber(e.share * 100, locale, { digits: 2 })}%</b> : null}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="text-muted-foreground">{t.nodeNone}</p>
          )}
        </aside>
      </div>
      <details>
        <summary className="cursor-pointer text-xs font-medium text-accent-text">{t.edgeTable}</summary>
        <div className="mt-2">
          <DataTable data={graph.edges} columns={edgeColumns} caption={t.edgeTable} pageSize={10} exportName="trace-edges" />
        </div>
      </details>
    </div>
  );
}

/** Generic read-only renderer for JSON blobs the API documents as free-form (quality / sustainability fields). */
function JsonTree({ value, depth = 0 }: { value: unknown; depth?: number }) {
  const { locale } = useLocale();
  if (value === null || value === undefined) return <span>—</span>;
  if (typeof value === "number") return <span className="tabular">{formatNumber(value, locale)}</span>;
  if (typeof value === "string" || typeof value === "boolean") return <span lang="en">{String(value)}</span>;
  if (Array.isArray(value))
    return (
      <ul className="list-disc pl-4">
        {value.map((v, i) => (
          <li key={i}>
            <JsonTree value={v} depth={depth + 1} />
          </li>
        ))}
      </ul>
    );
  const entries = Object.entries(value as Record<string, unknown>);
  return (
    <dl className={cn("grid grid-cols-[fit-content(45%)_minmax(0,1fr)] gap-x-3 gap-y-0.5 [overflow-wrap:anywhere]", depth > 0 && "mt-0.5 border-l border-border pl-2")}>
      {entries.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="font-mono text-muted-foreground">{k.replace(/_/g, " ")}</dt>
          <dd className="min-w-0">
            <JsonTree value={v} depth={depth + 1} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

function ReportPanel({ lotId }: { lotId: number }) {
  const t = useT(messages);
  const { locale } = useLocale();
  const demo = useDemo();
  const q = useApiQuery("/api/v1/traceability/lots/{lot_id}/report", { params: { path: { lot_id: lotId } } });
  const [busy, setBusy] = useState(false);

  async function print() {
    const win = window.open("about:blank", "_blank");
    setBusy(true);
    const id = toast.loading(t.printing);
    try {
      const doc = await apiGet("/api/v1/traceability/lots/{lot_id}/report/printable", { params: { path: { lot_id: lotId } } }, demo.request);
      const blob = new Blob([doc.html], { type: "text/html;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      if (win && !win.closed) {
        win.location.href = url;
        toast.success(doc.title, { id });
      } else {
        const a = document.createElement("a");
        a.href = url;
        a.download = doc.filename;
        a.click();
        toast.message(t.printBlocked, { id });
      }
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch {
      win?.close();
      toast.error(t.printFailed, { id });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section
      title={t.reportTitle}
      description={t.reportDesc}
      id="trace-report"
      actions={
        <Button variant="outline" size="sm" onClick={() => void print()} disabled={busy}>
          <Printer aria-hidden /> {t.print}
        </Button>
      }
    >
      <QueryState query={q}>
        {(r) => (
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <ProvenanceBadge kind="synthetic_actual" />
              <Badge tone="info">{t.methodBadge}</Badge>
              <Badge tone="warning">{t.notCert}</Badge>
            </div>
            <dl className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-5">
              {[
                [t.lot, <span key="l" className="font-mono font-semibold">{r.lot.code}</span>],
                [t.tank, r.lot.tank_code],
                [t.quantity, `${formatNumber(r.lot.quantity_t, locale)} t`],
                [t.ffa, r.lot.ffa_pct != null ? `${formatNumber(r.lot.ffa_pct, locale, { digits: 2 })} %` : "—"],
                [t.suppliers, formatNumber(r.lot.supplier_count ?? null, locale)],
              ].map(([k, v], i) => (
                <div key={i} className="rounded-lg border border-border p-2.5">
                  <dt className="text-2xs text-muted-foreground">{k}</dt>
                  <dd className="tabular mt-0.5 text-sm font-semibold">{v}</dd>
                </div>
              ))}
            </dl>
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
              <div className="min-w-0">
                <h3 className="mb-1.5 text-xs font-semibold">{t.sharesTitle}</h3>
                <div className="max-h-96 overflow-auto rounded-lg border border-border" tabIndex={0} role="region" aria-label={t.sharesTitle}>
                  <table className="tabular w-full border-collapse text-left text-xs">
                    <caption className="sr-only">{t.sharesTitle}</caption>
                    <thead className="sticky top-0 bg-surface-2 text-muted-foreground">
                      <tr>
                        {[t.colSupplier, t.colFfb, t.colShare, t.colAttributed].map((h) => (
                          <th key={h} scope="col" className="border-b border-border px-2.5 py-2 font-semibold whitespace-nowrap">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {r.supplier_shares.map((s) => (
                        <tr key={s.supplier_code} className="border-b border-border last:border-0">
                          <th scope="row" className="px-2.5 py-1.5 text-left font-normal" lang="en">
                            <span className="font-mono">{s.supplier_code}</span> <span className="text-muted-foreground">{s.supplier_name}</span>
                          </th>
                          <td className="px-2.5 py-1.5">{formatNumber(s.ffb_kg, locale)}</td>
                          <td className="px-2.5 py-1.5 font-semibold">{formatNumber(s.share_pct, locale, { digits: 2 })}</td>
                          <td className="px-2.5 py-1.5">{formatNumber(s.attributed_cpo_t, locale, { digits: 3 })}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="mt-1.5 text-2xs text-muted-foreground">
                  {t.batches}: <span className="font-mono">{r.production_batches.join(", ")}</span>
                </p>
              </div>
              <div className="flex min-w-0 flex-col gap-3 text-xs">
                <div>
                  <h3 className="mb-1 font-semibold">{t.quality}</h3>
                  <JsonTree value={r.quality_summary} />
                </div>
                {r.sustainability_fields ? (
                  <div>
                    <h3 className="mb-1 font-semibold">{t.sustainability}</h3>
                    <JsonTree value={r.sustainability_fields} />
                  </div>
                ) : null}
              </div>
            </div>
            <div>
              <h3 className="mb-1 text-xs font-semibold">{t.disclaimers}</h3>
              <ul className="list-disc pl-5 text-xs text-muted-foreground">
                {r.disclaimers.map((d) => (
                  <li key={d.key}>{locale === "th" && d.text_th ? d.text_th : <ApiText>{d.text_en}</ApiText>}</li>
                ))}
              </ul>
            </div>
            <Disclaimer kind="synthetic" />
          </div>
        )}
      </QueryState>
    </Section>
  );
}

function DeliveriesTable({ onTrace }: { onTrace: (d: Delivery) => void }) {
  const t = useT(messages);
  const { locale } = useLocale();
  const q = useApiQuery("/api/v1/traceability/deliveries", { params: { query: { limit: 100 } } });
  const columns = useMemo<DataTableColumn<Delivery>[]>(
    () => [
      { id: "code", header: t.colDelivery, value: (r) => r.code, cell: (r) => <span className="font-mono text-xs whitespace-nowrap">{r.code}</span> },
      { id: "sup", header: t.colSupplier, value: (r) => r.supplier_code },
      { id: "plt", header: t.colPlantation, value: (r) => r.plantation_code ?? "" },
      { id: "recv", header: t.colReceived, value: (r) => r.received_ts, cell: (r) => <span className="whitespace-nowrap">{formatDate(r.received_ts, locale, "datetime")}</span> },
      { id: "net", header: t.colNet, value: (r) => r.net_kg, align: "right", cell: (r) => formatNumber(r.net_kg, locale) },
      { id: "acc", header: t.colAccepted, value: (r) => r.accepted_kg, align: "right", cell: (r) => formatNumber(r.accepted_kg, locale) },
      { id: "grade", header: t.colGrade, value: (r) => r.grade },
      { id: "ripe", header: t.colRipe, value: (r) => r.ripe_pct ?? "", align: "right", cell: (r) => formatNumber(r.ripe_pct ?? null, locale, { digits: 1 }) },
      { id: "ticket", header: t.colTicket, value: (r) => r.ticket_no ?? "", cell: (r) => <span className="font-mono text-2xs">{r.ticket_no ?? "—"}</span> },
      {
        id: "act",
        header: "",
        value: () => "",
        sortable: false,
        csv: false,
        searchable: false,
        cell: (r) => (
          <Button size="xs" variant="outline" onClick={() => onTrace(r)}>
            {t.traceFrom}
          </Button>
        ),
      },
    ],
    [t, locale, onTrace],
  );
  return (
    <QueryState query={q} isEmpty={(d) => d.items.length === 0}>
      {(d) => (
        <>
          <ProvenanceBadge kind="synthetic_actual" />
          <DataTable data={d.items} columns={columns} caption={t.deliveriesTitle} getRowId={(r) => String(r.id)} pageSize={8} exportName="ffb-deliveries" />
        </>
      )}
    </QueryState>
  );
}

function LotsTable({ onPick }: { onPick: (l: Lot) => void }) {
  const t = useT(messages);
  const { locale } = useLocale();
  const q = useApiQuery("/api/v1/traceability/lots", { params: { query: { limit: 50 } } });
  const columns = useMemo<DataTableColumn<Lot>[]>(
    () => [
      {
        id: "code",
        header: t.colLot,
        value: (r) => r.code,
        cell: (r) => (
          <button type="button" onClick={() => onPick(r)} className="rounded font-mono text-xs font-semibold text-accent-text underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
            {r.code}
          </button>
        ),
      },
      { id: "tank", header: t.colTank, value: (r) => r.tank_code },
      { id: "fill", header: t.colFill, value: (r) => r.fill_start_ts, cell: (r) => <span className="whitespace-nowrap">{formatDate(r.fill_start_ts, locale, "datetime")}</span> },
      { id: "qty", header: t.colQty, value: (r) => r.quantity_t, align: "right", cell: (r) => formatNumber(r.quantity_t, locale, { digits: 1 }) },
      { id: "ffa", header: t.colFfa, value: (r) => r.ffa_pct ?? "", align: "right", cell: (r) => formatNumber(r.ffa_pct ?? null, locale, { digits: 2 }) },
      { id: "status", header: t.colStatus, value: (r) => r.status },
      { id: "sup", header: t.colSuppliers, value: (r) => r.supplier_count ?? "", align: "right" },
    ],
    [t, locale, onPick],
  );
  return (
    <QueryState query={q} isEmpty={(d) => d.items.length === 0}>
      {(d) => (
        <>
          <ProvenanceBadge kind="synthetic_actual" />
          <DataTable data={d.items} columns={columns} caption={t.lotsTitle} getRowId={(r) => String(r.id)} pageSize={8} exportName="cpo-lots" />
        </>
      )}
    </QueryState>
  );
}
