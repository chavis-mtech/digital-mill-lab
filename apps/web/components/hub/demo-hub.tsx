"use client";

import Link from "next/link";
import { ArrowUpRight, Compass, ShieldCheck } from "lucide-react";
import { useLocale, useT } from "@/lib/i18n/client";
import { DEMO_ROUTES, NAV_GROUPS, type NavGroupKey } from "@/content/routes";
import { FEATURES, type FeatureKey } from "@/content/status";
import { ExecutiveLayout } from "@/components/layouts/layouts";
import { StatusChip, StatusLegend } from "@/components/demo/status-chip";
import { Disclaimer } from "@/components/demo/disclaimer";
import { StartTourButton } from "@/components/tour/tour";
import { MetaIndicator } from "@/components/shell/meta-indicator";
import { ROUTE_ICONS } from "@/components/shell/icons";
import hub from "@/messages/hub.i18n";

const P2: FeatureKey[] = ["cv_grading", "smart_plantation", "petroleum_inventory", "port_scheduling", "group_data_platform"];
const PLATFORM: FeatureKey[] = ["synthetic_data", "api_contract", "session_sandbox", "simulated_live", "guided_tour", "integration_contracts"];

export function DemoHub() {
  const t = useT(hub);
  const { locale } = useLocale();
  const groups = Array.from(new Set(DEMO_ROUTES.map((r) => r.group))) as NavGroupKey[];

  return (
    <ExecutiveLayout title={t.title} description={t.description} breadcrumbs={false} actions={<StatusLegend />}>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <section className="relative overflow-hidden rounded-xl border border-accent/30 bg-accent-soft/60 p-5 md:col-span-2">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="flex items-center gap-2 text-base font-semibold">
                <Compass className="size-4 text-accent-text" aria-hidden />
                {t.tourTitle}
              </h2>
              <p className="mt-1 max-w-xl text-sm text-muted-foreground">{t.tourBody}</p>
            </div>
            <StartTourButton variant="accent" size="lg" />
          </div>
        </section>
        <section className="flex flex-col gap-2 rounded-xl border border-border bg-surface p-5">
          <h2 className="text-sm font-semibold">{t.systemTitle}</h2>
          <p className="text-2xs text-subtle-foreground">{t.systemBody}</p>
          <MetaIndicator detailed className="text-xs" />
        </section>
      </div>

      {groups.map((g) => (
        <section key={g} aria-labelledby={`hub-${g}`} className="flex flex-col gap-3">
          <h2 id={`hub-${g}`} className="text-xs font-semibold tracking-[0.08em] text-muted-foreground uppercase">
            {NAV_GROUPS[g][locale]}
          </h2>
          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {DEMO_ROUTES.filter((r) => r.group === g).map((r) => {
              const Icon = ROUTE_ICONS[r.icon];
              return (
                <li key={r.path}>
                  <Link
                    href={r.path}
                    className="group flex h-full flex-col gap-3 rounded-xl border border-border bg-surface p-4 shadow-xs transition-[border-color,box-shadow,transform] hover:-translate-y-px hover:border-border-strong hover:shadow-md focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="flex size-9 items-center justify-center rounded-lg bg-surface-2 text-foreground">
                        <Icon className="size-4.5" aria-hidden />
                      </span>
                      <StatusChip feature={r.feature} showTooltip={false} />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold">{r.title[locale]}</h3>
                      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{r.description[locale]}</p>
                    </div>
                    <span className="mt-auto inline-flex items-center gap-1 text-xs font-medium text-accent-text">
                      {t.open}
                      <ArrowUpRight className="size-3.5 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" aria-hidden />
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>
      ))}

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <section className="rounded-xl border border-border bg-surface p-5">
          <h2 className="text-sm font-semibold">{t.platform}</h2>
          <ul className="mt-3 flex flex-col divide-y divide-border">
            {PLATFORM.map((k) => (
              <li key={k} className="flex items-center justify-between gap-3 py-2 text-[0.8125rem]">
                <span>{FEATURES[k].label[locale]}</span>
                <StatusChip feature={k} />
              </li>
            ))}
          </ul>
        </section>
        <section className="rounded-xl border border-dashed border-border-strong bg-surface-2/50 p-5">
          <h2 className="text-sm font-semibold">{t.concepts}</h2>
          <p className="mt-1 text-xs text-muted-foreground">{t.conceptsNote}</p>
          <ul className="mt-3 flex flex-col divide-y divide-border">
            {P2.map((k) => (
              <li key={k} className="flex items-center justify-between gap-3 py-2 text-[0.8125rem]">
                <span>{FEATURES[k].label[locale]}</span>
                <StatusChip feature={k} />
              </li>
            ))}
          </ul>
        </section>
      </div>

      <section className="flex items-start gap-3 rounded-xl border border-border bg-surface p-4">
        <ShieldCheck className="mt-0.5 size-4 shrink-0 text-success-fg" aria-hidden />
        <div className="flex flex-col gap-2">
          <p className="text-sm font-semibold">{t.honestyTitle}</p>
          <p className="text-xs text-muted-foreground">{t.honestyBody}</p>
          <Disclaimer kind="advisory" />
          <Disclaimer kind="roles" />
        </div>
      </section>
    </ExecutiveLayout>
  );
}
