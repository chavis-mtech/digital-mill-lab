"use client";

/**
 * Chart kit (ECharts wrappers). Every chart:
 *  - takes contract-shaped data (`Series`, `BandSeries`, …) so API payloads go straight in,
 *  - colours series by ENTITY order (chart-1…6, never cycled, never by rank),
 *  - encodes provenance with line pattern (solid actual · dashed forecast · dotted what-if),
 *  - renders through <ChartFrame>: keyboard legend + data-table fallback + loading/error/empty states,
 *  - uses one y-axis only (no dual axes — split into two charts instead).
 */
import { useCallback, useMemo, useState } from "react";
import type { Schema } from "@dml/contracts";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatDate, formatNumber, formatValue } from "@/lib/format";
import { EChart, type BuildOption } from "./echart";
import { ChartFrame, type ChartStateProps, type LegendItem, type LinePattern } from "./chart-frame";
import type { ChartTokens } from "./tokens";
import common from "@/messages/common.i18n";

export type Series = Schema<"Series">;
export type BandSeries = Schema<"BandSeries">;
export type SeriesPoint = Schema<"SeriesPoint">;
type Kind = Schema<"ProvenanceKind">;

const PATTERN: Record<Kind, LinePattern> = { synthetic_actual: "solid", forecast: "dashed", what_if: "dotted" };
const ECHARTS_LINE: Record<LinePattern, "solid" | "dashed" | "dotted"> = {
  solid: "solid",
  dashed: "dashed",
  dotted: "dotted",
  area: "solid",
  bar: "solid",
  marker: "solid",
};

function esc(s: string) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] as string);
}

function baseGrid(t: ChartTokens) {
  return {
    grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
    tooltip: {
      backgroundColor: t.surface,
      borderColor: t.border,
      borderWidth: 1,
      padding: [8, 10],
      textStyle: { color: t.text, fontSize: 12, fontFamily: t.fontFamily },
      extraCssText: "box-shadow: 0 8px 24px -8px rgba(0,0,0,.25); border-radius: 8px;",
    },
  };
}

function valueAxis(t: ChartTokens, unit: string | undefined, locale: "th" | "en", extra: Record<string, unknown> = {}) {
  return {
    type: "value",
    scale: true,
    name: unit,
    nameTextStyle: { color: t.muted, fontSize: 11, align: "left" },
    axisLabel: { color: t.axis, fontSize: 11, formatter: (v: number) => formatNumber(v, locale, { compact: Math.abs(v) >= 10000 }) },
    splitLine: { lineStyle: { color: t.grid } },
    axisLine: { show: false },
    axisTick: { show: false },
    ...extra,
  };
}

function useHidden() {
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const toggle = useCallback(
    (key: string) =>
      setHidden((h) => {
        const n = new Set(h);
        if (n.has(key)) n.delete(key);
        else n.add(key);
        return n;
      }),
    [],
  );
  return [hidden, toggle] as const;
}

// ─────────────────────────────────────────────────────────────────────────────
// TimeSeriesChart / TrendChart
// ─────────────────────────────────────────────────────────────────────────────

export type AnomalyMarker = { t: string; v?: number | null; label: string; severity?: Schema<"Severity"> };
export type Threshold = { value: number; label: string; tone?: "warning" | "critical" | "neutral" };

export type TimeSeriesChartProps = ChartStateProps & {
  title: string;
  description?: string;
  series: Series[] | undefined;
  /** Anomaly markers (diamonds) — e.g. from AnomalyOut.detected_at. */
  anomalies?: AnomalyMarker[];
  /** Shaded normal band (NormalRange low/high). */
  normalRange?: { low?: number | null; high?: number | null; basis?: string } | null;
  thresholds?: Threshold[];
  height?: number;
  /** Format axis/tooltip time; default shows date+time for hourly data, date for daily. */
  timeStyle?: "datetime" | "date" | "short";
  summary?: string;
  actions?: React.ReactNode;
  className?: string;
};

