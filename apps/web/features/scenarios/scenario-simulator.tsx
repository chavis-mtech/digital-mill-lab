"use client";

import { useEffect, useState } from "react";
import { Calculator, Play, RotateCcw, TriangleAlert } from "lucide-react";
import type { Schema } from "@dml/contracts";
import { useApiMutation, useApiQuery } from "@/lib/api/hooks";
import { useDemo } from "@/lib/demo/context";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatDate, formatNumber, formatSigned, formatValue } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ExecutiveLayout } from "@/components/layouts/layouts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ProvenanceBadge } from "@/components/demo/provenance-badge";
import { Disclaimer } from "@/components/demo/disclaimer";
import { EvidencePanel } from "@/components/data/evidence-panel";
import { FormulaPanel } from "@/features/executive/shared/formulas";
import { ErrorState, LoadingState, QueryState } from "@/components/states/states";
import { ApiText, Section } from "@/features/executive/shared/section";
import { useScenarioLabel } from "@/features/executive/use-labels";
import messages from "./scenarios.i18n";
import { readForm, toFormValues, type FormValues } from "./form";

const FIELDS = [
  "ffb_intake_t_per_day",
  "oer_pct",
  "availability_pct",
  "processing_hours_per_day",
  "energy_cost_thb_per_kwh",
  "oil_loss_pct",
  "cpo_price_thb_per_kg",
] as const;

type WhatIf = Schema<"ProductionWhatIfResponse">;
type Kpi = Schema<"KpiValue">;

