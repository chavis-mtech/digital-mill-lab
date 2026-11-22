import { INTL_LOCALE, type Locale } from "@/lib/i18n/config";

/**
 * Display formatting only (ADR-002: no business formulas in TypeScript). These helpers never compute
 * KPIs — they render numbers the API already computed. Times are shown in mill time (Asia/Bangkok).
 */
export const MILL_TIMEZONE = "Asia/Bangkok";

const nfCache = new Map<string, Intl.NumberFormat>();
function nf(locale: Locale, opts: Intl.NumberFormatOptions) {
  const key = locale + JSON.stringify(opts);
  let f = nfCache.get(key);
  if (!f) {
    f = new Intl.NumberFormat(INTL_LOCALE[locale], opts);
    nfCache.set(key, f);
  }
  return f;
}

export const EMPTY = "—";

export function formatNumber(
  value: number | null | undefined,
  locale: Locale,
  opts: { digits?: number; minDigits?: number; compact?: boolean } = {},
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY;
  const { digits, minDigits, compact } = opts;
  const auto = digits ?? (Math.abs(value) >= 1000 ? 0 : Math.abs(value) >= 100 ? 1 : 2);
  return nf(locale, {
    maximumFractionDigits: auto,
    minimumFractionDigits: minDigits ?? 0,
    notation: compact ? "compact" : "standard",
  }).format(value);
}

/** Units that read better glued to the number. */
const TIGHT_UNITS = new Set(["%", "pp"]);

export function formatValue(
  value: number | null | undefined,
  unit: string | null | undefined,
  locale: Locale,
  opts?: { digits?: number; compact?: boolean },
): string {
  const n = formatNumber(value, locale, opts);
  if (n === EMPTY || !unit) return n;
  return TIGHT_UNITS.has(unit) ? `${n}${unit === "pp" ? " pp" : unit}` : `${n} ${unit}`;
}

export function formatSigned(value: number | null | undefined, locale: Locale, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY;
  const s = formatNumber(Math.abs(value), locale, { digits, minDigits: digits > 0 ? Math.min(digits, 1) : 0 });
  if (value > 0) return `+${s}`;
  if (value < 0) return `−${s}`;
  return s;
}

export function formatPercent(value: number | null | undefined, locale: Locale, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY;
  return nf(locale, { style: "percent", maximumFractionDigits: digits }).format(value / 100);
}

type DateStyle = "date" | "datetime" | "time" | "short" | "month";
const DATE_OPTS: Record<DateStyle, Intl.DateTimeFormatOptions> = {
  date: { day: "numeric", month: "short", year: "numeric" },
  datetime: { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false },
  time: { hour: "2-digit", minute: "2-digit", hour12: false },
  short: { day: "numeric", month: "short" },
  month: { month: "short", year: "numeric" },
};

export function formatDate(iso: string | Date | null | undefined, locale: Locale, style: DateStyle = "date"): string {
  if (!iso) return EMPTY;
  const d = typeof iso === "string" ? new Date(iso) : iso;
  if (Number.isNaN(d.getTime())) return EMPTY;
  return new Intl.DateTimeFormat(INTL_LOCALE[locale], { ...DATE_OPTS[style], timeZone: MILL_TIMEZONE }).format(d);
}

/** YYYY-MM-DD of an instant in mill time — used to build `as_of` query values from date pickers. */
export function millDateKey(iso: string | Date): string {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: MILL_TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(d);
  return parts; // en-CA yields YYYY-MM-DD
}
