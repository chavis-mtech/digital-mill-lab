"use client";

import { useId, useState, type ReactNode } from "react";
import { Table2 } from "lucide-react";
import { useT } from "@/lib/i18n/client";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ErrorState, EmptyState, LoadingState } from "@/components/states/states";
import common from "@/messages/common.i18n";

export type LinePattern = "solid" | "dashed" | "dotted" | "area" | "bar" | "marker";

export type LegendItem = {
  key: string;
  label: string;
  /** CSS colour (usually `var(--chart-N)` or a status/provenance token). */
  color: string;
  pattern?: LinePattern;
  hidden?: boolean;
  /** Non-toggleable items (bands, markers) are shown but not buttons. */
  toggleable?: boolean;
};

export type ChartTable = { caption?: string; columns: string[]; rows: (string | number | null)[][] };

export type ChartStateProps = {
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  empty?: boolean;
};

function Swatch({ color, pattern = "solid" }: { color: string; pattern?: LinePattern }) {
  if (pattern === "area" || pattern === "bar")
    return <span aria-hidden className={cn("inline-block size-2.5 shrink-0", pattern === "bar" ? "rounded-[2px]" : "rounded-sm opacity-60")} style={{ background: color }} />;
  if (pattern === "marker")
    return <span aria-hidden className="inline-block size-2.5 shrink-0 rotate-45 rounded-[1px] ring-2 ring-surface" style={{ background: color }} />;
  return (
    <svg aria-hidden width="18" height="8" className="shrink-0">
      <line
        x1="1"
        y1="4"
        x2="17"
        y2="4"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeDasharray={pattern === "dashed" ? "5 3" : pattern === "dotted" ? "1 3" : undefined}
      />
    </svg>
  );
}

/**
 * Accessible chart shell: <figure> + caption, keyboard-operable legend (buttons with aria-pressed), the
 * visual chart (aria-hidden) and a toggleable data table that carries the same numbers. All chart
 * components render through this — keep it that way so every chart has a non-visual equivalent.
 */
export function ChartFrame({
  title,
  description,
  summary,
  legend,
  onToggle,
  table,
  actions,
  height,
  children,
  className,
  loading,
  error,
  onRetry,
  empty,
}: {
  title: ReactNode;
  description?: ReactNode;
  /** One-sentence text summary for screen readers (e.g. "OER fell from 21.4% to 20.1% over 7 days"). */
  summary?: string;
  legend?: LegendItem[];
  onToggle?: (key: string) => void;
  table?: ChartTable;
  actions?: ReactNode;
  height: number;
  children: ReactNode;
  className?: string;
} & ChartStateProps) {
  const t = useT(common);
  const [showTable, setShowTable] = useState(false);
  const tableId = useId();
  const titleId = useId();

  let body: ReactNode = children;
  if (loading) body = <LoadingState height={height} />;
  else if (error) body = <ErrorState error={error} onRetry={onRetry} compact className="h-full" />;
  else if (empty) body = <EmptyState compact className="h-full" />;

  const ready = !loading && !error && !empty;

  return (
    <figure className={cn("flex min-w-0 flex-col gap-3", className)} aria-labelledby={titleId}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <figcaption className="min-w-0">
          <span id={titleId} className="block text-sm font-semibold text-foreground">
            {title}
          </span>
          {description ? <span className="mt-0.5 block text-xs text-muted-foreground">{description}</span> : null}
        </figcaption>
        <div className="flex items-center gap-1.5" data-print-hide>
          {actions}
          {table && ready ? (
            <Button variant="ghost" size="xs" aria-expanded={showTable} aria-controls={tableId} onClick={() => setShowTable((v) => !v)}>
              <Table2 aria-hidden />
              <span className="max-sm:sr-only">{showTable ? t.chart.hideTable : t.chart.showTable}</span>
            </Button>
          ) : null}
        </div>
      </div>

      {legend && legend.length > 0 && ready ? (
        <ul className="flex flex-wrap items-center gap-x-3 gap-y-1" aria-label={t.chart.legend}>
          {legend.map((item) => {
            const content = (
              <>
                <Swatch color={item.color} pattern={item.pattern} />
                <span className={cn(item.hidden && "line-through opacity-60")}>{item.label}</span>
              </>
            );
            return (
              <li key={item.key}>
                {item.toggleable !== false && onToggle ? (
                  <button
                    type="button"
                    aria-pressed={!item.hidden}
                    aria-label={t.chart.toggleSeries(item.label)}
                    onClick={() => onToggle(item.key)}
                    className="inline-flex items-center gap-1.5 rounded px-1 py-0.5 text-xs text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                  >
                    {content}
                  </button>
                ) : (
                  <span className="inline-flex items-center gap-1.5 px-1 py-0.5 text-xs text-muted-foreground">{content}</span>
                )}
              </li>
            );
          })}
        </ul>
      ) : null}

      <div style={{ minHeight: height }} className="relative">
        {summary && ready ? <p className="sr-only">{summary}</p> : null}
        {body}
      </div>

      {table && ready && showTable ? (
        <div id={tableId} tabIndex={0} role="region" aria-label={table.caption ?? t.chart.showTable} className="max-h-72 overflow-auto rounded-lg border border-border">
          <table className="tabular w-full text-left text-xs">
            {table.caption ? <caption className="sr-only">{table.caption}</caption> : null}
            <thead className="sticky top-0 bg-surface-2">
              <tr>
                {table.columns.map((c) => (
                  <th key={c} scope="col" className="px-3 py-2 font-semibold text-muted-foreground">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, i) => (
                <tr key={i} className="border-t border-border">
                  {row.map((cell, j) =>
                    j === 0 ? (
                      <th key={j} scope="row" className="px-3 py-1.5 font-normal whitespace-nowrap">
                        {cell ?? "—"}
                      </th>
                    ) : (
                      <td key={j} className="px-3 py-1.5 text-right">
                        {cell ?? "—"}
                      </td>
                    ),
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </figure>
  );
}
