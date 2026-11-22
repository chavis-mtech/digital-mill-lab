"use client";

import { useLocale } from "@/lib/i18n/client";
import type { Bilingual } from "@/lib/i18n/define";

const STAGES: Bilingual[] = [
  { th: "รับผลปาล์ม", en: "FFB reception" },
  { th: "นึ่ง", en: "Sterilisation" },
  { th: "แยกผล", en: "Threshing" },
  { th: "ย่อย", en: "Digestion" },
  { th: "หีบ", en: "Pressing" },
  { th: "ทำใส", en: "Clarification" },
  { th: "ถังเก็บ CPO", en: "CPO storage" },
];

/**
 * Decorative-but-truthful hero illustration: the palm-mill process sequence (SPEC §1/§4 Digital Twin Lite
 * order). It deliberately shows NO numbers — real (synthetic) values live in the demo with provenance.
 */
export function ProcessLine({ label, caption }: { label: string; caption: string }) {
  const { locale } = useLocale();
  return (
    <figure className="relative rounded-2xl border border-border bg-surface/80 p-5 shadow-lg backdrop-blur-sm sm:p-6">
      <figcaption className="mb-4 flex items-center justify-between gap-3">
        <span className="text-xs font-semibold text-foreground">{label}</span>
        <span className="rounded-full border border-dashed border-warning/60 bg-warning-soft px-2 py-0.5 text-2xs font-medium text-warning-fg">Demo Palm Mill A (fictional)</span>
      </figcaption>
      <ol className="relative grid grid-cols-1 gap-2 sm:grid-cols-7 sm:gap-0">
        <span aria-hidden className="absolute top-[1.125rem] right-[7%] left-[7%] hidden h-0.5 overflow-hidden rounded bg-border sm:block">
          <span className="pc-flow absolute inset-y-0 w-1/4 bg-gradient-to-r from-transparent via-accent to-transparent" />
        </span>
        {STAGES.map((s, i) => (
          <li key={s.en} className="relative flex items-center gap-3 sm:flex-col sm:gap-2 sm:text-center">
            <span className="relative z-10 flex size-9 shrink-0 items-center justify-center rounded-full border border-border-strong bg-surface text-xs font-semibold text-foreground tabular shadow-xs">
              {i + 1}
            </span>
            <span className="text-xs leading-tight font-medium text-muted-foreground">{s[locale]}</span>
          </li>
        ))}
      </ol>
      <p className="mt-5 border-t border-border pt-3 text-2xs text-subtle-foreground">{caption}</p>
      <style>{`@keyframes pc-flow{from{left:-25%}to{left:100%}}.pc-flow{animation:pc-flow 3.2s linear infinite}@media (prefers-reduced-motion: reduce){.pc-flow{animation:none;display:none}}`}</style>
    </figure>
  );
}
