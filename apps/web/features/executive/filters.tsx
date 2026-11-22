"use client";

import { CalendarDays, Factory, RotateCcw } from "lucide-react";
import { useApiQuery } from "@/lib/api/hooks";
import { useDemo } from "@/lib/demo/context";
import { useT } from "@/lib/i18n/client";
import { millDateKey } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import messages from "./executive.i18n";

/**
 * Executive filters (SPEC §4-A: date, period, unit). They drive the shared DemoContext (not local state), so
 * every page and the DemoControls stay consistent with the selection.
 */
export function ExecutiveFilters() {
  const t = useT(messages);
  const { period, scenarioId, asOf, setPlayback, setAsOf } = useDemo();
  const meta = useApiQuery("/api/v1/meta", undefined, { withClock: false, staleTime: 5 * 60_000 });
  const win = meta.data?.data_window;

  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label={t.filters.label}>
      <ToggleGroup
        type="single"
        value={period === "custom" ? "" : period}
        aria-label={t.filters.period}
        onValueChange={(v) => {
          if (v === "today") setPlayback(scenarioId ? "scenario_date" : "today");
          else if (v === "7d") setPlayback("last_7_days");
          else if (v === "30d") setPlayback("last_30_days");
        }}
      >
        <ToggleGroupItem value="today">{t.filters.today}</ToggleGroupItem>
        <ToggleGroupItem value="7d">{t.filters.d7}</ToggleGroupItem>
        <ToggleGroupItem value="30d">{t.filters.d30}</ToggleGroupItem>
      </ToggleGroup>
      <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <CalendarDays className="size-3.5" aria-hidden />
        <span className="sr-only sm:not-sr-only">{t.filters.date}</span>
        <Input
          type="date"
          className="h-8 w-[9.5rem] text-xs"
          value={asOf ? millDateKey(asOf) : ""}
          min={win?.start_date}
          max={win?.end_date}
          title={t.filters.dateHint}
          aria-describedby="exec-date-hint"
          onChange={(e) => setAsOf(e.target.value || null)}
        />
        <span id="exec-date-hint" className="sr-only">
          {t.filters.dateHint}
        </span>
      </label>
      {asOf ? (
        <Button variant="ghost" size="xs" onClick={() => setAsOf(null)}>
          <RotateCcw aria-hidden /> {t.filters.clearDate}
        </Button>
      ) : null}
      <span
        className="inline-flex h-8 items-center gap-1.5 rounded-md border border-border bg-surface px-2.5 text-xs text-muted-foreground"
        title={t.filters.unitNote}
      >
        <Factory className="size-3.5" aria-hidden />
        <span className="sr-only">{t.filters.unit}:</span>
        {t.filters.unitOnly}
      </span>
    </div>
  );
}
