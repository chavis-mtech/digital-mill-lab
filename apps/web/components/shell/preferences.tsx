"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useLocale, useT } from "@/lib/i18n/client";
import { useTheme, type ThemePreference } from "@/lib/theme/theme";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuLabel, DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import common from "@/messages/common.i18n";

/** TH | EN segmented switch (cookie-based, ADR-008). */
export function LanguageToggle({ className }: { className?: string }) {
  const { locale, setLocale, pending } = useLocale();
  const t = useT(common);
  return (
    <div role="group" aria-label={t.controls.language} className={cn("inline-flex items-center rounded-md border border-border bg-surface p-0.5", className)} aria-busy={pending}>
      {(["th", "en"] as const).map((l) => (
        <button
          key={l}
          type="button"
          lang={l}
          aria-pressed={locale === l}
          onClick={() => locale !== l && setLocale(l)}
          className={cn(
            "h-7 min-w-8 rounded px-2 text-xs font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
            locale === l ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
          )}
        >
          {l === "th" ? "ไทย" : "EN"}
        </button>
      ))}
    </div>
  );
}

const THEME_ICON = { system: Monitor, light: Sun, dark: Moon } as const;

export function ThemeToggle() {
  const { preference, setPreference } = useTheme();
  const t = useT(common);
  const labels: Record<ThemePreference, string> = { system: t.controls.themeSystem, light: t.controls.themeLight, dark: t.controls.themeDark };
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label={t.controls.theme}>
          {/* Icon follows the applied .dark class via CSS so SSR and hydration always match. */}
          <Sun aria-hidden className="dark:hidden" />
          <Moon aria-hidden className="hidden dark:block" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-40">
        <DropdownMenuLabel>{t.controls.theme}</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={preference} onValueChange={(v) => setPreference(v as ThemePreference)}>
          {(["system", "light", "dark"] as const).map((p) => {
            const I = THEME_ICON[p];
            return (
              <DropdownMenuRadioItem key={p} value={p}>
                <I className="size-4 text-muted-foreground" aria-hidden />
                {labels[p]}
              </DropdownMenuRadioItem>
            );
          })}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
