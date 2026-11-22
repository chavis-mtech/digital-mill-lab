"use client";

import { useEffect, useMemo, useState } from "react";
import { Download, FileSpreadsheet, Play, Printer, RotateCcw } from "lucide-react";
import type { Schema } from "@dml/contracts";
import { apiPost } from "@/lib/api/client";
import { useApiMutation, useApiQuery } from "@/lib/api/hooks";
import { useDemo } from "@/lib/demo/context";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatNumber, formatValue } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ExecutiveLayout } from "@/components/layouts/layouts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { toast } from "@/components/ui/toast";
import { ProvenanceBadge } from "@/components/demo/provenance-badge";
import { Disclaimer } from "@/components/demo/disclaimer";
import { FormulaPanel } from "@/features/executive/shared/formulas";
import { ErrorState, LoadingState, QueryState } from "@/components/states/states";
import { ApiText, Section } from "@/features/executive/shared/section";
import { downloadText, readPrintable, reserveWindow, showHtmlIn } from "@/features/executive/shared/download";
import common from "@/messages/common.i18n";
import messages from "./scenarios.i18n";
import { readForm, toFormValues, tornadoGeometry, type FormValues } from "./form";

type RoiInputs = Schema<"RoiInputs">;
type RoiCaseResult = Schema<"RoiCaseResult">;
type Defaults = Schema<"RoiDefaultsResponse">;

const INPUT_KEYS = [
  "daily_ffb_t",
  "operating_days",
  "current_oer_pct",
  "target_oer_pct",
  "cpo_price_thb_per_kg",
  "downtime_h_per_month",
  "processing_capacity_tph",
  "energy_cost_thb_per_year",
  "maintenance_expense_thb_per_year",
  "efficiency_improvement_pct",
  "downtime_reduction_pct",
  "implementation_cost_thb",
  "recurring_cost_thb_per_year",
] as const satisfies readonly (keyof RoiInputs)[];

const ROWS = [
  "additional_cpo_t",
  "gross_value_uplift_thb",
  "cost_avoidance_thb",
  "implementation_cost_thb",
  "annual_recurring_cost_thb",
  "net_benefit_year1_thb",
  "payback_months",
] as const satisfies readonly (keyof RoiCaseResult)[];

const SENS_VARS = [
  "target_oer_pct",
  "cpo_price_thb_per_kg",
  "downtime_reduction_pct",
  "efficiency_improvement_pct",
  "implementation_cost_thb",
  "recurring_cost_thb_per_year",
];

function fieldLabel(fields: unknown, key: string) {
  return (fields as Readonly<Record<string, string>>)[key] ?? key;
}

/** Merge edited numbers over the API defaults into a full RoiInputs (fixed fields keep their default). */
function toInputs(defaults: RoiInputs, body: Record<string, number>, editable: Set<string>): RoiInputs {
  const out = { ...defaults } as Record<string, number>;
  for (const [k, v] of Object.entries(body)) if (editable.has(k)) out[k] = k === "operating_days" ? Math.round(v) : v;
  return out as unknown as RoiInputs;
}

