"use client";

import { useCallback } from "react";
import { useT } from "@/lib/i18n/client";
import { useLocale } from "@/lib/i18n/client";
import { SCENARIO_LABELS, type ScenarioCode } from "@/lib/demo/constants";
import messages from "./executive.i18n";

/** Localised KPI label by API key, falling back to the API's (English) label for keys we do not know. */
export function useKpiLabel() {
  const t = useT(messages);
  const map = t.kpiLabel as Readonly<Record<string, string>>;
  return useCallback((key: string, apiLabel: string) => map[key] ?? apiLabel, [map]);
}

/** Localised scenario name (built-in TH/EN labels; the API name is used for unknown codes). */
export function useScenarioLabel() {
  const { locale } = useLocale();
  return useCallback(
    (code: string, apiLabel?: string) => SCENARIO_LABELS[code as ScenarioCode]?.[locale] ?? apiLabel ?? code,
    [locale],
  );
}
