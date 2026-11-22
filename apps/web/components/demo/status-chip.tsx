"use client";

import { CircleCheck, CircleDashed, Contrast, FlaskConical, type LucideIcon } from "lucide-react";
import { useLocale, useT } from "@/lib/i18n/client";
import { cn } from "@/lib/utils";
import { FEATURES, type FeatureEntry, type FeatureKey, type FeatureStatus } from "@/content/status";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import common from "@/messages/common.i18n";

export const STATUS_STYLE: Record<FeatureStatus, { icon: LucideIcon; className: string }> = {
  implemented: { icon: CircleCheck, className: "border-success/35 bg-success-soft text-success-fg" },
  partial: { icon: Contrast, className: "border-info/35 bg-info-soft text-info-fg" },
  prototype: { icon: FlaskConical, className: "border-maintenance/35 bg-maintenance-soft text-maintenance-fg" },
  planned: { icon: CircleDashed, className: "border-dashed border-border-strong bg-neutral-soft text-neutral-fg" },
};

type Props = { className?: string; size?: "sm" | "md"; showTooltip?: boolean } & (
  | { feature: FeatureKey; status?: never }
  | { status: FeatureStatus; feature?: never }
);

/**
 * Feature-maturity chip. Pass `feature` to read the single source of truth (`content/status.ts`); pass a raw
 * `status` only for legends. Shows the target maturity for P2 concepts (e.g. "Planned → Prototype").
 */
export function StatusChip({ feature, status, className, size = "sm", showTooltip = true }: Props) {
  const t = useT(common);
  const { locale } = useLocale();
  const entry: FeatureEntry | undefined = feature ? FEATURES[feature] : undefined;
  const s: FeatureStatus = entry?.status ?? status ?? "planned";
  const target = entry?.target;
  const { icon: Icon, className: tone } = STATUS_STYLE[s];

  const chip = (
    <span
      data-status={s}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border font-medium whitespace-nowrap",
        size === "sm" ? "px-2 py-px text-2xs leading-4" : "px-2.5 py-0.5 text-xs",
        tone,
        className,
      )}
    >
      <Icon className={size === "sm" ? "size-3" : "size-3.5"} aria-hidden />
      {t.status[s]}
      {target && target !== s ? (
        <span>
          {" → "}
          {t.status[target]}
        </span>
      ) : null}
    </span>
  );

  if (!entry || !showTooltip) return chip;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span tabIndex={0} className="inline-flex rounded-full focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
          {chip}
        </span>
      </TooltipTrigger>
      <TooltipContent>
        <p className="font-medium">{entry.label[locale]}</p>
        {entry.note ? <p className="opacity-85">{entry.note[locale]}</p> : null}
        <p className="mt-1 font-mono text-[0.6875rem] opacity-75">
          {entry.owner}
          {entry.tasks.length ? ` · ${entry.tasks.join(", ")}` : ""}
        </p>
      </TooltipContent>
    </Tooltip>
  );
}

/** Legend of the four maturity levels. */
export function StatusLegend({ className }: { className?: string }) {
  const t = useT(common);
  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)} role="group" aria-label={t.status.legend}>
      {(["implemented", "partial", "prototype", "planned"] as const).map((s) => (
        <StatusChip key={s} status={s} />
      ))}
    </div>
  );
}
