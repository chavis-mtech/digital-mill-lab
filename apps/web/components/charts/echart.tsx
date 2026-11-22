"use client";

import { useEffect, useRef, useState } from "react";
import * as echarts from "echarts/core";
import { BarChart, GaugeChart, HeatmapChart, LineChart, ScatterChart } from "echarts/charts";
import {
  AriaComponent,
  DataZoomComponent,
  GridComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import type { EChartsCoreOption } from "echarts/core";
import { readChartTokens, type ChartTokens } from "./tokens";
import { useTheme } from "@/lib/theme/theme";

echarts.use([
  LineChart,
  BarChart,
  HeatmapChart,
  GaugeChart,
  ScatterChart,
  GridComponent,
  TooltipComponent,
  MarkLineComponent,
  MarkAreaComponent,
  MarkPointComponent,
  DataZoomComponent,
  VisualMapComponent,
  AriaComponent,
  SVGRenderer,
]);

export type BuildOption = (tokens: ChartTokens) => EChartsCoreOption;

/**
 * Thin ECharts wrapper (tree-shaken, SVG renderer). `build` receives resolved theme tokens and is re-run on
 * theme change, so charts follow light/dark without hard-coded colours. The canvas is `aria-hidden`; the
 * accessible name/summary and data table live in <ChartFrame>.
 */
export function EChart({ build, height = 260, className }: { build: BuildOption; height?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.EChartsType | null>(null);
  const { resolved } = useTheme();
  const [tokens, setTokens] = useState<ChartTokens | null>(null);

  useEffect(() => {
    // Read after the theme class is applied (next frame).
    const id = requestAnimationFrame(() => setTokens(readChartTokens()));
    return () => cancelAnimationFrame(id);
  }, [resolved]);

  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current, undefined, { renderer: "svg" });
    chartRef.current = chart;
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!chartRef.current || !tokens) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const option = build(tokens) as Record<string, unknown>;
    chartRef.current.setOption(
      {
        animation: !reduce,
        animationDuration: 300,
        textStyle: { fontFamily: tokens.fontFamily, color: tokens.text },
        ...option,
      },
      { notMerge: true },
    );
  }, [build, tokens]);

  return <div ref={ref} aria-hidden className={className} style={{ height, width: "100%" }} />;
}
