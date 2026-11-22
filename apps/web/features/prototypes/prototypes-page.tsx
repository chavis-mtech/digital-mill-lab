"use client";

import Link from "next/link";
import { FlaskConical } from "lucide-react";
import { OperationsLayout } from "@/components/layouts/layouts";
import { StatusChip } from "@/components/demo/status-chip";
import { Disclaimer } from "@/components/demo/disclaimer";
import { QueryState } from "@/components/states/states";
import { Badge } from "@/components/ui/badge";
import { useApiQuery } from "@/lib/api/hooks";
import { useT } from "@/lib/i18n/client";
import type { FeatureKey } from "@/content/status";
import { ApiText } from "@/features/maintenance/shared/ops-ui";
import messages from "./prototypes.i18n";

type CardKey = "cv" | "plantation" | "petroleum" | "port" | "platform";

const CARDS: { key: CardKey; feature: FeatureKey; generic?: boolean; link?: { href: string; textKey: "related" } }[] = [
  { key: "cv", feature: "cv_grading" },
  { key: "plantation", feature: "smart_plantation", link: { href: "/demo/traceability", textKey: "related" } },
  { key: "petroleum", feature: "petroleum_inventory", generic: true },
  { key: "port", feature: "port_scheduling", generic: true, link: { href: "/demo/logistics", textKey: "related" } },
  { key: "platform", feature: "group_data_platform", link: { href: "/docs/integration", textKey: "related" } },
];

export function PrototypesPage() {
  const t = useT(messages);
  return (
    <OperationsLayout
      title={t.title}
      description={t.description}
      eyebrow={t.banner}
      actions={<StatusChip status="prototype" size="md" />}
    >
      <div role="note" className="flex items-start gap-2 rounded-xl border border-maintenance/40 bg-maintenance-soft/40 p-3 text-xs" data-tour="prototypes-banner">
        <FlaskConical className="mt-0.5 size-4 shrink-0 text-maintenance-fg" aria-hidden />
        <p>
          <b className="text-foreground">{t.banner}.</b> {t.bannerBody}
        </p>
      </div>
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        {CARDS.map((c) => {
          const card = t.cards[c.key];
          return (
            <article key={c.key} id={c.key} className="flex min-w-0 scroll-mt-28 flex-col gap-3 rounded-xl border border-border bg-surface p-5 shadow-xs">
              <header className="flex flex-wrap items-start justify-between gap-2">
                <h2 className="text-base font-semibold">{card.title}</h2>
                <div className="flex flex-wrap items-center gap-1.5">
                  <StatusChip feature={c.feature} />
                  {c.generic ? <Badge tone="outline">{t.generic}</Badge> : null}
                </div>
              </header>
              <p className="rounded-md border border-dashed border-border-strong bg-surface-2/60 px-2.5 py-1.5 text-xs font-medium text-muted-foreground">{t.noOutput}</p>
              <dl className="flex flex-col gap-2.5 text-sm">
                {(["problem", "concept", "data", "validation"] as const).map((k) => (
                  <div key={k}>
                    <dt className="text-2xs font-semibold text-muted-foreground uppercase">{t[k]}</dt>
                    <dd className="mt-0.5 leading-relaxed">{card[k as keyof typeof card] as string}</dd>
                  </div>
                ))}
                <div>
                  <dt className="text-2xs font-semibold text-warning-fg uppercase">{t.notBuilt}</dt>
                  <dd className="mt-0.5 leading-relaxed">{card.notBuilt}</dd>
                </div>
              </dl>
              {c.key === "cv" ? <CvProtocol /> : null}
              {c.link ? (
                <p className="text-xs">
                  {t.related}:{" "}
                  <Link href={c.link.href} className="text-accent-text underline underline-offset-2 hover:no-underline">
                    {(card as { related: string }).related}
                  </Link>
                </p>
              ) : null}
            </article>
          );
        })}
      </div>
      <Disclaimer kind="synthetic" />
    </OperationsLayout>
  );
}

/** Live research protocol from GET /cv/protocol (no model output, no accuracy). */
function CvProtocol() {
  const t = useT(messages);
  const c = t.cards.cv;
  const q = useApiQuery("/api/v1/cv/protocol", undefined, { withClock: false });
  return (
    <section className="flex flex-col gap-2 rounded-lg border border-border p-3" aria-label={c.protocolTitle}>
      <h3 className="text-sm font-semibold">{c.protocolTitle}</h3>
      <p className="text-2xs text-muted-foreground">{c.protocolNote}</p>
      <QueryState query={q} compact>
        {(d) => (
          <div className="flex flex-col gap-3 text-xs">
            <ListBlock title={c.datasetReq} items={d.dataset_requirements} />
            <TextBlock title={c.camera} text={d.camera_position} />
            <TextBlock title={c.lighting} text={d.lighting} />
            <ListBlock title={c.labelling} items={d.labelling_protocol} />
            <div>
              <p className="text-2xs font-semibold text-muted-foreground uppercase">{c.classes}</p>
              <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
                {Object.entries(d.class_definitions).map(([k, v]) => (
                  <div key={k} className="contents">
                    <dt className="font-mono">{k}</dt>
                    <dd lang="en">{v}</dd>
                  </div>
                ))}
              </dl>
            </div>
            <ListBlock title={c.evaluation} items={d.evaluation_plan} />
            <ListBlock title={c.pilot} items={d.pilot_validation_plan} />
            <p className="text-2xs text-muted-foreground">{c.uploadNote}</p>
          </div>
        )}
      </QueryState>
    </section>
  );
}

function ListBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <p className="text-2xs font-semibold text-muted-foreground uppercase">{title}</p>
      <ul className="mt-1 list-disc pl-5">
        {items.map((i) => (
          <li key={i} lang="en">
            {i}
          </li>
        ))}
      </ul>
    </div>
  );
}

function TextBlock({ title, text }: { title: string; text: string }) {
  return (
    <div>
      <p className="text-2xs font-semibold text-muted-foreground uppercase">{title}</p>
      <p className="mt-1">
        <ApiText>{text}</ApiText>
      </p>
    </div>
  );
}
