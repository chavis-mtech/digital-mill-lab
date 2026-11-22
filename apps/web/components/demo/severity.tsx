"use client";

import {
  CircleCheck,
  Info,
  OctagonExclamationPoint,
  TriangleExclamationPoint,
  Wrench,
  ArrowDown,
  Minus,
  ArrowUp,
  type LucideIcon,
} from "lucide-react";
import type { Schema } from "@dml/contracts";
import { useT } from "@/lib/i18n/client";
import { cn } from "@/lib/utils";
import common from "@/messages/common.i18n";

export type Severity = Schema<"Severity">;
export type HealthState = Schema<"HealthState">;

const SEVERITY_STYLE: Record<Severity, { icon: LucideIcon; className: string; rank: number }> = {
  info: { icon: Info, className: "bg-info-soft text-info-fg border-info/30", rank: 0 },
  low: { icon: ArrowDown, className: "bg-neutral-soft text-neutral-fg border-border-strong", rank: 1 },
  medium: { icon: Minus, className: "bg-warning-soft text-warning-fg border-warning/40", rank: 2 },
  high: { icon: ArrowUp, className: "bg-critical-soft text-critical-fg border-critical/30", rank: 3 },
  critical: { icon: OctagonExclamationPoint, className: "bg-critical text-white border-critical dark:text-background", rank: 4 },
};

export const severityRank = (s: Severity) => SEVERITY_STYLE[s].rank;

/** Alert / risk severity pill: icon + text + colour (never colour alone). */
export function SeverityPill({ severity, className }: { severity: Severity; className?: string }) {
  const t = useT(common);
  const { icon: Icon, className: tone } = SEVERITY_STYLE[severity];
  return (
    <span
      data-severity={severity}
      className={cn("inline-flex items-center gap-1 rounded-md border px-1.5 py-px text-2xs leading-4 font-semibold whitespace-nowrap", tone, className)}
    >
      <Icon className="size-3" aria-hidden strokeWidth={2.5} />
      {t.severity[severity]}
    </span>
  );
}

const HEALTH_STYLE: Record<HealthState, { icon: LucideIcon; className: string; dot: string }> = {
  normal: { icon: CircleCheck, className: "bg-success-soft text-success-fg border-success/30", dot: "bg-success" },
  warning: { icon: TriangleExclamationPoint, className: "bg-warning-soft text-warning-fg border-warning/45", dot: "bg-warning" },
  critical: { icon: OctagonExclamationPoint, className: "bg-critical-soft text-critical-fg border-critical/35", dot: "bg-critical" },
  maintenance_required: { icon: Wrench, className: "bg-maintenance-soft text-maintenance-fg border-maintenance/35", dot: "bg-maintenance" },
};

/** Equipment / process health state badge (AI-C01 states). Pass `count` to use as an alert counter. */
export function AlertBadge({ state, count, className }: { state: HealthState; count?: number; className?: string }) {
  const t = useT(common);
  const { icon: Icon, className: tone } = HEALTH_STYLE[state];
  return (
    <span
      data-health={state}
      className={cn("inline-flex items-center gap-1 rounded-md border px-1.5 py-px text-2xs leading-4 font-medium whitespace-nowrap", tone, className)}
    >
      <Icon className="size-3" aria-hidden />
      {t.health[state]}
      {count !== undefined ? <span className="tabular ml-0.5 rounded bg-current/10 px-1 font-semibold">{count}</span> : null}
    </span>
  );
}

export function healthDotClass(state: HealthState) {
  return HEALTH_STYLE[state].dot;
}
