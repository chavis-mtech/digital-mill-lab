"use client";

import { Sigma } from "lucide-react";
import type { Schema } from "@dml/contracts";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatNumber, formatValue } from "@/lib/format";
import { cn } from "@/lib/utils";
import common from "@/messages/common.i18n";

export type Formula = Schema<"Formula">;

/**
 * Shows formulas returned by the API (expression + named inputs + result). Pure display — the UI never
 * evaluates the expression (ADR-002). Used by scenario, ROI, maintenance and energy what-ifs.
 */
export function FormulaPanel({ formulas, title, className }: { formulas: Formula[]; title?: string; className?: string }) {
  const t = useT(common);
  const { locale } = useLocale();
  return (
    <section className={cn("flex flex-col gap-3 rounded-xl border border-border bg-surface p-4", className)} aria-label={title ?? t.formula.title}>
      <div className="flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold">
          <Sigma className="size-4 text-muted-foreground" aria-hidden />
          {title ?? t.formula.title}
        </h3>
        <span className="text-2xs text-subtle-foreground">{t.formula.calculatedBy}</span>
      </div>
      <ol className="flex flex-col gap-3">
        {formulas.map((f) => (
          <li key={f.key} className="rounded-lg bg-surface-2 p-3">
            <p className="text-xs font-medium">{f.label}</p>
            <code className="mt-1 block overflow-x-auto font-mono text-[0.75rem] whitespace-pre text-accent-text">{f.expression}</code>
            <div className="mt-2 grid gap-2 sm:grid-cols-[1fr_auto] sm:items-end">
              <dl className="tabular grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs" aria-label={t.formula.inputs}>
                {Object.entries(f.inputs).map(([k, v]) => (
                  <div key={k} className="contents">
                    <dt className="font-mono text-muted-foreground">{k}</dt>
                    <dd>{typeof v === "number" ? formatNumber(v, locale) : (v ?? "—")}</dd>
                  </div>
                ))}
              </dl>
              <p className="tabular text-right text-sm">
                <span className="text-xs text-muted-foreground">{t.formula.result} = </span>
                <span className="font-semibold">{formatValue(f.result, f.unit, locale)}</span>
              </p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
