"use client";

import { SeverityPill as KitSeverityPill, type Severity } from "@/components/demo/severity";
import { cn } from "@/lib/utils";

/**
 * Kit SeverityPill with an AA-contrast fix for "critical" in dark mode (white on the light dark-theme red
 * measures 3.15:1 in axe). Workaround inside frontend-exec; the kit fix is requested in docs/status/frontend-exec.md.
 */
export function SeverityPill({ severity, className }: { severity: Severity; className?: string }) {
  return <KitSeverityPill severity={severity} className={cn(severity === "critical" && "dark:text-[oklch(0.18_0.02_25)]", className)} />;
}
