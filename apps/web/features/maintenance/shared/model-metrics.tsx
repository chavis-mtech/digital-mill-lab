"use client";

import { CircleCheck, CircleX, CircleMinus } from "lucide-react";
import type { Schema } from "@dml/contracts";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatNumber } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import messages from "./ops-shared.i18n";

type ModelInfo = Schema<"ModelInfo">;

/** Measured metrics vs the naive baseline (SPEC §0.6): a model that loses is shown as losing. */
export function ModelMetrics({ model }: { model: ModelInfo }) {
  const t = useT(messages);
  const { locale } = useLocale();
  return (
    <section className="flex flex-col gap-2 rounded-xl border border-border bg-surface p-4" aria-label={t.model.title}>
      <h3 className="text-sm font-semibold">{t.model.title}</h3>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
        <dt className="text-muted-foreground">{t.model.name}</dt>
        <dd className="font-mono">
          {model.name} {model.version}
        </dd>
        <dt className="text-muted-foreground">{t.model.algorithm}</dt>
        <dd lang="en">{model.algorithm}</dd>
        <dt className="text-muted-foreground">{t.model.status}</dt>
        <dd>{model.status}</dd>
        {model.test_window && model.test_window.length > 0 ? (
          <>
            <dt className="text-muted-foreground">{t.model.testWindow}</dt>
            <dd className="font-mono text-2xs">{model.test_window.join(" → ")}</dd>
          </>
        ) : null}
        {model.data_kind ? (
          <>
            <dt className="text-muted-foreground">{t.model.dataKind}</dt>
            <dd>{model.data_kind}</dd>
          </>
        ) : null}
      </dl>
      <div className="relative overflow-x-auto rounded-lg border border-border" tabIndex={0} role="region" aria-label={t.model.title}>
        <table className="tabular w-full border-collapse text-left text-xs">
          <caption className="sr-only">{t.model.title}</caption>
          <thead className="bg-surface-2 text-muted-foreground">
            <tr>
              {[t.model.metric, t.model.modelValue, t.model.baseline, t.model.verdict].map((h) => (
                <th key={h} scope="col" className="border-b border-border px-2.5 py-2 font-semibold whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {model.metrics.map((m) => (
              <tr key={m.name} className="border-b border-border last:border-0">
                <th scope="row" className="px-2.5 py-2 text-left font-medium uppercase">
                  {m.name}
                  <span className="block text-2xs font-normal text-muted-foreground normal-case">{m.better_is === "lower" ? t.model.lowerBetter : m.better_is === "higher" ? t.model.higherBetter : ""}</span>
                </th>
                <td className="px-2.5 py-2 font-semibold">{formatNumber(m.model, locale, { digits: 3 })}</td>
                <td className="px-2.5 py-2">
                  {formatNumber(m.baseline ?? null, locale, { digits: 3 })}
                  {m.baseline_name ? <span className="block font-mono text-2xs text-muted-foreground">{m.baseline_name}</span> : null}
                </td>
                <td className="px-2.5 py-2">
                  {m.beats_baseline === true ? (
                    <Badge tone="success">
                      <CircleCheck aria-hidden /> {t.model.beats}
                    </Badge>
                  ) : m.beats_baseline === false ? (
                    <Badge tone="warning">
                      <CircleX aria-hidden /> {t.model.loses}
                    </Badge>
                  ) : (
                    <Badge tone="neutral">
                      <CircleMinus aria-hidden /> {t.model.unknown}
                    </Badge>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-2xs text-muted-foreground">{t.model.honest}</p>
    </section>
  );
}
