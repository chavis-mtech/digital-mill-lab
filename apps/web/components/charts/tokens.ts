"use client";

/**
 * Resolve design tokens (CSS variables, may be oklch) to rgba strings ECharts/zrender can parse.
 * We paint each colour onto a 1×1 canvas and read the pixel back, which works for any CSS colour syntax.
 */
let ctx: CanvasRenderingContext2D | null = null;

export function cssColor(varName: string, alpha?: number): string {
  if (typeof window === "undefined") return "#888";
  const raw = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
  if (!raw) return "#888";
  ctx ??= document.createElement("canvas").getContext("2d", { willReadFrequently: true });
  if (!ctx) return raw;
  ctx.clearRect(0, 0, 1, 1);
  ctx.fillStyle = "#000";
  ctx.fillStyle = raw;
  ctx.fillRect(0, 0, 1, 1);
  const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data as unknown as [number, number, number, number];
  const finalAlpha = alpha ?? +(a / 255).toFixed(3);
  return `rgba(${r}, ${g}, ${b}, ${finalAlpha})`;
}

export type ChartTokens = {
  categorical: string[];
  sequential: string[];
  diverging: string[];
  text: string;
  muted: string;
  axis: string;
  grid: string;
  surface: string;
  border: string;
  band: string;
  normalBand: string;
  success: string;
  warning: string;
  critical: string;
  maintenance: string;
  forecast: string;
  whatIf: string;
  actual: string;
  fontFamily: string;
};

export function readChartTokens(): ChartTokens {
  const fontFamily = typeof window === "undefined" ? "sans-serif" : getComputedStyle(document.body).fontFamily;
  return {
    categorical: [1, 2, 3, 4, 5, 6, 7].map((i) => cssColor(`--chart-${i}`)),
    sequential: [1, 2, 3, 4, 5, 6].map((i) => cssColor(`--seq-${i}`)),
    diverging: ["--div-neg-3", "--div-neg-2", "--div-neg-1", "--div-mid", "--div-pos-1", "--div-pos-2", "--div-pos-3"].map((v) => cssColor(v)),
    text: cssColor("--foreground"),
    muted: cssColor("--muted-foreground"),
    axis: cssColor("--chart-axis"),
    grid: cssColor("--chart-grid"),
    surface: cssColor("--surface"),
    border: cssColor("--border"),
    band: cssColor("--chart-band"),
    normalBand: cssColor("--chart-normal-band"),
    success: cssColor("--success"),
    warning: cssColor("--warning"),
    critical: cssColor("--critical"),
    maintenance: cssColor("--maintenance"),
    forecast: cssColor("--prov-forecast"),
    whatIf: cssColor("--prov-whatif"),
    actual: cssColor("--prov-actual"),
    fontFamily,
  };
}
