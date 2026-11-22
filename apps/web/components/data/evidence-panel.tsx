"use client";

import { CircleQuestionMark } from "lucide-react";
import type { Schema } from "@dml/contracts";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatDate, formatNumber, formatValue } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import common from "@/messages/common.i18n";

export type Evidence = Schema<"Evidence">;
export type Assumption = Schema<"Assumption">;

/**
 * Evidence + assumptions + possible contributing factors (SPEC §0 rule 7: anomaly ≠ proven cause).
 * The factors heading always reads "Possible contributing factors — not proven causes".
 */
export function EvidencePanel({
  evidence = [],
  factors = [],
  assumptions = [],
  title,
  className,
}: {
  evidence?: Evidence[];
  /** Free-text possible contributing factors from the API (never computed in the UI). */
  factors?: string[];
  assumptions?: Assumption[];
  title?: string;
  className?: string;
}) {
  const t = useT(common);
  const { locale } = useLocale();

  return (
    <section className={cn("flex flex-col gap-4 rounded-xl border border-border bg-surface p-4", className)} aria-label={title ?? t.evidence.title}>
      <div>
        <h3 className="mb-2 text-sm font-semibold">{title ?? t.evidence.title}</h3>
        {evidence.length === 0 ? (
          <p className="text-xs text-muted-foreground">{t.evidence.none}</p>
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {evidence.map((e, i) => {
              const out =
                e.normal_range && e.observed != null && ((e.normal_range.low != null && e.observed < e.normal_range.low) || (e.normal_range.high != null && e.observed > e.normal_range.high));
              return (
                <li key={`${e.metric}-${i}`} className="grid gap-1 py-2.5 first:pt-0 last:pb-0 sm:grid-cols-[1fr_auto] sm:items-baseline sm:gap-4">
                  <div className="min-w-0">
                    <p className="text-[0.8125rem] font-medium">{e.label}</p>
                    {e.entity ? <p className="text-2xs text-muted-foreground">{e.entity.label}</p> : null}
                    {e.note ? <p className="mt-0.5 text-xs text-muted-foreground">{e.note}</p> : null}
                    {e.window_start ? (
                      <p className="text-2xs text-subtle-foreground">
                        {formatDate(e.window_start, locale, "datetime")}
                        {e.window_end ? ` – ${formatDate(e.window_end, locale, "datetime")}` : ""}
                      </p>
                    ) : null}
                  </div>
                  <dl className="tabular grid grid-cols-[auto_auto] gap-x-3 text-xs sm:text-right">
                    <dt className="text-muted-foreground">{t.evidence.observed}</dt>
                    <dd className={cn("font-semibold", out ? "text-critical-fg" : "text-foreground")}>{formatValue(e.observed, e.unit, locale)}</dd>
                    {e.expected != null ? (
                      <>
                        <dt className="text-muted-foreground">{t.evidence.expected}</dt>
                        <dd>{formatValue(e.expected, e.unit, locale)}</dd>
                      </>
                    ) : null}
                    {e.normal_range ? (
                      <>
                        <dt className="text-muted-foreground">{t.evidence.normalRange}</dt>
                        <dd title={`${t.evidence.basis}: ${e.normal_range.basis}`}>
                          {formatNumber(e.normal_range.low ?? null, locale)} – {formatValue(e.normal_range.high ?? null, e.normal_range.unit, locale)}
                        </dd>
                      </>
                    ) : null}
                  </dl>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {factors.length > 0 ? (
        <div className="rounded-lg border border-dashed border-warning/50 bg-warning-soft/50 p-3">
          <h4 className="flex items-center gap-1.5 text-xs font-semibold text-warning-fg">
            <CircleQuestionMark className="size-3.5" aria-hidden />
            {t.evidence.factorsTitle}
          </h4>
          <ul className="mt-1.5 list-disc space-y-0.5 pl-5 text-xs text-foreground">
            {factors.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
          <p className="mt-1.5 text-2xs text-muted-foreground">{t.evidence.factorsNote}</p>
        </div>
      ) : null}

      {assumptions.length > 0 ? (
        <div>
          <h4 className="mb-1.5 text-xs font-semibold">{t.evidence.assumptionsTitle}</h4>
          <ul className="flex flex-col gap-1.5">
            {assumptions.map((a) => (
              <li key={a.key} className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
                <span className="text-muted-foreground">{a.label}</span>
                <span className="tabular font-medium">{typeof a.value === "number" ? formatValue(a.value, a.unit, locale) : (a.value ?? "—")}</span>
                <Badge tone="outline">{t.factTag[a.tag]}</Badge>
                {a.source ? <span className="font-mono text-2xs text-subtle-foreground">{a.source}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
