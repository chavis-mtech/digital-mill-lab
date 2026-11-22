"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type ThemePreference = "system" | "light" | "dark";
export const THEME_STORAGE_KEY = "dml_theme";

/**
 * Inline, render-blocking script (in <head>) that applies the theme before first paint to avoid a flash.
 * Keep it tiny and dependency-free.
 */
export const themeInitScript = `(function(){try{var p=localStorage.getItem('${THEME_STORAGE_KEY}')||'system';var d=p==='dark'||(p==='system'&&matchMedia('(prefers-color-scheme: dark)').matches);var e=document.documentElement;e.classList.toggle('dark',d);e.dataset.theme=d?'dark':'light';}catch(_){}})();`;

type ThemeContextValue = { preference: ThemePreference; resolved: "light" | "dark"; setPreference: (p: ThemePreference) => void };
const ThemeCtx = createContext<ThemeContextValue | null>(null);

function systemDark() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPref] = useState<ThemePreference>("system");
  const [resolved, setResolved] = useState<"light" | "dark">("light");

  useEffect(() => {
    let stored: ThemePreference = "system";
    try {
      const v = window.localStorage.getItem(THEME_STORAGE_KEY);
      if (v === "light" || v === "dark" || v === "system") stored = v;
    } catch {
      /* ignore */
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect -- hydrate from browser-only storage
    setPref(stored);
  }, []);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      const dark = preference === "dark" || (preference === "system" && mq.matches);
      const root = document.documentElement;
      root.classList.toggle("dark", dark);
      root.dataset.theme = dark ? "dark" : "light";
      setResolved(dark ? "dark" : "light");
      window.dispatchEvent(new CustomEvent("pc:themechange", { detail: dark ? "dark" : "light" }));
    };
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, [preference]);

  const setPreference = useCallback((p: ThemePreference) => {
    setPref(p);
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, p);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo(() => ({ preference, resolved, setPreference }), [preference, resolved, setPreference]);
  return <ThemeCtx.Provider value={value}>{children}</ThemeCtx.Provider>;
}

export function useTheme(): ThemeContextValue {
  const v = useContext(ThemeCtx);
  if (!v) return { preference: "system", resolved: systemDark() ? "dark" : "light", setPreference: () => {} };
  return v;
}
