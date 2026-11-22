"use client";

import Link from "next/link";
import { Construction } from "lucide-react";
import { useLocale, useT } from "@/lib/i18n/client";
import { findRoute } from "@/content/routes";
import { FEATURES } from "@/content/status";
import { AIWorkspaceLayout, DocsLayout, ExecutiveLayout, OperationsLayout } from "./layouts";
import { Button } from "@/components/ui/button";
import common from "@/messages/common.i18n";

/**
 * Placeholder for demo/docs routes not built yet (the build plan placeholder rule). Route owners REPLACE their
 * page.tsx wholesale — do not extend this component. It renders the route's real layout so navigation and
 * the shell look right, plus an honest "not built yet" state with owner and task ids.
 */
export function RoutePlaceholder({ route }: { route: string }) {
  const { locale } = useLocale();
  const t = useT(common);
  const entry = findRoute(route);
  const feature = entry ? FEATURES[entry.feature] : undefined;

  const body = (
    <div role="status" className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-border-strong bg-surface-2/50 px-6 py-14 text-center" data-placeholder={route}>
      <span className="flex size-10 items-center justify-center rounded-full bg-neutral-soft text-neutral-fg">
        <Construction className="size-5" aria-hidden />
      </span>
      <p className="text-base font-semibold">{t.states.notBuiltTitle}</p>
      <p className="max-w-lg text-sm text-muted-foreground">{t.states.notBuiltBody}</p>
      {feature ? (
        <p className="font-mono text-2xs text-subtle-foreground">
          {t.states.owner}: {entry?.owner} · {t.states.task}: {feature.tasks.join(", ") || "—"}
        </p>
      ) : null}
      <Button asChild variant="outline" size="sm" className="mt-2">
        <Link href="/demo">{t.nav.demoHub}</Link>
      </Button>
      <span className="sr-only">{entry?.title[locale]}</span>
    </div>
  );

  switch (entry?.layout) {
    case "executive":
      return <ExecutiveLayout route={route}>{body}</ExecutiveLayout>;
    case "ai":
      return <AIWorkspaceLayout route={route}>{body}</AIWorkspaceLayout>;
    case "docs":
      return <DocsLayout route={route}>{body}</DocsLayout>;
    default:
      return <OperationsLayout route={route}>{body}</OperationsLayout>;
  }
}
