"use client";

import { type ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { Ban, Construction, Hourglass, Inbox, RotateCcw, ServerCrash, TriangleExclamationPoint, type LucideIcon } from "lucide-react";
import { useT } from "@/lib/i18n/client";
import { isApiRequestError, type ApiRequestError } from "@/lib/api/errors";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import common from "@/messages/common.i18n";

type FrameProps = {
  icon: LucideIcon;
  title: ReactNode;
  body?: ReactNode;
  tone?: "neutral" | "critical" | "warning" | "planned";
  action?: ReactNode;
  meta?: ReactNode;
  className?: string;
  compact?: boolean;
  role?: "status" | "alert";
};

function StateFrame({ icon: Icon, title, body, tone = "neutral", action, meta, className, compact, role = "status" }: FrameProps) {
  return (
    <div
      role={role}
      className={cn(
        "flex flex-col items-center justify-center gap-2 rounded-lg border text-center",
        compact ? "px-4 py-5" : "px-6 py-10",
        tone === "planned" ? "border-dashed border-border-strong bg-surface-2/60" : "border-border bg-surface",
        className,
      )}
    >
      <span
        className={cn(
          "flex size-9 items-center justify-center rounded-full",
          tone === "critical" && "bg-critical-soft text-critical-fg",
          tone === "warning" && "bg-warning-soft text-warning-fg",
          tone === "neutral" && "bg-surface-2 text-muted-foreground",
          tone === "planned" && "bg-neutral-soft text-neutral-fg",
        )}
      >
        <Icon className="size-4.5" aria-hidden />
      </span>
      <p className="text-sm font-semibold text-foreground">{title}</p>
      {body ? <p className="max-w-md text-xs leading-relaxed text-muted-foreground">{body}</p> : null}
      {meta ? <div className="text-2xs text-subtle-foreground">{meta}</div> : null}
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  );
}

export function EmptyState({ title, body, action, className, compact }: { title?: ReactNode; body?: ReactNode; action?: ReactNode; className?: string; compact?: boolean }) {
  const t = useT(common);
  return <StateFrame icon={Inbox} title={title ?? t.states.emptyTitle} body={body ?? t.states.emptyBody} action={action} className={className} compact={compact} />;
}

/** Contract stub (HTTP 501). Shows owner + task from the envelope so reviewers know who builds it. */
export function NotImplementedState({
  owner,
  task,
  title,
  body,
  className,
  compact,
}: {
  owner?: string;
  task?: string;
  title?: ReactNode;
  body?: ReactNode;
  className?: string;
  compact?: boolean;
}) {
  const t = useT(common);
  return (
    <StateFrame
      icon={Construction}
      tone="planned"
      title={title ?? t.states.notImplementedTitle}
      body={body ?? t.states.notImplementedBody}
      className={className}
      compact={compact}
      meta={
        owner || task ? (
          <span className="font-mono">
            {owner ? `${t.states.owner}: ${owner}` : null}
            {owner && task ? " · " : null}
            {task ? `${t.states.task}: ${task}` : null}
          </span>
        ) : undefined
      }
    />
  );
}

/** Maps any error (preferably ApiRequestError) to the right state. */
export function ErrorState({ error, onRetry, className, compact }: { error: unknown; onRetry?: () => void; className?: string; compact?: boolean }) {
  const t = useT(common);
  if (isApiRequestError(error)) {
    if (error.isNotImplemented) return <NotImplementedState {...error.stubInfo} className={className} compact={compact} />;
    const retry = onRetry ? (
      <Button variant="outline" size="sm" onClick={onRetry}>
        <RotateCcw aria-hidden /> {t.states.retry}
      </Button>
    ) : undefined;
    const meta = error.requestId ? <span className="font-mono">{`${t.states.requestId}: ${error.requestId}`}</span> : undefined;
    if (error.isUnavailable)
      return <StateFrame icon={ServerCrash} tone="warning" role="alert" title={t.states.unavailableTitle} body={t.states.unavailableBody} action={retry} className={className} compact={compact} />;
    if (error.isForbidden)
      return <StateFrame icon={Ban} tone="warning" title={t.states.forbiddenTitle} body={t.states.forbiddenBody} meta={meta} className={className} compact={compact} />;
    if (error.isRateLimited)
      return <StateFrame icon={Hourglass} tone="warning" title={t.states.rateLimitedTitle} body={t.states.rateLimitedBody} action={retry} className={className} compact={compact} />;
    return (
      <StateFrame
        icon={TriangleExclamationPoint}
        tone="critical"
        role="alert"
        title={t.states.errorTitle}
        body={error.message || t.states.errorBody}
        meta={meta}
        action={retry}
        className={className}
        compact={compact}
      />
    );
  }
  return (
    <StateFrame
      icon={TriangleExclamationPoint}
      tone="critical"
      role="alert"
      title={t.states.errorTitle}
      body={t.states.errorBody}
      action={
        onRetry ? (
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RotateCcw aria-hidden /> {t.states.retry}
          </Button>
        ) : undefined
      }
      className={className}
      compact={compact}
    />
  );
}

/** Generic skeleton block with an accessible "loading" status. `lines` renders text-like rows. */
export function LoadingState({ className, lines = 3, height }: { className?: string; lines?: number; height?: number | string }) {
  const t = useT(common);
  return (
    <div role="status" aria-live="polite" className={cn("flex flex-col gap-2", className)} style={height ? { minHeight: height } : undefined}>
      <span className="sr-only">{t.states.loading}</span>
      {height ? <Skeleton className="h-full min-h-24 w-full flex-1" /> : null}
      {!height
        ? Array.from({ length: lines }, (_, i) => <Skeleton key={i} className={cn("h-4", i === lines - 1 ? "w-2/3" : "w-full")} />)
        : null}
    </div>
  );
}

/**
 * Render a TanStack query with all four states handled: loading → <LoadingState>, 501 → <NotImplementedState>,
 * other errors → <ErrorState> (with retry), empty → <EmptyState>, else `children(data)`.
 *
 * @example <QueryState query={q} isEmpty={(d) => d.items.length === 0}>{(d) => <Table rows={d.items} />}</QueryState>
 */
export function QueryState<T>({
  query,
  children,
  isEmpty,
  loading,
  empty,
  compact,
  className,
}: {
  query: UseQueryResult<T, ApiRequestError>;
  children: (data: T) => ReactNode;
  isEmpty?: (data: T) => boolean;
  loading?: ReactNode;
  empty?: ReactNode;
  compact?: boolean;
  className?: string;
}) {
  if (query.isPending) return <>{loading ?? <LoadingState className={className} />}</>;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} compact={compact} className={className} />;
  if (isEmpty?.(query.data)) return <>{empty ?? <EmptyState compact={compact} className={className} />}</>;
  return <>{children(query.data)}</>;
}
