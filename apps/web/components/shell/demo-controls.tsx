"use client";

import { useId } from "react";
import { CalendarClock, Clapperboard, Radio, RotateCcw, Settings2, UserRound } from "lucide-react";
import type { DemoRole } from "@dml/contracts";
import { useApiQuery } from "@/lib/api/hooks";
import { useDemo } from "@/lib/demo/context";
import { PLAYBACK_LABELS, PLAYBACK_MODES, ROLE_LABELS, ROLES, SCENARIO_CODES, SCENARIO_LABELS, type PlaybackMode, type ScenarioCode } from "@/lib/demo/constants";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { LanguageToggle, ThemeToggle } from "./preferences";
import common from "@/messages/common.i18n";

const NONE = "__none";

function useLabels() {
  const { locale } = useLocale();
  const scenarios = useApiQuery("/api/v1/scenarios", undefined, { withClock: false, staleTime: 5 * 60_000 });
  const roles = useApiQuery("/api/v1/demo/roles", undefined, { withClock: false, staleTime: 10 * 60_000 });
  const scenarioName = (code: ScenarioCode) => {
    const s = scenarios.data?.items.find((i) => i.code === code);
    return s ? (locale === "th" ? s.name_th : s.name_en) : SCENARIO_LABELS[code][locale];
  };
  const roleName = (role: DemoRole) => {
    const r = roles.data?.items.find((i) => i.role === role);
    return r ? (locale === "th" ? r.label_th : r.label_en) : ROLE_LABELS[role][locale];
  };
  return { scenarioName, roleName, catalogFallback: scenarios.isError };
}

/** Resolved demo clock from GET /api/v1/demo/context (implemented): what the server will actually use. */
function useResolvedClock() {
  return useApiQuery("/api/v1/demo/context", undefined, { staleTime: 30_000 });
}

