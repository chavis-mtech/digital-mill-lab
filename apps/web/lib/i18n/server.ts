import "server-only";
import { cookies } from "next/headers";
import { DEFAULT_LOCALE, isLocale, LOCALE_COOKIE, type Locale } from "./config";
import { pick, type Messages, type Widen } from "./define";

/** Read the visitor's locale from the cookie (server components / route handlers). */
export async function getLocale(): Promise<Locale> {
  const store = await cookies();
  const value = store.get(LOCALE_COOKIE)?.value;
  return isLocale(value) ? value : DEFAULT_LOCALE;
}

/** Server-side translation: `const t = await getT(messages)`. */
export async function getT<T>(messages: Messages<T>): Promise<Widen<T>> {
  return pick(messages, await getLocale());
}