function CasesTable({ cases, provenance }: { cases: RoiCaseResult[]; provenance: Schema<"Provenance"> }) {
  const t = useT(messages);
  const { locale } = useLocale();
  const cell = (c: RoiCaseResult, r: (typeof ROWS)[number]) => {
    if (r === "payback_months") return c.payback_months == null ? <span className="text-muted-foreground" title={t.roi.noPayback}>—</span> : formatNumber(c.payback_months, locale, { digits: 1 });
    const v = c[r];
    return (
      <span className={cn(r === "net_benefit_year1_thb" && v < 0 && "text-critical-fg")}>
        {formatNumber(v, locale, { digits: r === "additional_cpo_t" ? 1 : 0 })}
        {r === "net_benefit_year1_thb" && v < 0 ? <span className="sr-only"> ({t.roi.negative})</span> : null}
      </span>
    );
  };
  return (
    <div className="relative overflow-x-auto" tabIndex={0} role="region" aria-label={t.roi.cases}>
      <table className="w-full min-w-[40rem] text-xs">
        <caption className="sr-only">{t.roi.cases}</caption>
        <thead>
          <tr className="border-b border-border text-left text-muted-foreground">
            <th scope="col" className="py-1.5 pr-2 font-medium">{t.roi.output}</th>
            {cases.map((c) => (
              <th key={c.case} scope="col" className={cn("py-1.5 pr-2 text-right font-medium", c.case === "expected" && "text-foreground")}>
                {t.roi.case[c.case]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROWS.map((r) => (
            <tr key={r} className={cn("border-b border-border/60", r === "net_benefit_year1_thb" && "font-semibold")}>
              <th scope="row" className="py-1.5 pr-2 text-left font-normal">
                {t.roi.row[r]}
              </th>
              {cases.map((c) => (
                <td key={c.case} className={cn("tabular py-1.5 pr-2 text-right", c.case === "expected" && "bg-accent-soft/30")}>
                  {cell(c, r)}
                </td>
              ))}
            </tr>
          ))}
          <tr>
            <th scope="row" className="py-1.5 pr-2 text-left text-2xs font-normal text-muted-foreground">
              {t.roi.multipliers}
            </th>
            {cases.map((c) => (
              <td key={c.case} className="py-1.5 pr-2 text-right font-mono text-2xs text-muted-foreground">
                {Object.entries(c.multipliers)
                  .map(([k, v]) => `${k.replace(/_realisation|_factor/g, "")}×${v}`)
                  .join(" ")}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
      <div className="mt-1 flex items-center gap-2">
        <ProvenanceBadge provenance={provenance} />
      </div>
    </div>
  );
}

function Tornado({ inputs }: { inputs: RoiInputs }) {
  const t = useT(messages);
  const { locale } = useLocale();
  const [swing, setSwing] = useState("20");
  const sens = useApiMutation("/api/v1/roi/sensitivity");
  const { mutate } = sens;
  const key = JSON.stringify(inputs) + swing;
  useEffect(() => {
    const s = Number(swing);
    if (!Number.isFinite(s) || s <= 0 || s > 100) return;
    mutate({ body: { inputs, variables: SENS_VARS, swing_pct: s } });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `key` captures inputs + swing
  }, [key, mutate]);
  const W = 520;
  const LABEL = 210;
  const ROW = 30;
  const d = sens.data;
  const geo = useMemo(() => (d ? tornadoGeometry(d.bars, d.base_net_benefit_thb, W) : null), [d]);
  return (
    <Section
      id="roi-tornado"
      title={t.roi.tornado}
      description={d ? t.roi.tornadoDesc(`${swing}%`, formatValue(d.base_net_benefit_thb, "THB", locale)) : undefined}
      actions={
        <>
          <label className="flex items-center gap-1.5 text-xs">
            {t.roi.swing}
            <Input type="number" min={1} max={100} value={swing} onChange={(e) => setSwing(e.target.value)} className="h-8 w-20" />
          </label>
          {d ? <ProvenanceBadge provenance={d.provenance} /> : null}
        </>
      }
    >
      {sens.isError ? (
        <ErrorState error={sens.error} compact />
      ) : !d || !geo ? (
        <LoadingState lines={4} />
      ) : (
        <>
          <div className="relative overflow-x-auto">
            <svg viewBox={`0 0 ${LABEL + W + 20} ${geo.rows.length * ROW + 30}`} className="h-auto w-full min-w-[34rem]" role="img" aria-label={t.roi.tornado}>
              <line x1={LABEL + geo.baseX} x2={LABEL + geo.baseX} y1={4} y2={geo.rows.length * ROW + 8} stroke="var(--foreground)" strokeWidth={1} />
              {geo.zeroX !== null ? <line x1={LABEL + geo.zeroX} x2={LABEL + geo.zeroX} y1={4} y2={geo.rows.length * ROW + 8} stroke="var(--critical)" strokeDasharray="3 3" /> : null}
              {geo.rows.map((r, i) => (
                <g key={r.bar.variable} transform={`translate(0, ${i * ROW + 8})`}>
                  <text x={LABEL - 8} y={ROW / 2} textAnchor="end" dominantBaseline="middle" fontSize={11} fill="var(--foreground)">
                    {fieldLabel(t.roi.field, r.bar.variable).slice(0, 34)}
                  </text>
                  <rect x={LABEL + r.low.x} y={4} width={Math.max(r.low.w, 1)} height={ROW - 10} fill="var(--chart-2)" opacity={0.85} />
                  <rect x={LABEL + r.high.x} y={4} width={Math.max(r.high.w, 1)} height={ROW - 10} fill="var(--chart-1)" opacity={0.85} />
                </g>
              ))}
              <text x={LABEL + geo.baseX} y={geo.rows.length * ROW + 24} textAnchor="middle" fontSize={10} fill="var(--muted-foreground)">
                {formatNumber(d.base_net_benefit_thb, locale, { compact: true })}
              </text>
            </svg>
          </div>
          <div className="flex flex-wrap gap-3 text-2xs text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <span className="inline-block size-2.5 rounded-sm bg-chart-2" aria-hidden /> {t.roi.low}
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="inline-block size-2.5 rounded-sm bg-chart-1" aria-hidden /> {t.roi.high}
            </span>
          </div>
          <div className="relative overflow-x-auto" tabIndex={0} role="region" aria-label={t.roi.tornado}>
            <table className="w-full min-w-[34rem] text-xs">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th scope="col" className="py-1 pr-2 font-medium">{t.roi.variable}</th>
                  <th scope="col" className="py-1 pr-2 text-right font-medium">{t.roi.low}</th>
                  <th scope="col" className="py-1 pr-2 text-right font-medium">{t.roi.high}</th>
                  <th scope="col" className="py-1 pr-2 text-right font-medium">{t.roi.atLow}</th>
                  <th scope="col" className="py-1 text-right font-medium">{t.roi.atHigh}</th>
                </tr>
              </thead>
              <tbody>
                {geo.rows.map(({ bar }) => (
                  <tr key={bar.variable} className="border-b border-border/60">
                    <th scope="row" className="py-1 pr-2 text-left font-normal">
                      {fieldLabel(t.roi.field, bar.variable)}
                      {bar.note ? (
                        <span className="block text-2xs text-muted-foreground">
                          <ApiText>{bar.note}</ApiText>
                        </span>
                      ) : null}
                    </th>
                    <td className="tabular py-1 pr-2 text-right">{formatNumber(bar.low_value, locale)}</td>
                    <td className="tabular py-1 pr-2 text-right">{formatNumber(bar.high_value, locale)}</td>
                    <td className="tabular py-1 pr-2 text-right">{formatNumber(bar.net_benefit_low_thb, locale, { digits: 0 })}</td>
                    <td className="tabular py-1 text-right">{formatNumber(bar.net_benefit_high_thb, locale, { digits: 0 })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Section>
  );
}

function ExportButtons({ inputs }: { inputs: RoiInputs }) {
  const t = useT(messages);
  const demo = useDemo();
  async function run(kind: "csv" | "markdown" | "print") {
    const win = kind === "print" ? reserveWindow() : null;
    try {
      if (kind === "print") {
        const raw: unknown = await apiPost("/api/v1/roi/export/printable", { body: { inputs, format: "markdown" } }, demo.request);
        const doc = readPrintable(raw);
        if (!doc) throw new Error("printable report missing html");
        if (!showHtmlIn(win, doc.html)) downloadText(doc.filename, doc.html, "html");
      } else {
        const doc = await apiPost("/api/v1/roi/export", { body: { inputs, format: kind } }, demo.request);
        downloadText(doc.filename, doc.content, kind);
      }
      toast.success(t.roi.exportDone);
    } catch (e) {
      win?.close();
      toast.error(t.roi.exportFail, { description: e instanceof Error ? e.message : undefined });
    }
  }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm">
          <Download aria-hidden /> {t.roi.export}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onSelect={() => void run("print")}>
          <Printer aria-hidden /> {t.roi.exportPrint}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => void run("csv")}>
          <FileSpreadsheet aria-hidden /> {t.roi.exportCsv}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => void run("markdown")}>
          <FileSpreadsheet aria-hidden /> {t.roi.exportMd}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function RoiWorkspace({ defaults }: { defaults: Defaults }) {
  const t = useT(messages);
  const tc = useT(common);
  const { locale } = useLocale();
  const editable = useMemo(() => new Set(defaults.assumptions.filter((a) => a.editable !== false).map((a) => a.key)), [defaults]);
  const tagOf = useMemo(() => new Map(defaults.assumptions.map((a) => [a.key, a])), [defaults]);
  const [form, setForm] = useState<FormValues>(() => toFormValues(defaults.inputs as unknown as Record<string, unknown>, INPUT_KEYS));
  const [inputs, setInputs] = useState<RoiInputs>(defaults.inputs);
  const [invalid, setInvalid] = useState<string[]>([]);
  const [formulaCase, setFormulaCase] = useState("expected");
  const calc = useApiMutation("/api/v1/roi/calculate");
  const { mutate } = calc;
  const inputsKey = JSON.stringify(inputs);
  useEffect(() => {
    mutate({ body: inputs });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- inputsKey captures inputs
  }, [inputsKey, mutate]);

  const submit = () => {
    const { body, invalid: bad } = readForm(form, INPUT_KEYS);
    setInvalid(bad);
    if (!bad.length) setInputs(toInputs(defaults.inputs, body, editable));
  };
  const d = calc.data;
  const disclaimer = d?.disclaimer ?? defaults.disclaimer;

  return (
    <>
      <Disclaimer kind="roi" variant="block" />
      <Section id="roi-inputs" title={t.roi.inputs} description={t.roi.inputsDesc} actions={<ExportButtons inputs={inputs} />}>
        <form
          className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          {INPUT_KEYS.map((k) => {
            const a = tagOf.get(k);
            const canEdit = editable.has(k);
            const bad = invalid.includes(k);
            return (
              <label key={k} className="flex flex-col gap-1 text-xs">
                <span className="font-medium">{t.roi.field[k]}</span>
                <Input
                  inputMode="decimal"
                  value={form[k] ?? ""}
                  disabled={!canEdit}
                  aria-invalid={bad}
                  onChange={(e) => setForm((f) => ({ ...f, [k]: e.target.value }))}
                  className={cn(bad && "border-critical")}
                />
                <span className="flex flex-wrap items-center gap-1 text-2xs text-muted-foreground">
                  {a ? <Badge tone="outline">{tc.factTag[a.tag]}</Badge> : null}
                  {a?.source ? <ApiText className="line-clamp-2">{a.source}</ApiText> : null}
                  {bad ? <span className="text-critical-fg">{t.roi.invalid}</span> : null}
                </span>
              </label>
            );
          })}
          <div className="col-span-full flex flex-wrap gap-2">
            <Button type="submit" disabled={calc.isPending}>
              <Play aria-hidden /> {calc.isPending ? t.roi.running : t.roi.calculate}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setForm(toFormValues(defaults.inputs as unknown as Record<string, unknown>, INPUT_KEYS));
                setInvalid([]);
                setInputs(defaults.inputs);
              }}
            >
              <RotateCcw aria-hidden /> {t.roi.reset}
            </Button>
          </div>
        </form>
      </Section>

      <Section id="roi-cases" title={t.roi.cases} data-tour="roi-cases">
        {calc.isError ? (
          <ErrorState error={calc.error} onRetry={() => mutate({ body: inputs })} compact />
        ) : !d ? (
          <LoadingState lines={6} />
        ) : (
          <>
            <CasesTable cases={d.cases} provenance={d.provenance} />
            {d.double_counting_note ? (
              <p className="rounded-md border border-border bg-surface-2 p-2 text-xs">
                <span className="font-semibold">{t.roi.doubleCounting}: </span>
                <ApiText>{d.double_counting_note}</ApiText>
              </p>
            ) : null}
            <div className="flex flex-col gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-sm font-semibold">{t.roi.formulas}</h3>
                <Select value={formulaCase} onValueChange={setFormulaCase}>
                  <SelectTrigger size="sm" className="w-48" aria-label={t.roi.chooseCase}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {d.cases.map((c) => (
                      <SelectItem key={c.case} value={c.case}>
                        {t.roi.case[c.case]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <FormulaPanel formulas={d.formulas.filter((f) => f.key.startsWith(`${formulaCase}.`))} />
            </div>
          </>
        )}
        <p className="rounded-md bg-surface-2 p-2 text-xs" role="note">
          <span className="font-semibold">{t.roi.apiDisclaimer}: </span>
          {locale === "th" && disclaimer.text_th ? disclaimer.text_th : <ApiText>{disclaimer.text_en}</ApiText>}
        </p>
      </Section>

      <Tornado inputs={inputs} />
      <Disclaimer kind="roi" variant="block" />
    </>
  );
}

/** ROI & value simulator (DML-085..090) over /roi/defaults, /roi/calculate, /roi/sensitivity, /roi/export*. */
export function RoiSimulator() {
  const q = useApiQuery("/api/v1/roi/defaults");
  return (
    <ExecutiveLayout route="/demo/business-impact">
      <QueryState query={q}>{(d) => <RoiWorkspace key={JSON.stringify(d.inputs)} defaults={d} />}</QueryState>
    </ExecutiveLayout>
  );
}
