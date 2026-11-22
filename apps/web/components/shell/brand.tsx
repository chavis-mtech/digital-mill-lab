import Link from "next/link";
import { cn } from "@/lib/utils";

/**
 * Product mark for this independent concept (an abstract process-flow glyph). Deliberately NOT a
 * company logo — we have no rights to company marks (SPEC §0 rule 1).
 */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden className={cn("size-7 shrink-0", className)}>
      <rect width="32" height="32" rx="8" className="fill-primary" />
      <path d="M8 21.5V14m5.33 7.5V10.5m5.34 11V16m5.33 5.5V12.5" className="stroke-primary-foreground" strokeWidth="2.4" strokeLinecap="round" />
      <circle cx="24" cy="9" r="2.4" className="fill-accent" />
    </svg>
  );
}

export function Brand({ href = "/", compact = false, className }: { href?: string; compact?: boolean; className?: string }) {
  return (
    <Link href={href} className={cn("flex min-w-0 items-center gap-2.5 rounded-md focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none", className)}>
      <BrandMark />
      {!compact ? (
        <span className="flex min-w-0 flex-col leading-none">
          <span className="truncate text-[0.875rem] font-semibold tracking-tight text-foreground">Digital Mill Lab</span>
          <span className="mt-0.5 truncate text-[0.625rem] font-medium tracking-wide text-muted-foreground uppercase">Independent concept · Synthetic data</span>
        </span>
      ) : null}
    </Link>
  );
}
