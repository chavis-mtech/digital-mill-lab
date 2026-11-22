"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Titled panel used across frontend-exec pages (a Card with a heading row and optional actions). */
export function Section({
  title,
  description,
  actions,
  children,
  className,
  id,
  "data-tour": dataTour,
  as: Tag = "section",
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  id?: string;
  "data-tour"?: string;
  as?: "section" | "div";
}) {
  const headingId = id ? `${id}-title` : undefined;
  return (
    <Tag
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
    </Tag>
  );
}

/** Marks API-provided English narrative text so screen readers switch language and TH users see a hint. */
export function ApiText({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span lang="en" className={className}>
      {children}
    </span>
  );
}