function Fields({ layout }: { layout: "row" | "stack" }) {
  const t = useT(common);
  const { locale } = useLocale();
  const demo = useDemo();
  const { scenarioName, roleName, catalogFallback } = useLabels();
  const ids = { scenario: useId(), playback: useId(), role: useId() };
  const row = layout === "row";

  const scenarioField = (
    <div className={cn("flex min-w-0 flex-col gap-1", row && "w-[13.5rem]")}>
      <Label htmlFor={ids.scenario} className={cn(row && "sr-only")}>
        {t.controls.scenario}
      </Label>
      <Select value={demo.scenarioId ?? NONE} onValueChange={(v) => demo.setScenario(v === NONE ? null : (v as ScenarioCode))}>
        <SelectTrigger id={ids.scenario} size="sm" data-tour="demo-scenario">
          <Clapperboard className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={NONE}>{t.controls.noScenario}</SelectItem>
          {SCENARIO_CODES.map((c) => (
            <SelectItem key={c} value={c}>
              {scenarioName(c)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {!row && catalogFallback ? <p className="text-2xs text-subtle-foreground">{t.controls.scenarioCatalogFallback}</p> : null}
    </div>
  );

  const playbackField = (
    <div className={cn("flex min-w-0 flex-col gap-1", row && "w-[10.5rem]")}>
      <Label htmlFor={ids.playback} className={cn(row && "sr-only")}>
        {t.controls.playback}
      </Label>
      <Select value={demo.playback} onValueChange={(v) => demo.setPlayback(v as PlaybackMode)}>
        <SelectTrigger id={ids.playback} size="sm">
          {demo.playback === "simulated_live" ? (
            <Radio className="size-3.5 shrink-0 text-accent-text" aria-hidden />
          ) : (
            <CalendarClock className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
          )}
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {PLAYBACK_MODES.map((m) => (
            <SelectItem key={m} value={m} disabled={m === "scenario_date" && !demo.scenarioId}>
              {PLAYBACK_LABELS[m][locale]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );

  const roleField = (
    <div className={cn("flex min-w-0 flex-col gap-1", row && "w-[12.5rem]")}>
      <Label htmlFor={ids.role} className={cn(row && "sr-only")}>
        {t.controls.role}
        {row ? ` — ${t.controls.roleNotice}` : null}
      </Label>
      <Select value={demo.role} onValueChange={(v) => demo.setRole(v as DemoRole)}>
        <SelectTrigger id={ids.role} size="sm" aria-describedby={`${ids.role}-note`}>
          <UserRound className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {ROLES.map((r) => (
            <SelectItem key={r} value={r}>
              {roleName(r)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <p id={`${ids.role}-note`} className={cn("text-2xs text-subtle-foreground", row && "sr-only")}>
        {t.controls.roleNotice}
      </p>
    </div>
  );

  return (
    <div className={cn(row ? "flex items-center gap-2" : "flex flex-col gap-3")}>
      {scenarioField}
      {playbackField}
      {roleField}
    </div>
  );
}

/** Live-mode status chip; honest about the simulation and about the endpoint being a stub. */
function LiveChip() {
  const t = useT(common);
  const { live, playback } = useDemo();
  if (playback !== "simulated_live") return null;
  const text = live.status === "running" ? t.controls.liveRunning : live.status === "unavailable" ? t.controls.liveUnavailable : live.status === "error" ? t.controls.liveError : t.controls.liveRunning;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          tabIndex={0}
          role="status"
          className={cn(
            "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-2xs font-semibold whitespace-nowrap",
            live.status === "running" ? "border-accent/40 bg-accent-soft text-accent-text" : "border-dashed border-border-strong bg-neutral-soft text-neutral-fg",
          )}
        >
          <Radio className={cn("size-3", live.status === "running" && "animate-pulse")} aria-hidden />
          {t.controls.liveBadge}
          <span className="sr-only">{text}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent>{text}</TooltipContent>
    </Tooltip>
  );
}

function ClockReadout({ className }: { className?: string }) {
  const t = useT(common);
  const { locale } = useLocale();
  const q = useResolvedClock();
  const asOf = q.data?.context.as_of;
  return (
    <p className={cn("tabular flex flex-col text-right leading-tight", className)}>
      <span className="text-[0.625rem] font-medium tracking-wide text-subtle-foreground uppercase">{t.controls.asOf}</span>
      <span className="text-xs font-semibold whitespace-nowrap text-foreground">{asOf ? formatDate(asOf, locale, "datetime") : q.isError ? "—" : "…"}</span>
    </p>
  );
}

/**
 * Top-bar demo controls: scenario switcher, playback, simulated role, language, theme.
 * ≥ xl: inline. Below: a "Demo settings" popover with the same, fully labelled fields.
 */
export function DemoControls() {
  const t = useT(common);
  const demo = useDemo();
  return (
    <div className="flex items-center gap-2" aria-label={t.controls.label} role="group">
      <div className="hidden items-center gap-2 2xl:flex">
        <Fields layout="row" />
      </div>
      <LiveChip />
      <ClockReadout className="hidden xl:flex" />
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm" className="2xl:hidden" aria-label={t.controls.settings}>
            <Settings2 aria-hidden />
            <span className="max-sm:sr-only">{t.controls.settings}</span>
          </Button>
        </PopoverTrigger>
        <PopoverContent align="end" className="w-[min(20rem,calc(100vw-1.5rem))]">
          <p className="mb-3 text-sm font-semibold">{t.controls.label}</p>
          <Fields layout="stack" />
          <div className="mt-3 flex items-center justify-between gap-2 border-t border-border pt-3 xl:hidden">
            <ClockReadout className="items-start text-left" />
          </div>
          <div className="mt-3 flex items-center justify-between gap-2 border-t border-border pt-3">
            <LanguageToggle />
            <Button variant="ghost" size="xs" onClick={demo.reset}>
              <RotateCcw aria-hidden /> {t.controls.resetContext}
            </Button>
          </div>
        </PopoverContent>
      </Popover>
      <LanguageToggle className="hidden sm:inline-flex" />
      <ThemeToggle />
    </div>
  );
}
