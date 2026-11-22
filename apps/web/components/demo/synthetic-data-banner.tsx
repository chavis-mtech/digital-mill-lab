"use client";

import { FlaskConical, Info } from "lucide-react";
import { useT } from "@/lib/i18n/client";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import common from "@/messages/common.i18n";

/**
 * Persistent honesty banner (SPEC §0 rule 2). Mounted by the demo/docs shell on every page — do not
 * remove or hide it in feature pages.
 */
export function SyntheticDataBanner({ className }: { className?: string }) {
  const t = useT(common);
  return (
    <div
      role="note"
      aria-label={t.banner.synthetic}
      data-synthetic-banner
      className={cn(
        "flex h-[var(--banner-h)] items-center justify-center gap-2 border-b border-warning/30 bg-warning-soft px-4 text-xs font-medium text-warning-fg",
        className,
      )}
    >
      <FlaskConical className="size-3.5 shrink-0" aria-hidden />
      <span className="line-clamp-2 text-center leading-tight sm:truncate">{t.banner.synthetic}</span>
      <Popover>
        <PopoverTrigger className="inline-flex shrink-0 items-center gap-1 rounded px-1 underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
          <Info className="size-3.5" aria-hidden />
          <span className="max-sm:sr-only">{t.banner.details}</span>
        </PopoverTrigger>
        <PopoverContent className="text-xs leading-relaxed text-foreground">{t.banner.detailsBody}</PopoverContent>
      </Popover>
    </div>
  );
}
