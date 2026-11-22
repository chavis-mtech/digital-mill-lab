"use client";

import { Calculator, FlaskConical, Radio, ShieldCheck, UserRound, Building, Gauge, type LucideIcon } from "lucide-react";
import { useT } from "@/lib/i18n/client";
import { cn } from "@/lib/utils";
import common from "@/messages/common.i18n";

export type DisclaimerKind = "roi" | "synthetic" | "advisory" | "simulatedLive" | "roles" | "independent" | "riskScore";

const ICONS: Record<DisclaimerKind, LucideIcon> = {
  roi: Calculator,
  synthetic: FlaskConical,
  advisory: ShieldCheck,
  simulatedLive: Radio,
  roles: UserRound,
  independent: Building,
  riskScore: Gauge,
};

/**
 * Standard disclaimers with the exact wording from SPEC §0 / GET /api/v1/meta. `kind="roi"` renders the
 * mandatory ROI sentence: "Illustrative business scenario based on adjustable assumptions, not verified
 * any company's financial results." Place it directly above/below every ROI or business-value figure.
 */
export function Disclaimer({ kind, className, variant = "inline" }: { kind: DisclaimerKind; className?: string; variant?: "inline" | "block" }) {
  const t = useT(common);
  const Icon = ICONS[kind];
  return (
    <p
      role="note"
      data-disclaimer={kind}
      className={cn(
        "flex items-start gap-2 text-xs leading-relaxed text-muted-foreground",
        variant === "block" && "rounded-lg border border-border bg-surface-2 px-3 py-2",
        className,
      )}
    >
      <Icon className="mt-0.5 size-3.5 shrink-0" aria-hidden />
      <span>{t.disclaimer[kind]}</span>
    </p>
  );
}
