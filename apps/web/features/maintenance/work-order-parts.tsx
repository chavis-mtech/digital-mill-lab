"use client";

/** Presentational pieces for the work-order workflow (status badge, stepper, audit trail). */
import { Check, CircleDashed, ShieldAlert, ShieldCheck, ShieldQuestionMark } from "lucide-react";
import type { Schema } from "@dml/contracts";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { QueryState } from "@/components/states/states";
import { useApiQuery } from "@/lib/api/hooks";
import messages from "./maintenance.i18n";
import { WO_FLOW, flowIndex, shortHash, type WorkOrderStatus } from "./helpers";

const TONE: Record<WorkOrderStatus, "info" | "accent" | "maintenance" | "warning" | "success" | "neutral" | "outline"> = {
  open: "info",
  assigned: "accent",
  in_progress: "maintenance",
  on_hold: "warning",
  resolved: "success",
  closed: "neutral",
  cancelled: "outline",
};

export function useStatusLabel() {
  const t = useT(messages);
  return (s: WorkOrderStatus) => t.wo[`s_${s}` as const];
}

export function WoStatusBadge({ status }: { status: WorkOrderStatus }) {
  const label = useStatusLabel();
  return (
    <Badge tone={TONE[status]} data-wo-status={status}>
      {label(status)}
    </Badge>
  );
}

export function WoPriorityBadge({ priority }: { priority: Schema<"WorkOrderPriority"> }) {
  const t = useT(messages);
  const label = t.wo[`p_${priority}` as const];
  return <Badge tone={priority === "urgent" ? "critical" : priority === "high" ? "warning" : "neutral"}>{label}</Badge>;
}

/** Lifecycle stepper — reached steps come from the API history, never invented. */
export function StatusStepper({ current, reached }: { current: WorkOrderStatus; reached: readonly WorkOrderStatus[] }) {
  const t = useT(messages);
  const label = useStatusLabel();
  const idx = flowIndex(current);
  const offPath = idx === -1;
  return (
    <div>
      <ol aria-label={t.wo.stepper} className="flex flex-wrap items-center gap-x-1 gap-y-2">
        {WO_FLOW.map((s, i) => {
          const done = reached.includes(s) && s !== current;
          const isCurrent = s === current;
          return (
            <li key={s} className="flex items-center gap-1" aria-current={isCurrent ? "step" : undefined}>
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-2xs font-medium",
                  isCurrent && "border-accent bg-accent-soft text-accent-text",
                  done && "border-success/40 bg-success-soft text-success-fg",
                  !isCurrent && !done && "border-dashed border-border-strong text-muted-foreground",
                )}
              >
                {done ? <Check className="size-3" aria-hidden /> : isCurrent ? <span className="size-1.5 rounded-full bg-accent" aria-hidden /> : <CircleDashed className="size-3" aria-hidden />}
                {label(s)}
              </span>
              {i < WO_FLOW.length - 1 ? <span aria-hidden className="h-px w-3 bg-border-strong" /> : null}
            </li>
          );
        })}
      </ol>
      {offPath ? (
        <p className="mt-1.5 text-xs text-muted-foreground">
          <WoStatusBadge status={current} />
        </p>
      ) : null}
    </div>
  );
}

function JsonBlock({ title, value }: { title: string; value: unknown }) {
  if (value == null) return null;
  return (
    <div className="min-w-0">
      <p className="text-2xs font-semibold text-muted-foreground">{title}</p>
      <pre className="mt-0.5 max-h-40 overflow-auto rounded bg-surface-2 p-2 font-mono text-[0.6875rem] leading-snug">{JSON.stringify(value, null, 1)}</pre>
    </div>
  );
}

export function ChainBadge({ verified }: { verified: boolean | null | undefined }) {
  const t = useT(messages);
  if (verified === true)
    return (
      <Badge tone="success" data-chain="verified">
        <ShieldCheck aria-hidden /> {t.wo.chainVerified}
      </Badge>
    );
  if (verified === false)
    return (
      <Badge tone="critical" data-chain="broken">
        <ShieldAlert aria-hidden /> {t.wo.chainBroken}
      </Badge>
    );
  return (
    <Badge tone="neutral" data-chain="unknown">
      <ShieldQuestionMark aria-hidden /> {t.wo.chainUnknown}
    </Badge>
  );
}

/** Full audit trail with the hash-chain verification badge (GET /work-orders/{id}/audit). */
export function AuditTrail({ workOrderId }: { workOrderId: number }) {
  const t = useT(messages);
  const { locale } = useLocale();
  const q = useApiQuery("/api/v1/work-orders/{work_order_id}/audit", { params: { path: { work_order_id: workOrderId } } });
  return (
    <QueryState query={q} isEmpty={(d) => d.items.length === 0} empty={<p className="text-xs text-muted-foreground">{t.wo.auditNone}</p>} compact>
      {(d) => (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <ChainBadge verified={d.chain_verified} />
            <span className="text-xs text-muted-foreground">{t.wo.auditDesc}</span>
          </div>
          <ol className="flex flex-col gap-2" aria-label={t.wo.auditTitle}>
            {d.items.map((e) => (
              <li key={e.id} className="rounded-lg border border-border p-3 text-xs">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="font-mono text-[0.8125rem] font-semibold">{e.action}</p>
                  <p className="tabular text-muted-foreground">{formatDate(e.ts, locale, "datetime")}</p>
                </div>
                <p className="mt-0.5 text-muted-foreground">
                  {t.wo.colActor}: {e.actor} · {t.wo.colRole}: <span className="font-mono">{e.role}</span>
                </p>
                <dl className="mt-1.5 grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 font-mono text-[0.6875rem] text-muted-foreground">
                  <dt>{t.wo.colHash}</dt>
                  <dd title={e.hash}>{shortHash(e.hash, 16)}</dd>
                  <dt>{t.wo.colPrev}</dt>
                  <dd title={e.prev_hash ?? ""}>{shortHash(e.prev_hash, 16)}</dd>
                </dl>
                {e.before || e.after ? (
                  <details className="mt-1.5">
                    <summary className="cursor-pointer text-accent-text">{t.wo.colChange}</summary>
                    <div className="mt-1.5 grid gap-2 sm:grid-cols-2">
                      <JsonBlock title={t.wo.before} value={e.before} />
                      <JsonBlock title={t.wo.after} value={e.after} />
                    </div>
                  </details>
                ) : null}
              </li>
            ))}
          </ol>
        </div>
      )}
    </QueryState>
  );
}
