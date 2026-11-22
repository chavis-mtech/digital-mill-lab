/**
 * Pure form + chart-geometry helpers for the scenario and ROI simulators (frontend-exec). These never compute
 * business results: they parse user input and place API-returned values on a pixel scale.
 */

/** Parse a user-typed number ("1,000", " 18.9 ", Thai digits are not expected). Empty/invalid → null. */
export function parseNumber(raw: string): number | null {
  const s = raw.replace(/[,\s]/g, "");
  if (s === "" || s === "-" || s === ".") return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

export type FormValues = Record<string, string>;

/** Seed form text from numbers (API defaults / baseline inputs). Non-numeric values are skipped. */
export function toFormValues(src: Record<string, unknown> | null | undefined, keys: readonly string[]): FormValues {
  const out: FormValues = {};
  for (const k of keys) {
    const v = src?.[k];
    if (typeof v === "number" && Number.isFinite(v)) out[k] = String(Math.round(v * 10000) / 10000);
  }
  return out;
}

/**
 * Build a request body from the form: every key whose text parses to a number. Returns the invalid keys too,
 * so the UI can flag them instead of silently dropping input.
 */
export function readForm(values: FormValues, keys: readonly string[]): { body: Record<string, number>; invalid: string[] } {
  const body: Record<string, number> = {};
  const invalid: string[] = [];
  for (const k of keys) {
    const raw = values[k];
    if (raw === undefined || raw.trim() === "") continue;
    const n = parseNumber(raw);
    if (n === null) invalid.push(k);
    else body[k] = n;
  }
  return { body, invalid };
}

export type TornadoBar = { variable: string; net_benefit_low_thb: number; net_benefit_high_thb: number };

/**
 * Pixel geometry for a tornado chart centred on the API's base net benefit. Bars are sorted by swing (widest
 * first). `x` is the left edge and `w` the width of each half bar, inside [0, width].
 */
export function tornadoGeometry<B extends TornadoBar>(bars: readonly B[], base: number, width: number) {
  const values = bars.flatMap((b) => [b.net_benefit_low_thb, b.net_benefit_high_thb]).concat(base);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const sx = (v: number) => ((v - min) / span) * width;
  const baseX = sx(base);
  const sorted = [...bars].sort(
    (a, b) => Math.abs(b.net_benefit_high_thb - b.net_benefit_low_thb) - Math.abs(a.net_benefit_high_thb - a.net_benefit_low_thb),
  );
  return {
    baseX,
    zeroX: min <= 0 && max >= 0 ? sx(0) : null,
    rows: sorted.map((b) => {
      const lo = sx(b.net_benefit_low_thb);
      const hi = sx(b.net_benefit_high_thb);
      return {
        bar: b,
        low: { x: Math.min(lo, baseX), w: Math.abs(lo - baseX) },
        high: { x: Math.min(hi, baseX), w: Math.abs(hi - baseX) },
      };
    }),
  };
}