function ResultsTable({ data }: { data: WhatIf }) {
  const t = useT(messages);
  const { locale } = useLocale();
  const find = (list: Kpi[], key: string) => list.find((k) => k.key === key);
  return (
    <div className="relative overflow-x-auto" tabIndex={0} role="region" aria-label={t.calc.results}>
      <table className="w-full min-w-[34rem] text-xs">
        <caption className="sr-only">{t.calc.results}</caption>
        <thead>
          <tr className="border-b border-border text-left text-muted-foreground">
            <th scope="col" className="py-1.5 pr-2 font-medium">{t.calc.metric}</th>
            <th scope="col" className="py-1.5 pr-2 text-right font-medium">{t.calc.baseline}</th>
            <th scope="col" className="py-1.5 pr-2 text-right font-medium">{t.calc.scenario}</th>
            <th scope="col" className="py-1.5 text-right font-medium">{t.calc.delta}</th>
          </tr>
        </thead>
        <tbody>
          {data.baseline.map((b) => {
            const s = find(data.scenario, b.key);
            const d = find(data.delta, b.key);
            const changed = d?.value != null && Math.abs(d.value) >= 0.005;
            return (
              <tr key={b.key} className={cn("border-b border-border/60", changed && "bg-accent-soft/30")}>
                <th scope="row" className="py-1.5 pr-2 text-left font-normal">
                  <ApiText>{b.label}</ApiText>
                </th>
                <td className="tabular py-1.5 pr-2 text-right">
                  <span className="inline-flex items-center gap-1">
                    {formatValue(b.value, b.unit, locale)} <ProvenanceBadge provenance={b.provenance} compact />
                  </span>
                </td>
                <td className="tabular py-1.5 pr-2 text-right">
                  {s ? (
                    <span className="inline-flex items-center gap-1">
                      {formatValue(s.value, s.unit, locale)} <ProvenanceBadge provenance={s.provenance} compact />
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
                <td className={cn("tabular py-1.5 text-right", changed && "font-semibold")}>
                  {d?.value != null ? (changed ? `${formatSigned(d.value, locale, Math.abs(d.value) >= 100 ? 0 : 2)} ${d.unit}` : `0 ${d.unit}`) : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** AI-B03 / DML-050: production what-if calculator over POST /scenarios/production/calculate. */
function ProductionCalculator() {
  const t = useT(messages);
  const { locale } = useLocale();
  const demo = useDemo();
  const ctxKey = `${demo.scenarioId ?? ""}|${demo.asOf ?? ""}`;
  const calc = useApiMutation("/api/v1/scenarios/production/calculate");
  const [baseline, setBaseline] = useState<Record<string, unknown> | null>(null);
  const [form, setForm] = useState<FormValues>({});
  const [days, setDays] = useState("30");
  const [invalid, setInvalid] = useState<string[]>([]);
  const { mutate } = calc;

  // First calculation with no overrides returns the baseline inputs used to prefill the form; re-run when the
  // demo clock / scenario changes so the baseline always matches the selected moment.
  useEffect(() => {
    mutate(
      { body: { days: 30 } },
      {
        onSuccess: (d) => {
          setBaseline(d.baseline_inputs ?? null);
          setForm(toFormValues(d.baseline_inputs, FIELDS));
          setDays("30");
          setInvalid([]);
        },
      },
    );
  }, [ctxKey, mutate]);

  const run = () => {
    const { body, invalid: bad } = readForm(form, FIELDS);
    const n = Number(days);
    setInvalid(bad);
    if (bad.length || !Number.isFinite(n) || n < 1) return;
    calc.mutate({ body: { ...body, days: Math.round(n) } });
  };

  const data = calc.data;
  return (
    <Section id="scenario-calc" title={t.calc.title} description={t.calc.desc}>
      <form
        className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4"
        onSubmit={(e) => {
          e.preventDefault();
          run();
        }}
      >
        {FIELDS.map((k) => {
          const base = baseline?.[k];
          const bad = invalid.includes(k);
          return (
            <label key={k} className="flex flex-col gap-1 text-xs">
              <span className="font-medium">{t.calc.field[k]}</span>
              <Input inputMode="decimal" value={form[k] ?? ""} aria-invalid={bad} onChange={(e) => setForm((f) => ({ ...f, [k]: e.target.value }))} className={cn(bad && "border-critical")} />
              <span className="text-2xs text-muted-foreground">
                {typeof base === "number" ? t.calc.baselineHint(formatNumber(base, locale)) : " "}
              </span>
            </label>
          );
        })}
        <label className="flex flex-col gap-1 text-xs">
          <span className="font-medium">{t.calc.days}</span>
          <Input type="number" min={1} max={365} value={days} onChange={(e) => setDays(e.target.value)} />
        </label>
        <div className="col-span-full flex flex-wrap items-center gap-2">
          <Button type="submit" disabled={calc.isPending}>
            <Play aria-hidden /> {calc.isPending ? t.calc.running : t.calc.run}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setForm(toFormValues(baseline, FIELDS));
              setDays("30");
              setInvalid([]);
            }}
          >
            <RotateCcw aria-hidden /> {t.calc.reset}
          </Button>
          {data ? <ProvenanceBadge provenance={data.provenance} /> : null}
          {data?.horizon_days ? <span className="text-2xs text-muted-foreground">{t.calc.horizon(data.horizon_days)}</span> : null}
        </div>
      </form>

      <div data-tour="scenario-impact" className="flex flex-col gap-4" aria-live="polite">
        {calc.isError ? (
          <ErrorState error={calc.error} onRetry={run} compact />
        ) : !data ? (
          <LoadingState lines={4} />
        ) : (
          <>
            <h3 className="text-sm font-semibold">{t.calc.results}</h3>
            {data.warnings?.length ? (
              <ul className="flex flex-col gap-1 rounded-md border border-warning/50 bg-warning-soft/50 p-2 text-xs" aria-label={t.calc.warnings}>
                {data.warnings.map((w) => (
                  <li key={w} className="flex items-start gap-1.5">
                    <TriangleAlert className="mt-0.5 size-3.5 shrink-0 text-warning-fg" aria-hidden />
                    <ApiText>{w}</ApiText>
                  </li>
                ))}
              </ul>
            ) : null}
            <ResultsTable data={data} />
            <Disclaimer kind="roi" />
            {data.calculation_example ? (
              <div className="flex flex-wrap items-center gap-2 rounded-lg border border-dashed border-border-strong p-3 text-sm">
                <Calculator className="size-4 text-muted-foreground" aria-hidden />
                <Badge tone="info">{t.calc.example}</Badge>
                <span className="font-medium">
                  <ApiText>{data.calculation_example}</ApiText>
                </span>
                <span className="text-2xs text-muted-foreground">{t.calc.exampleNote}</span>
              </div>
            ) : null}
            <div className="grid grid-cols-1 gap-4 2xl:grid-cols-2">
              <FormulaPanel formulas={data.formulas} title={t.calc.formulas} />
              <EvidencePanel assumptions={data.assumptions} title={t.calc.assumptions} />
            </div>
          </>
        )}
      </div>
    </Section>
  );
}

/** Deterministic episodes with MEASURED effects (GET /scenarios); activating one sets the shared demo context. */
function ScenarioCatalog() {
  const t = useT(messages);
  const { locale } = useLocale();
  const label = useScenarioLabel();
  const { scenarioId, setScenario } = useDemo();
  const q = useApiQuery("/api/v1/scenarios");
  return (
    <Section id="scenario-catalog" title={t.catalog.title} description={t.catalog.desc}>
      <QueryState query={q} compact isEmpty={(d) => d.items.length === 0}>
        {(d) => (
          <ul className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {d.items.map((s) => {
              const active = s.code === scenarioId;
              return (
                <li key={s.code} className={cn("flex flex-col gap-2 rounded-lg border p-3", active ? "border-accent bg-accent-soft/30" : "border-border")}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-semibold">{locale === "th" ? s.name_th : s.name_en || label(s.code)}</p>
                    {active ? (
                      <Badge tone="accent">{t.catalog.active}</Badge>
                    ) : (
                      <Button size="xs" variant="outline" onClick={() => setScenario(s.code)}>
                        {t.catalog.activate}
                      </Button>
                    )}
                  </div>
                  <p className="text-2xs text-muted-foreground">
                    {t.catalog.focus}: {formatDate(s.focus_ts, locale, "datetime")}
                    {s.primary_equipment_code ? ` · ${s.primary_equipment_code}` : ""}
                  </p>
                  {s.highlights_available ? (
                    <ul className="flex flex-col gap-1 text-xs">
                      {s.expected_effects.slice(0, 4).map((e, i) => (
                        <li key={`${e.metric}-${i}`} className="flex flex-col">
                          <ApiText>{e.description}</ApiText>
                          {e.significance ? (
                            <span className="text-2xs text-muted-foreground">
                              <ApiText>{e.significance}</ApiText>
                            </span>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-xs text-muted-foreground">{s.highlights_note ? <ApiText>{s.highlights_note}</ApiText> : t.catalog.notYet}</p>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </QueryState>
    </Section>
  );
}

export function ScenarioSimulator() {
  return (
    <ExecutiveLayout route="/demo/scenarios">
      <ProductionCalculator />
      <ScenarioCatalog />
    </ExecutiveLayout>
  );
}
