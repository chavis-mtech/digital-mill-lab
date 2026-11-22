"use client";

import Link from "next/link";
import { ArrowDownRight, ArrowRight, ArrowUpRight, ChevronRight } from "lucide-react";
import type { Schema } from "@dml/contracts";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatNumber, formatSigned, formatValue } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ProvenanceBadge } from "@/components/demo/provenance-badge";
import { StatusChip } from "@/components/demo/status-chip";
import { SeverityPill } from "@/components/demo/severity";
import { Sparkline } from "@/components/charts/charts";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/states/states";
import type { FeatureKey } from "@/content/status";
import common from "@/messages/common.i18n";

export type KpiValue = Schema<"KpiValue">;

/**
 * KPI tile: value + unit, delta vs previous period (direction judged by the API's `good_direction`, never
 * re-derived here), optional sparkline, provenance badge and maturity chip. Pass the `KpiValue` straight
 * from the API. Interpretation of "better/worse" uses only good_direction + delta sign.
 */
export function KpiCard({
  kpi,
  label,
  sparkline,
  feature,
  href,
  loading,
  error,
  digits,
  className,
  "data-tour": dataTour,
}: {
  kpi?: KpiValue | null;
  /** Override the API label (e.g. a localised label). */
  label?: string;
  sparkline?: Schema<"SeriesPoint">[];
  /** Show the maturity chip of a feature (content/status.ts). */
  feature?: FeatureKey;
  /** Drill-down link. */
  href?: string;
  loading?: boolean;
  error?: unknown;
  digits?: number;
  className?: string;
  "data-tour"?: string;
}) {
  const t = useT(common);
  const { locale } = useLocale();

  if (loading)
    return (
      <div className={cn("flex flex-col gap-3 rounded-xl border border-border bg-surface p-4", className)} role="status" aria-label={t.states.loading}>
        <Skeleton className="h-3.5 w-24" />
        <Skeleton className="h-7 w-32" />
        <Skeleton className="h-3 w-40" />
      </div>
    );
  if (error) return <ErrorState error={error} compact className={className} />;

  const delta = kpi?.delta ?? null;
  const hasDelta = delta !== null && delta !== 0 && kpi?.good_direction !== "flat";
  const good = hasDelta ? (kpi!.good_direction === "up" ? delta! > 0 : delta! < 0) : null;
  const DeltaIcon = delta === null || delta === 0 ? ArrowRight : delta > 0 ? ArrowUpRight : ArrowDownRight;
  const moved = delta !== null && delta !== 0;
  // A neutral ("flat") KPI that moved is "changed", never "unchanged".
  const verdict = good === null ? (moved ? t.kpi.changed : t.kpi.unchanged) : good ? t.kpi.better : t.kpi.worse;

  const body = (
    <>
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs leading-snug font-medium text-muted-foreground">{label ?? kpi?.label ?? t.kpi.noData}</p>
        {kpi?.status && kpi.status !== "info" ? <SeverityPill severity={kpi.status} /> : null}
      </div>
      <div className="flex items-end justify-between gap-3">
        <p className="tabular text-[1.625rem] leading-none font-semibold tracking-tight text-foreground">
          {formatNumber(kpi?.value ?? null, locale, { digits })}
          {kpi?.unit && kpi.value != null ? <span className="ml-1 text-sm font-medium text-muted-foreground">{kpi.unit}</span> : null}
        </p>
        {sparkline ? <Sparkline points={sparkline} kind={kpi?.provenance.kind} label={`${kpi?.label ?? ""} — ${t.kpi.trend}`} /> : null}
      </div>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
        {kpi && delta !== null ? (
          <span
            className={cn(
              "tabular inline-flex items-center gap-0.5 font-medium",
              good === true && "text-success-fg",
              good === false && "text-critical-fg",
              good === null && "text-muted-foreground",
            )}
          >
            <DeltaIcon className="size-3.5" aria-hidden />
            {formatSigned(delta, locale, digits ?? 1)}
            {kpi.delta_pct != null ? ` (${formatSigned(kpi.delta_pct, locale, 1)}%)` : ""}
            <span className="sr-only">
              {" "}
              {verdict}, {t.kpi.vsPrevious} {formatValue(kpi.previous ?? null, kpi.unit, locale)}
            </span>
          </span>
        ) : null}
        {kpi && delta !== null ? <span className="text-subtle-foreground" aria-hidden>{t.kpi.vsPrevious}</span> : null}
      </div>
      <div className="mt-auto flex flex-wrap items-center gap-1.5 pt-1">
        {kpi ? <ProvenanceBadge provenance={kpi.provenance} /> : null}
        {feature ? <StatusChip feature={feature} /> : null}
        {kpi?.target != null ? (
          <span className="tabular text-2xs text-subtle-foreground">
            {t.kpi.target}: {formatValue(kpi.target, kpi.unit, locale)}
          </span>
        ) : null}
        {href ? <ChevronRight className="ml-auto size-4 text-subtle-foreground transition-transform group-hover:translate-x-0.5" aria-hidden /> : null}
      </div>
    </>
  );

  const cls = cn("group flex min-w-0 flex-col gap-2.5 rounded-xl border border-border bg-surface p-4 shadow-xs", className);
  return href ? (
    <Link href={href} data-tour={dataTour} className={cn(cls, "transition-[border-color,box-shadow] hover:border-border-strong hover:shadow-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none")} aria-label={`${label ?? kpi?.label ?? ""} — ${t.kpi.drillDown}`}>
      {body}
    </Link>
  ) : (
    <div className={cls} data-tour={dataTour}>
      {body}
    </div>
  );
}