export function TimeSeriesChart({
  title,
  description,
  series,
  anomalies = [],
  normalRange,
  thresholds = [],
  height = 260,
  timeStyle = "datetime",
  summary,
  actions,
  className,
  ...state
}: TimeSeriesChartProps) {
  const { locale } = useLocale();
  const t = useT(common);
  const [hidden, toggle] = useHidden();
  const list = useMemo(() => series ?? [], [series]);
  const unit = list[0]?.unit;

  const build = useCallback<BuildOption>(
    (tk) => {
      const visible = list.map((s, i) => ({ s, i })).filter(({ s }) => !hidden.has(s.key));
      const first = visible[0]?.s;
      const lines = visible.map(({ s, i }, idx) => {
        const color = tk.categorical[i % 6];
        return {
          type: "line",
          name: s.label,
          id: s.key,
          showSymbol: false,
          symbolSize: 6,
          connectNulls: false,
          lineStyle: { width: 2, type: ECHARTS_LINE[PATTERN[s.provenance.kind]], color },
          itemStyle: { color },
          emphasis: { focus: "series" },
          data: s.points.map((p) => [p.t, p.v]),
          ...(idx === 0 && normalRange && (normalRange.low != null || normalRange.high != null)
            ? {
                markArea: {
                  silent: true,
                  itemStyle: { color: tk.normalBand },
                  data: [[{ yAxis: normalRange.low ?? "min" }, { yAxis: normalRange.high ?? "max" }]],
                },
              }
            : {}),
          ...(idx === 0 && thresholds.length
            ? {
                markLine: {
                  silent: true,
                  symbol: "none",
                  label: { color: tk.muted, fontSize: 10, formatter: "{b}", position: "insideEndTop" },
                  data: thresholds.map((th) => ({
                    name: th.label,
                    yAxis: th.value,
                    lineStyle: { type: "dashed", width: 1, color: th.tone === "critical" ? tk.critical : th.tone === "warning" ? tk.warning : tk.axis },
                  })),
                },
              }
            : {}),
        };
      });
      const anomalySeries =
        anomalies.length && !hidden.has("__anomaly")
          ? [
              {
                type: "scatter",
                name: t.chart.anomaly,
                id: "__anomaly",
                symbol: "diamond",
                symbolSize: 12,
                z: 5,
                itemStyle: { color: tk.critical, borderColor: tk.surface, borderWidth: 2 },
                data: anomalies.map((a) => {
                  let v = a.v;
                  if (v == null && first) {
                    const target = Date.parse(a.t);
                    let best: SeriesPoint | undefined;
                    for (const p of first.points) if (!best || Math.abs(Date.parse(p.t) - target) < Math.abs(Date.parse(best.t) - target)) best = p;
                    v = best?.v ?? null;
                  }
                  return { value: [a.t, v], name: a.label };
                }),
              },
            ]
          : [];

      return {
        ...baseGrid(tk),
        tooltip: {
          ...baseGrid(tk).tooltip,
          trigger: "axis",
          axisPointer: { type: "line", lineStyle: { color: tk.axis, type: "dashed" } },
          formatter: (params: Array<{ seriesName: string; value: [string, number | null]; color: string; seriesId: string; name: string }>) => {
            if (!params.length) return "";
            const head = `<div style="font-weight:600;margin-bottom:4px">${esc(formatDate(params[0]!.value[0], locale, timeStyle))}</div>`;
            const rows = params
              .map((p) => {
                const label = p.seriesId === "__anomaly" ? `${t.chart.anomaly}: ${p.name}` : p.seriesName;
                const val = p.seriesId === "__anomaly" ? "" : esc(formatValue(p.value[1], unit, locale));
                return `<div style="display:flex;gap:12px;justify-content:space-between;align-items:center"><span style="display:inline-flex;gap:6px;align-items:center"><span style="width:8px;height:8px;border-radius:2px;background:${p.color}"></span>${esc(label)}</span><b style="font-variant-numeric:tabular-nums">${val}</b></div>`;
              })
              .join("");
            return head + rows;
          },
        },
        xAxis: {
          type: "time",
          axisLabel: { color: tk.axis, fontSize: 11, hideOverlap: true, formatter: (v: number) => formatDate(new Date(v), locale, timeStyle === "datetime" ? "short" : timeStyle) },
          axisLine: { lineStyle: { color: tk.grid } },
          axisTick: { show: false },
          splitLine: { show: false },
        },
        yAxis: valueAxis(tk, unit, locale),
        series: [...lines, ...anomalySeries],
      };
    },
    [list, hidden, anomalies, normalRange, thresholds, locale, unit, timeStyle, t],
  );

  const legend: LegendItem[] = [
    ...list.map((s, i) => ({
      key: s.key,
      label: s.label,
      color: `var(--chart-${(i % 6) + 1})`,
      pattern: PATTERN[s.provenance.kind],
      hidden: hidden.has(s.key),
    })),
    ...(anomalies.length ? [{ key: "__anomaly", label: t.chart.anomaly, color: "var(--critical)", pattern: "marker" as const, hidden: hidden.has("__anomaly") }] : []),
    ...(normalRange && (normalRange.low != null || normalRange.high != null)
      ? [{ key: "__normal", label: t.chart.normalRange, color: "var(--success)", pattern: "area" as const, toggleable: false }]
      : []),
  ];

  // Table: union of timestamps × series.
  const table = useMemo(() => {
    const times = Array.from(new Set(list.flatMap((s) => s.points.map((p) => p.t)))).sort();
    const maps = list.map((s) => new Map(s.points.map((p) => [p.t, p.v])));
    return {
      caption: title,
      columns: [t.chart.time, ...list.map((s) => `${s.label}${s.unit ? ` (${s.unit})` : ""}`)],
      rows: times.map((tm) => [formatDate(tm, locale, timeStyle), ...maps.map((m) => formatNumber(m.get(tm) ?? null, locale))]),
    };
  }, [list, locale, timeStyle, title, t]);

  return (
    <ChartFrame
      title={title}
      description={description}
      summary={summary}
      legend={list.length > 1 || anomalies.length || normalRange ? legend : undefined}
      onToggle={toggle}
      table={table}
      actions={actions}
      height={height}
      className={className}
      empty={state.empty ?? (!state.loading && !state.error && list.every((s) => s.points.length === 0))}
      {...state}
    >
      <EChart build={build} height={height} />
    </ChartFrame>
  );
}

