import type { Locale } from "./config";

/**
 * Deep-widen a message tree: literal strings become `string`, functions keep their signature.
 * The TH dictionary is the source of truth; EN must have exactly the same shape (checked by tsc AND by
 * `lib/i18n/dictionaries.test.ts`).
 */
export type Widen<T> = T extends string
  ? string
  : T extends (...args: infer A) => string
    ? (...args: A) => string
    : T extends readonly (infer U)[]
      ? readonly Widen<U>[]
      : { readonly [K in keyof T]: Widen<T[K]> };

export type MessageTree = {
  readonly [key: string]: string | ((...args: never[]) => string) | MessageTree | readonly string[] | readonly MessageTree[];
};

export type Messages<T> = { readonly th: T; readonly en: Widen<T> };

/**
 * Declare a bilingual message bundle. Put each bundle in a file named `*.i18n.ts` (default export) so the
 * key-parity test picks it up automatically.
 *
 * @example
 *   export default defineMessages({
 *     th: { title: "ศูนย์ควบคุมผู้บริหาร", rows: (n: number) => `${n} รายการ` },
 *     en: { title: "Executive Control Tower", rows: (n: number) => `${n} rows` },
 *   });
 */
export function defineMessages<const T extends MessageTree>(messages: { th: T; en: Widen<T> }): Messages<T> {
  return messages;
}

/** Pick the dictionary for a locale. */
export function pick<T>(messages: Messages<T>, locale: Locale): Widen<T> {
  return (locale === "th" ? messages.th : messages.en) as Widen<T>;
}

/** Inline bilingual value, for content objects: `{ th: "…", en: "…" }`. */
export type Bilingual<T = string> = { th: T; en: T };

export function bi<T>(value: Bilingual<T>, locale: Locale): T {
  return value[locale];
}
