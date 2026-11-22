/** i18n configuration (ADR-008): cookie-based locale, TH default, EN option, no route prefix. */
export const LOCALES = ["th", "en"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "th";
export const LOCALE_COOKIE = "dml_locale";

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (LOCALES as readonly string[]).includes(value);
}

/** BCP-47 tags used for Intl formatting. Gregorian calendar keeps dates aligned with ISO data/API values. */
export const INTL_LOCALE: Record<Locale, string> = { th: "th-TH-u-ca-gregory", en: "en-GB" };