/** Alias with the same API — "trend" reads better in executive views. */
export const TrendChart = TimeSeriesChart;

// ─────────────────────────────────────────────────────────────────────────────
// AreaBandChart — forecast with uncertainty band (+ optional actuals)
// ─────────────────────────────────────────────────────────────────────────────

export function AreaBandChart({
  title,
  description,
  band,
  actual,
  baseline,
  height = 260,
  summary,
  actions,
  className,
  ...state
}: ChartStateProps & {
  title: string;
  description?: string;
  /** Forecast median + lower/upper (contract `BandSeries`). */
  band: BandSeries | undefined;
  /** Observed synthetic actuals for comparison. */
  actual?: Series;
  /** Naive baseline forecast (required next to every model forecast — SPEC §9). */
  baseline?: Series;
  height?: number;
  summary?: string;
  actions?: React.ReactNode;
  className?: string;
}) {
  const { locale } = useLocale();
  const t = useT(common);
  const [hidden, toggle] = useHidden();
  const unit = band?.unit ?? actual?.unit;

  const build = useCallback<BuildOption>(
    (tk) => {
      const pts = band?.points ?? [];
      const out: Record<string, unknown>[] = [];
      if (!hidden.has("__band")) {
        out.push(
          { type: "line", id: "__lower", stack: "band", symbol: "none", lineStyle: { opacity: 0 }, silent: true, data: pts.map((p) => [p.t, p.lower ?? null]) },
          {
            type: "line",
            id: "__width",
            stack: "band",
            symbol: "none",
            lineStyle: { opacity: 0 },
            areaStyle: { color: tk.band },
            silent: true,
            data: pts.map((p) => [p.t, p.lower != null && p.upper != null ? p.upper - p.lower : null]),
          },
        );
      }
      if (actual && !hidden.has(actual.key))
        out.push({ type: "line", id: actual.key, name: actual.label, showSymbol: false, lineStyle: { width: 2, color: tk.categorical[0] }, itemStyle: { color: tk.categorical[0] }, data: actual.points.map((p) => [p.t, p.v]) });
      if (baseline && !hidden.has(baseline.key))
        out.push({ type: "line", id: baseline.key, name: baseline.label, showSymbol: false, lineStyle: { width: 1.5, type: "dotted", color: tk.categorical[6] }, itemStyle: { color: tk.categorical[6] }, data: baseline.points.map((p) => [p.t, p.v]) });
      if (band && !hidden.has(band.key))
        out.push({ type: "line", id: band.key, name: band.label, showSymbol: false, lineStyle: { width: 2, type: "dashed", color: tk.forecast }, itemStyle: { color: tk.forecast }, data: pts.map((p) => [p.t, p.v]) });

      const bandByT = new Map(pts.map((p) => [p.t, p]));
      return {
        ...baseGrid(tk),
        tooltip: {
          ...baseGrid(tk).tooltip,
          trigger: "axis",
          axisPointer: { type: "line", lineStyle: { color: tk.axis, type: "dashed" } },
          formatter: (params: Array<{ seriesId: string; seriesName: string; value: [string, number | null]; color: string }>) => {
            const visible = params.filter((p) => !p.seriesId.startsWith("__"));
            const tm = params[0]?.value[0];
            if (!tm) return "";
            const b = bandByT.get(tm);
            let html = `<div style="font-weight:600;margin-bottom:4px">${esc(formatDate(tm, locale, "datetime"))}</div>`;
            for (const p of visible)
              html += `<div style="display:flex;gap:12px;justify-content:space-between"><span><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${p.color};margin-right:6px"></span>${esc(p.seriesName)}</span><b style="font-variant-numeric:tabular-nums">${esc(formatValue(p.value[1], unit, locale))}</b></div>`;
            if (b && b.lower != null && b.upper != null && !hidden.has("__band"))
              html += `<div style="color:${tk.muted};margin-top:2px">${esc(t.chart.band)}: ${esc(formatNumber(b.lower, locale))} – ${esc(formatValue(b.upper, unit, locale))}</div>`;
            return html;
          },
        },
        xAxis: {
          type: "time",
          axisLabel: { color: tk.axis, fontSize: 11, hideOverlap: true, formatter: (v: number) => formatDate(new Date(v), locale, "short") },
          axisLine: { lineStyle: { color: tk.grid } },
          axisTick: { show: false },
        },
        yAxis: valueAxis(tk, unit, locale),
        series: out,
      };
    },
    [band, actual, baseline, hidden, locale, unit, t],
  );

  const legend: LegendItem[] = [
    ...(actual ? [{ key: actual.key, label: actual.label, color: "var(--chart-1)", pattern: "solid" as const, hidden: hidden.has(actual.key) }] : []),
    ...(band ? [{ key: band.key, label: band.label, color: "var(--prov-forecast)", pattern: "dashed" as const, hidden: hidden.has(band.key) }] : []),
    ...(band ? [{ key: "__band", label: band.interval ? `${t.chart.band} (${band.interval})` : t.chart.band, color: "var(--prov-forecast)", pattern: "area" as const, hidden: hidden.has("__band") }] : []),
    ...(baseline ? [{ key: baseline.key, label: baseline.label, color: "var(--chart-7)", pattern: "dotted" as const, hidden: hidden.has(baseline.key) }] : []),
  ];

  const table = useMemo(() => {
    const pts = band?.points ?? [];
    const act = new Map(actual?.points.map((p) => [p.t, p.v]) ?? []);
    const base = new Map(baseline?.points.map((p) => [p.t, p.v]) ?? []);
    const times = Array.from(new Set([...pts.map((p) => p.t), ...act.keys(), ...base.keys()])).sort();
    const bandBy = new Map(pts.map((p) => [p.t, p]));
    return {
      caption: title,
      columns: [t.chart.time, ...(actual ? [actual.label] : []), band?.label ?? "", t.chart.lower, t.chart.upper, ...(baseline ? [baseline.label] : [])],
      rows: times.map((tm) => {
        const b = bandBy.get(tm);
        return [
          formatDate(tm, locale, "datetime"),
          ...(actual ? [formatNumber(act.get(tm) ?? null, locale)] : []),
          formatNumber(b?.v ?? null, locale),
          formatNumber(b?.lower ?? null, locale),
          formatNumber(b?.upper ?? null, locale),
          ...(baseline ? [formatNumber(base.get(tm) ?? null, locale)] : []),
        ];
      }),
    };
  }, [band, actual, baseline, locale, title, t]);

  return (
    <ChartFrame
      title={title}
      description={description}
      summary={summary}
      legend={legend}
      onToggle={toggle}
      table={table}
      actions={actions}
      height={height}
      className={className}
      empty={state.empty ?? (!state.loading && !state.error && !band?.points.length)}
      {...state}
    >
      <EChart build={build} height={height} />
    </ChartFrame>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// BarChart
// ─────────────────────────────────────────────────────────────────────────────

export type BarSeries = { key: string; label: string; values: (number | null)[]; kind?: Kind };

export function BarChart({
  title,
  description,
  categories,
  series,
  unit,
  horizontal = false,
  stacked = false,
  height = 260,
  summary,
  actions,
  className,
  ...state
}: ChartStateProps & {
  title: string;
  description?: string;
  categories: string[];
  series: BarSeries[];
  unit?: string;
  horizontal?: boolean;
  stacked?: boolean;
  height?: number;
  summary?: string;
  actions?: React.ReactNode;
  className?: string;
}) {
  const { locale } = useLocale();
  const t = useT(common);
  const [hidden, toggle] = useHidden();

  const build = useCallback<BuildOption>(
    (tk) => {
      const catAxis = {
        type: "category",
        data: categories,
        axisLabel: { color: tk.axis, fontSize: 11, hideOverlap: true, width: horizontal ? 120 : undefined, overflow: "truncate" },
        axisLine: { lineStyle: { color: tk.grid } },
        axisTick: { show: false },
      };
      const valAxis = valueAxis(tk, unit, locale, { scale: false });
      const visible = series.map((s, i) => ({ s, i })).filter(({ s }) => !hidden.has(s.key));
      return {
        ...baseGrid(tk),
        tooltip: {
          ...baseGrid(tk).tooltip,
          trigger: "axis",
          axisPointer: { type: "shadow", shadowStyle: { color: tk.grid, opacity: 0.5 } },
          valueFormatter: (v: number | null) => formatValue(v, unit, locale),
        },
        xAxis: horizontal ? valAxis : catAxis,
        yAxis: horizontal ? { ...catAxis, inverse: true } : valAxis,
        series: visible.map(({ s, i }, idx) => ({
          type: "bar",
          name: s.label,
          id: s.key,
          stack: stacked ? "total" : undefined,
          barMaxWidth: 28,
          barGap: "15%",
          itemStyle: {
            color: tk.categorical[i % 6],
            borderRadius: stacked && idx < visible.length - 1 ? 0 : horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0],
            borderColor: tk.surface,
            borderWidth: stacked ? 1 : 0,
            decal: s.kind === "what_if" ? { symbol: "rect", dashArrayX: [1, 0], dashArrayY: [2, 3], rotation: Math.PI / 4, color: "rgba(255,255,255,.35)" } : undefined,
          },
          data: s.values,
        })),
      };
    },
    [categories, series, unit, horizontal, stacked, hidden, locale],
  );

  const table = useMemo(
    () => ({
      caption: title,
      columns: [t.chart.category, ...series.map((s) => `${s.label}${unit ? ` (${unit})` : ""}`)],
      rows: categories.map((c, ci) => [c, ...series.map((s) => formatNumber(s.values[ci] ?? null, locale))]),
    }),
    [categories, series, unit, locale, title, t],
  );

  return (
    <ChartFrame
      title={title}
      description={description}
      summary={summary}
      legend={series.length > 1 ? series.map((s, i) => ({ key: s.key, label: s.label, color: `var(--chart-${(i % 6) + 1})`, pattern: "bar" as const, hidden: hidden.has(s.key) })) : undefined}
      onToggle={toggle}
      table={table}
      actions={actions}
      height={height}
      className={className}
      empty={state.empty ?? (!state.loading && !state.error && categories.length === 0)}
      {...state}
    >
      <EChart build={build} height={height} />
    </ChartFrame>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// HeatmapChart
// ─────────────────────────────────────────────────────────────────────────────

export function HeatmapChart({
  title,
  description,
  x,
  y,
  values,
  unit,
  scale = "sequential",
  domain,
  height = 280,
  summary,
  className,
  ...state
}: ChartStateProps & {
  title: string;
  description?: string;
  x: string[];
  y: string[];
  /** [xIndex, yIndex, value] triples. */
  values: [number, number, number | null][];
  unit?: string;
  /** sequential = magnitude (one hue); diverging = deviation around a neutral midpoint (domain must be symmetric). */
  scale?: "sequential" | "diverging";
  domain?: [number, number];
  height?: number;
  summary?: string;
  className?: string;
}) {
  const { locale } = useLocale();
  const t = useT(common);
  const nums = values.map((v) => v[2]).filter((v): v is number => v != null);
  const [min, max] = domain ?? (scale === "diverging" ? [-Math.max(...nums.map(Math.abs), 1), Math.max(...nums.map(Math.abs), 1)] : [Math.min(...nums, 0), Math.max(...nums, 1)]);

  const build = useCallback<BuildOption>(
    (tk) => ({
      ...baseGrid(tk),
      grid: { left: 8, right: 16, top: 8, bottom: 44, containLabel: true },
      tooltip: {
        ...baseGrid(tk).tooltip,
        trigger: "item",
        formatter: (p: { value: [number, number, number | null] }) =>
          `${esc(y[p.value[1]] ?? "")} · ${esc(x[p.value[0]] ?? "")}<br/><b style="font-variant-numeric:tabular-nums">${esc(formatValue(p.value[2], unit, locale))}</b>`,
      },
      xAxis: { type: "category", data: x, axisLabel: { color: tk.axis, fontSize: 10, hideOverlap: true }, axisTick: { show: false }, axisLine: { show: false }, splitArea: { show: false } },
      yAxis: { type: "category", data: y, axisLabel: { color: tk.axis, fontSize: 11 }, axisTick: { show: false }, axisLine: { show: false } },
      visualMap: {
        min,
        max,
        calculable: false,
        orient: "horizontal",
        left: "center",
        bottom: 0,
        itemHeight: 120,
        itemWidth: 10,
        textStyle: { color: tk.muted, fontSize: 10 },
        formatter: (v: number) => formatNumber(v, locale),
        inRange: { color: scale === "diverging" ? tk.diverging : tk.sequential },
      },
      series: [{ type: "heatmap", data: values, itemStyle: { borderColor: tk.surface, borderWidth: 2, borderRadius: 3 }, emphasis: { itemStyle: { borderColor: tk.text, borderWidth: 1 } } }],
    }),
    [x, y, values, unit, scale, min, max, locale],
  );

  const table = useMemo(() => {
    const grid = new Map(values.map(([xi, yi, v]) => [`${xi}:${yi}`, v]));
    return { caption: title, columns: ["", ...x], rows: y.map((yl, yi) => [yl, ...x.map((_, xi) => formatNumber(grid.get(`${xi}:${yi}`) ?? null, locale))]) };
  }, [values, x, y, locale, title]);

  return (
    <ChartFrame
      title={title}
      description={description ?? (unit ? `${t.chart.value}: ${unit}` : undefined)}
      summary={summary}
      table={table}
      height={height}
      className={className}
      empty={state.empty ?? (!state.loading && !state.error && values.length === 0)}
      {...state}
    >
      <EChart build={build} height={height} />
    </ChartFrame>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// GaugeChart
// ─────────────────────────────────────────────────────────────────────────────

export type GaugeBand = { to: number; tone: "success" | "warning" | "critical" };

export function GaugeChart({
  title,
  description,
  value,
  min = 0,
  max = 100,
  unit,
  bands = [],
  height = 200,
  className,
  ...state
}: ChartStateProps & {
  title: string;
  description?: string;
  value: number | null | undefined;
  min?: number;
  max?: number;
  unit?: string;
  /** Ascending `to` values; colour bands come from status tokens (API-provided thresholds — no TS business rules). */
  bands?: GaugeBand[];
  height?: number;
  className?: string;
}) {
  const { locale } = useLocale();
  const t = useT(common);
  const build = useCallback<BuildOption>(
    (tk) => {
      const toneColor = { success: tk.success, warning: tk.warning, critical: tk.critical };
      const axisColors: [number, string][] = bands.length
        ? bands.map((b) => [Math.min(1, Math.max(0, (b.to - min) / (max - min))), toneColor[b.tone]])
        : [[1, tk.categorical[0]!]];
      return {
        series: [
          {
            type: "gauge",
            min,
            max,
            startAngle: 205,
            endAngle: -25,
            radius: "92%",
            center: ["50%", "62%"],
            progress: { show: false },
            axisLine: { lineStyle: { width: 10, color: axisColors } },
            pointer: { width: 4, length: "58%", itemStyle: { color: tk.text } },
            anchor: { show: true, size: 10, itemStyle: { color: tk.text, borderColor: tk.surface, borderWidth: 2 } },
            axisTick: { show: false },
            splitLine: { length: 6, distance: -10, lineStyle: { color: tk.surface, width: 2 } },
            axisLabel: { distance: 14, color: tk.axis, fontSize: 10, formatter: (v: number) => formatNumber(v, locale) },
            detail: { valueAnimation: true, offsetCenter: [0, "38%"], fontSize: 20, fontWeight: 600, color: tk.text, formatter: () => formatValue(value, unit, locale) },
            data: [{ value: value ?? min }],
          },
        ],
      };
    },
    [value, min, max, unit, bands, locale],
  );
  return (
    <ChartFrame
      title={title}
      description={description}
      summary={`${title}: ${formatValue(value, unit, locale)} (${formatNumber(min, locale)}–${formatNumber(max, locale)})`}
      table={{ columns: [t.chart.value, "min", "max"], rows: [[formatValue(value, unit, locale), min, max]] }}
      height={height}
      className={className}
      empty={state.empty ?? (!state.loading && !state.error && (value === null || value === undefined))}
      {...state}
    >
      <EChart build={build} height={height} />
    </ChartFrame>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sparkline — tiny inline SVG (no ECharts; used inside KPI cards)
// ─────────────────────────────────────────────────────────────────────────────

export function Sparkline({
  points,
  width = 96,
  height = 28,
  kind = "synthetic_actual",
  className,
  label,
}: {
  points: SeriesPoint[] | undefined;
  width?: number;
  height?: number;
  kind?: Kind;
  className?: string;
  /** Accessible label, e.g. "OER trend, last 14 days". If omitted the sparkline is decorative. */
  label?: string;
}) {
  const vals = (points ?? []).map((p) => p.v).filter((v): v is number => v != null);
  if (vals.length < 2) return <span aria-hidden className={className} style={{ width, height, display: "inline-block" }} />;
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  const step = width / (vals.length - 1);
  const coords = vals.map((v, i) => [i * step, height - 3 - ((v - min) / span) * (height - 6)] as const);
  const d = coords.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const last = coords[coords.length - 1]!;
  const color = kind === "forecast" ? "var(--prov-forecast)" : kind === "what_if" ? "var(--prov-whatif)" : "var(--chart-1)";
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className={className} role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      <path d={`${d} L${width},${height} L0,${height} Z`} fill={color} opacity={0.08} />
      <path d={d} fill="none" stroke={color} strokeWidth={1.75} strokeLinejoin="round" strokeLinecap="round" strokeDasharray={kind === "forecast" ? "4 3" : kind === "what_if" ? "1 3" : undefined} />
      <circle cx={last[0]} cy={last[1]} r={2.5} fill={color} stroke="var(--surface)" strokeWidth={1.5} />
    </svg>
  );
}
