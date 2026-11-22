"use client";

import { useApiQuery } from "@/lib/api/hooks";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import common from "@/messages/common.i18n";

/** Live health of the API via GET /api/v1/meta (implemented). Polls every 30 s. */
export function useMeta() {
  return useApiQuery("/api/v1/meta", undefined, { withClock: false, refetchInterval: 30_000, staleTime: 25_000 });
}

export function MetaIndicator({ className, detailed = false }: { className?: string; detailed?: boolean }) {
  const t = useT(common);
  const { locale } = useLocale();
  const q = useMeta();
  const state = q.isPending ? "checking" : q.isError ? "offline" : "online";
  return (
    <div className={cn("flex flex-col gap-1 text-2xs", className)} role="status" aria-live="polite">
      <span className="inline-flex items-center gap-1.5 font-medium text-muted-foreground">
        <span
          aria-hidden
          className={cn(
            "size-2 rounded-full",
            state === "online" && "bg-success shadow-[0_0_0_3px_var(--success-soft)]",
            state === "offline" && "bg-critical",
            state === "checking" && "animate-pulse bg-border-strong",
          )}
        />
        {t.meta.api}: {state === "online" ? t.meta.online : state === "offline" ? t.meta.offline : t.meta.checking}
        {q.data ? <span className="font-mono text-subtle-foreground">v{q.data.version}</span> : null}
      </span>
      {detailed && q.data ? (
        <dl className="tabular grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-subtle-foreground">
          <dt>{t.meta.dataWindow}</dt>
          <dd>
            {formatDate(q.data.data_window.start_date, locale)} – {formatDate(q.data.data_window.end_date, locale)} ({t.meta.days(q.data.data_window.days)})
          </dd>
          <dt>{t.meta.copilotMode}</dt>
          <dd>{q.data.copilot_mode}</dd>
        </dl>
      ) : null}
    </div>
  );
}
