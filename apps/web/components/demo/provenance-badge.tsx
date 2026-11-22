"use client";

import { CircleDot, SlidersHorizontal, TrendingUp, type LucideIcon } from "lucide-react";
import type { Schema } from "@dml/contracts";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import common from "@/messages/common.i18n";

export type Provenance = Schema<"Provenance">;
export type ProvenanceKind = Schema<"ProvenanceKind">;

/**
 * Provenance styling. Never colour alone: each kind has its own icon AND border/line pattern
 * (solid = observed synthetic actual, dashed = forecast, dotted = what-if). Charts reuse `PROVENANCE_STYLE`.
 */
export const PROVENANCE_STYLE: Record<
  ProvenanceKind,
  { icon: LucideIcon; border: string; text: string; bg: string; line: "solid" | "dashed" | "dotted"; cssVar: string }
> = {
  synthetic_actual: {
    icon: CircleDot,
    border: "border-solid border-prov-actual/45",
    text: "text-prov-actual",
    bg: "bg-prov-actual/8",
    line: "solid",
    cssVar: "--prov-actual",
  },
  forecast: {
    icon: TrendingUp,
    border: "border-dashed border-prov-forecast/70",
    text: "text-prov-forecast",
    bg: "bg-prov-forecast/8",
    line: "dashed",
    cssVar: "--prov-forecast",
  },
  what_if: {
    icon: SlidersHorizontal,
    border: "border-dotted border-prov-whatif/80",
    text: "text-prov-whatif",
    bg: "bg-prov-whatif/8",
    line: "dotted",
    cssVar: "--prov-whatif",
  },
};

type Props = {
  /** The API provenance object (preferred) … */
  provenance?: Provenance | null;
  /** … or just a kind (e.g. for legends). */
  kind?: ProvenanceKind;
  /** Hide the text label (icon + tooltip only). Use only where space is tight; the tooltip keeps it accessible. */
  compact?: boolean;
  className?: string;
};

/** Badge that states where a number comes from: synthetic actual / forecast / what-if (SPEC §4.A). */
export function ProvenanceBadge({ provenance, kind, compact = false, className }: Props) {
  const t = useT(common);
  const { locale } = useLocale();
  const k: ProvenanceKind = provenance?.kind ?? kind ?? "synthetic_actual";
  const style = PROVENANCE_STYLE[k];
  const Icon = style.icon;
  const label = t.provenance[k];
  const tip = k === "forecast" ? t.provenance.tooltipForecast : k === "what_if" ? t.provenance.tooltipWhatIf : t.provenance.tooltipActual;

  const badge = (
    <span
      data-provenance={k}
      className={cn(
        "inline-flex items-center gap-1 rounded-[5px] border px-1.5 py-px text-2xs leading-4 font-medium whitespace-nowrap",
        style.border,
        style.text,
        style.bg,
        className,
      )}
    >
      <Icon className="size-3 shrink-0" aria-hidden />
      {compact ? <span className="sr-only">{label}</span> : label}
    </span>
  );

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span tabIndex={0} className="inline-flex rounded-[5px] focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
          {badge}
        </span>
      </TooltipTrigger>
      <TooltipContent>
        <p className="font-medium">{label}</p>
        <p className="opacity-80">{tip}</p>
        {provenance ? (
          <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-2 opacity-90">
            <dt>{t.provenance.source}</dt>
            <dd className="font-mono text-[0.6875rem]">{provenance.source}</dd>
            <dt>{t.provenance.asOf}</dt>
            <dd>{formatDate(provenance.as_of, locale, "datetime")}</dd>
            {provenance.model_version ? (
              <>
                <dt>{t.provenance.model}</dt>
                <dd className="font-mono text-[0.6875rem]">{provenance.model_version}</dd>
              </>
            ) : null}
          </dl>
        ) : null}
      </TooltipContent>
    </Tooltip>
  );
}
