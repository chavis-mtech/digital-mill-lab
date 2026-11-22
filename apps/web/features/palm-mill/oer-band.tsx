"use client";

import type { Schema } from "@dml/contracts";
import type { Series } from "@/components/charts/charts";

type Trend = Schema<"OerTrendResponse">;

/**
 * Reshape the API's expected-OER band (BandSeries) into lower/upper line series for TimeSeriesChart. The kit's
 * AreaBandChart styles its band as a *forecast*, which would mislabel a statistical range computed from synthetic
 * actuals; this keeps the API provenance. Pure reshaping — no values are computed.
 */
export function bandAsLines(band: Schema<"BandSeries"> | null | undefined, lowerLabel: string, upperLabel: string): Series[] {
  if (!band) return [];
  return [
    { key: `${band.key}_lower`, label: lowerLabel, unit: band.unit, provenance: band.provenance, points: band.points.map((p) => ({ t: p.t, v: p.lower ?? null })) },
    { key: `${band.key}_upper`, label: upperLabel, unit: band.unit, provenance: band.provenance, points: band.points.map((p) => ({ t: p.t, v: p.upper ?? null })) },
  ];
}

/** Series list for the OER-vs-expected chart: observed OER, expected OER, then the range bounds. */
export function oerChartSeries(d: Trend, lowerLabel: string, upperLabel: string): Series[] {
  return [d.oer, ...(d.expected_oer ? [d.expected_oer] : []), ...bandAsLines(d.expected_band, lowerLabel, upperLabel)];
}
