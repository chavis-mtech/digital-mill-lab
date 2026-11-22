"use client";

/**
 * Small UI helpers shared by every frontend-ops feature (maintenance, logistics, energy, traceability, copilot,
 * prototypes). Display only — no business numbers are computed here (ADR-002).
 */
import { useId, type ComponentProps, type ReactNode } from "react";
import { UserCog } from "lucide-react";
import { useApiQuery } from "@/lib/api/hooks";
import { useDemo } from "@/lib/demo/context";
import { useLocale } from "@/lib/i18n/client";
import { ROLE_LABELS } from "@/lib/demo/constants";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { SeverityPill, type Severity } from "@/components/demo/severity";

/** Titled panel (Card with heading row and optional actions). */
export function Section({
  title,
  description,
  actions,
  children,
  className,
  id,
  "data-tour": dataTour,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  id?: string;
  "data-tour"?: string;
}) {
  const auto = useId();
  const headingId = `${id ?? auto}-title`;
  return (
    <section
      id={id}
      data-tour={dataTour}
      aria-labelledby={headingId}
      className={cn("flex min-w-0 scroll-mt-28 flex-col gap-3 rounded-xl border border-border bg-surface p-4 shadow-xs", className)}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 id={headingId} className="text-sm font-semibold tracking-tight text-foreground">
            {title}
          </h2>
          {description ? <p className="mt-0.5 text-xs text-muted-foreground">{description}</p> : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}

/** Marks API-provided English narrative so screen readers switch language. */
export function ApiText({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span lang="en" className={className}>
      {children}
    </span>
  );
}

/** Stat tile with an arbitrary badge row (used where a KpiValue is not available from the API). */
export function StatTile({ label, value, unit, foot, className }: { label: ReactNode; value: ReactNode; unit?: string; foot?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-2 rounded-xl border border-border bg-surface p-4 shadow-xs", className)}>
      <p className="text-xs leading-snug font-medium text-muted-foreground">{label}</p>
      <p className="tabular text-[1.625rem] leading-none font-semibold tracking-tight text-foreground">
        {value}
        {unit ? <span className="ml-1 text-sm font-medium text-muted-foreground">{unit}</span> : null}
      </p>
      {foot ? <div className="mt-auto flex flex-wrap items-center gap-1.5 pt-1 text-xs">{foot}</div> : null}
    </div>
  );
}

const FIELD = "h-9 w-full min-w-0 rounded-md border border-input bg-surface px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-50";

export function Field({ label, hint, children, className }: { label: ReactNode; hint?: ReactNode; children: (id: string) => ReactNode; className?: string }) {
  const id = useId();
  return (
    <div className={cn("flex min-w-0 flex-col gap-1", className)}>
      <label htmlFor={id} className="text-xs font-medium text-foreground">
        {label}
      </label>
      {children(id)}
      {hint ? <p className="text-2xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export function NativeSelect({ className, ...props }: ComponentProps<"select">) {
  return <select className={cn(FIELD, "pr-8", className)} {...props} />;
}

export function NativeInput({ className, ...props }: ComponentProps<"input">) {
  return <input className={cn(FIELD, className)} {...props} />;
}

export function TextArea({ className, ...props }: ComponentProps<"textarea">) {
  return <textarea className={cn(FIELD, "h-auto min-h-20 py-2 leading-relaxed", className)} {...props} />;
}

/** Role permissions from GET /demo/roles (server-side truth; the UI never hard-codes who may do what). */
export function usePermissions() {
  const { role } = useDemo();
  const q = useApiQuery("/api/v1/demo/roles", undefined, { withClock: false, staleTime: 5 * 60_000 });
  const mine = q.data?.items.find((r) => r.role === role);
  return {
    ready: Boolean(mine),
    role,
    roles: q.data?.items ?? [],
    can: (permission: string) => Boolean(mine?.permissions.includes(permission)),
    /** Roles (other than the current one) that hold the permission. */
    rolesWith: (permission: string) => (q.data?.items ?? []).filter((r) => r.permissions.includes(permission)).map((r) => r.role),
  };
}

/**
 * Explains a missing permission and offers a one-click switch of the SIMULATED viewpoint (never authentication).
 */
export function RoleGate({
  allowed,
  permission,
  needRole = "maintenance_engineer",
  message,
  switchLabel,
  className,
}: {
  allowed: boolean;
  permission: string;
  needRole?: Parameters<ReturnType<typeof useDemo>["setRole"]>[0];
  message: (roleLabel: string, permission: string) => string;
  switchLabel: (roleLabel: string) => string;
  className?: string;
}) {
  const { role, setRole } = useDemo();
  const { locale } = useLocale();
  if (allowed) return null;
  const current = ROLE_LABELS[role][locale];
  const target = ROLE_LABELS[needRole][locale];
  return (
    <div role="note" className={cn("flex flex-col gap-2 rounded-lg border border-warning/50 bg-warning-soft/60 p-3 text-xs sm:flex-row sm:items-center sm:justify-between", className)}>
      <p className="text-foreground">{message(current, permission)}</p>
      <Button size="sm" variant="outline" onClick={() => setRole(needRole)}>
        <UserCog aria-hidden /> {switchLabel(target)}
      </Button>
    </div>
  );
}

export function TileSkeleton() {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4" role="status">
      <Skeleton className="h-3.5 w-24" />
      <Skeleton className="h-7 w-20" />
    </div>
  );
}

/**
 * SeverityPill with an AA-safe critical style in dark mode (the kit's solid `bg-critical text-white` measures 3.15:1
 * on the dark theme). Same icon + text; only the critical colours are overridden. Reported as a kit request.
 */
export function OpsSeverityPill({ severity, className }: { severity: Severity; className?: string }) {
  return <SeverityPill severity={severity} className={cn(severity === "critical" && "border-critical/50 bg-critical-soft text-critical-fg dark:text-critical-fg", className)} />;
}
