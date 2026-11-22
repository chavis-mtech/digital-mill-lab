"use client";

import { createContext, useCallback, useContext, useMemo, useTransition, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { LOCALE_COOKIE, type Locale } from "./config";
import { pick, type Messages, type Widen } from "./define";

type LocaleContextValue = { locale: Locale; setLocale: (next: Locale) => void; pending: boolean };

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({ initialLocale, children }: { initialLocale: Locale; children: ReactNode }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  const setLocale = useCallback(
    (next: Locale) => {
      // 1 year, lax, whole site. Not a tracking cookie: it only stores the UI language.
      document.cookie = `${LOCALE_COOKIE}=${next}; Path=/; Max-Age=31536000; SameSite=Lax`;
      document.documentElement.lang = next;
      startTransition(() => router.refresh());
    },
    [router],
  );

  const value = useMemo(() => ({ locale: initialLocale, setLocale, pending }), [initialLocale, setLocale, pending]);
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale(): LocaleContextValue {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useLocale must be used inside <LocaleProvider>");
  return ctx;
}

/** Client-side translation: `const t = useT(messages)` → `t.title`, `t.rows(3)`. */
export function useT<T>(messages: Messages<T>): Widen<T> {
  const { locale } = useLocale();
  return pick(messages, locale);
}
