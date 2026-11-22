"use client";

import { useId, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CircleCheck, OctagonExclamationPoint, TriangleExclamationPoint, Wrench, type LucideIcon } from "lucide-react";
import type { Schema } from "@dml/contracts";
import { useApiQuery } from "@/lib/api/hooks";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatDate, formatValue } from "@/lib/format";
import { cn } from "@/lib/utils";
import { OperationsLayout } from "@/components/layouts/layouts";
import { AlertBadge } from "@/components/demo/severity";
import { ProvenanceBadge } from "@/components/demo/provenance-badge";
import { Disclaimer } from "@/components/demo/disclaimer";
import { QueryState } from "@/components/states/states";
import { ApiText, Section } from "@/features/executive/shared/section";
import common from "@/messages/common.i18n";
import messages from "./palm-mill.i18n";
import { StagePanel } from "./stage-panel";
import { NODE_H, NODE_W, VIEW_H, VIEW_W, drawableEdges, edgePath, healthTone, layoutTwin, pickDefaultStage, type HealthState } from "./twin-model";

type Stage = Schema<"StageState">;

const ICON: Record<HealthState, LucideIcon> = {
  normal: CircleCheck,
  warning: TriangleExclamationPoint,
  critical: OctagonExclamationPoint,
  maintenance_required: Wrench,
};

function NodeCard({ stage, selected, onSelect }: { stage: Stage; selected: boolean; onSelect: () => void }) {
  const t = useT(messages);
  const tc = useT(common);
  const { locale } = useLocale();
  const name = locale === "th" ? stage.name_th : stage.name_en;
  const tone = healthTone(stage.status);
  const Icon = ICON[stage.status];
  const k = stage.headline_kpi;
  return (
    <div
      data-stage={stage.code}
      data-health={stage.status}
      onClick={onSelect}
      className={cn(
        "flex h-full cursor-pointer flex-col gap-1 rounded-lg border-2 p-2 text-left shadow-xs transition-shadow",
        selected ? "ring-2 ring-ring ring-offset-2 ring-offset-background" : "hover:shadow-md",
      )}
      style={{ background: tone.fill, borderColor: tone.stroke }}
    >
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onSelect();
        }}
        aria-pressed={selected}
        className="flex flex-col gap-0.5 rounded text-left focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        <span className="line-clamp-2 text-[0.8125rem] leading-tight font-semibold text-foreground">{name}</span>
        <span className="inline-flex items-center gap-1 text-2xs font-semibold" style={{ color: tone.text }}>
          <Icon className="size-3" aria-hidden />
          {tc.health[stage.status]}
          {stage.active_alerts ? (
            <span className="tabular ml-1 rounded bg-critical px-1 text-white dark:text-[oklch(0.18_0.02_25)]">
              {stage.active_alerts}
              <span className="sr-only"> {t.twin.alerts(stage.active_alerts)}</span>
            </span>
          ) : null}
        </span>
      </button>
      <div className="mt-auto flex items-center justify-between gap-1 text-2xs">
        {k ? (
          <span className="min-w-0 truncate text-muted-foreground" title={k.label}>
            <span className="tabular font-semibold text-foreground">{formatValue(k.value, k.unit, locale)}</span>
          </span>
        ) : (
          <span className="text-muted-foreground">{t.twin.noKpi}</span>
        )}
        {k ? <ProvenanceBadge provenance={k.provenance} compact /> : null}
      </div>
    </div>
  );
}

function TwinDiagram({ stages, edges, selected, onSelect }: { stages: Stage[]; edges: Schema<"FlowEdge">[]; selected: string | null; onSelect: (c: string) => void }) {
  const markerId = useId().replace(/:/g, "");
  const boxes = layoutTwin(stages);
  const byCode = new Map<string, Stage>(stages.map((s) => [s.code, s]));
  return (
    <svg viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} className="h-auto w-full min-w-[52rem]" role="group" aria-labelledby="twin-diagram-title">
      <defs>
        <marker id={markerId} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" fill="var(--muted-foreground)" />
        </marker>
      </defs>
      {drawableEdges(edges, boxes).map(({ edge, a, b }) => (
        <path
          key={`${edge.source}-${edge.target}`}
          d={edgePath(a, b)}
          fill="none"
          stroke="var(--muted-foreground)"
          strokeWidth={1.5}
          strokeDasharray={a.row === "support" || b.row === "support" ? "5 4" : undefined}
          markerEnd={`url(#${markerId})`}
          aria-hidden
        >
          <title>{edge.material}</title>
        </path>
      ))}
      {boxes.map((b) => {
        const s = byCode.get(b.code);
        if (!s) return null;
        return (
          <foreignObject key={b.code} x={b.x} y={b.y} width={NODE_W} height={NODE_H} className="overflow-visible">
            <NodeCard stage={s} selected={selected === s.code} onSelect={() => onSelect(s.code)} />
          </foreignObject>
        );
      })}
    </svg>
  );
}

/** Ordered list mirroring the diagram — visible on phones and as the text alternative on larger screens. */
function StageList({ stages, edges, selected, onSelect }: { stages: Stage[]; edges: Schema<"FlowEdge">[]; selected: string | null; onSelect: (c: string) => void }) {
  const t = useT(messages);
  const tc = useT(common);
  const { locale } = useLocale();
  const groups: Array<[string, Stage[]]> = [
    [t.twin.mainLine, stages.filter((s) => s.kind === "main").sort((a, b) => a.sequence - b.sequence)],
    [t.twin.support, stages.filter((s) => s.kind !== "main").sort((a, b) => a.sequence - b.sequence)],
  ];
  return (
    <div className="flex flex-col gap-3">
      {groups.map(([title, list]) => (
        <div key={title}>
          <h3 className="mb-1 text-xs font-semibold text-muted-foreground">{title}</h3>
          <ol className="flex flex-col gap-1">
            {list.map((s) => {
              const name = locale === "th" ? s.name_th : s.name_en;
              const out = edges.filter((e) => e.source === s.code);
              return (
                <li key={s.code}>
                  <button
                    type="button"
                    aria-pressed={selected === s.code}
                    onClick={() => onSelect(s.code)}
                    className={cn(
                      "flex w-full flex-wrap items-center gap-2 rounded-md border border-border px-2 py-1.5 text-left text-xs focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                      selected === s.code ? "bg-accent-soft/50" : "bg-surface hover:bg-surface-2",
                    )}
                  >
                    <AlertBadge state={s.status} count={s.active_alerts || undefined} />
                    <span className="font-medium">{name}</span>
                    {s.headline_kpi ? (
                      <span className="tabular text-muted-foreground">
                        {s.headline_kpi.label}: {formatValue(s.headline_kpi.value, s.headline_kpi.unit, locale)}
                      </span>
                    ) : null}
                    {out.length ? <span className="w-full text-2xs text-subtle-foreground">→ {out.map((e) => `${e.target} (${e.material})`).join(", ")}</span> : null}
                    <span className="sr-only">{tc.health[s.status]}</span>
                  </button>
                </li>
              );
            })}
          </ol>
        </div>
      ))}
    </div>
  );
}

/** Digital Twin Lite (DML-079/080/081): node state from GET /process/stages at the demo clock. */
export function ProcessTwin() {
  const t = useT(messages);
  const tc = useT(common);
  const { locale } = useLocale();
  const params = useSearchParams();
  const [picked, setPicked] = useState<string | null>(null);
  const q = useApiQuery("/api/v1/process/stages");
  const stages = q.data?.stages ?? [];
  const selected = pickDefaultStage(stages, picked ?? params.get("stage"));
  const sel = stages.find((s) => s.code === selected);

  const select = (code: string) => {
    setPicked(code);
    const url = new URL(window.location.href);
    url.searchParams.set("stage", code);
    window.history.replaceState(window.history.state, "", url);
  };

  return (
    <OperationsLayout route="/demo/palm-mill/process">
      <div className="grid grid-cols-[minmax(0,1fr)] gap-5 min-[1700px]:grid-cols-[minmax(0,1fr)_32rem]">
        <Section
          id="twin"
          title={<span id="twin-diagram-title">{t.twin.diagramTitle}</span>}
          description={q.data ? t.twin.diagramDesc(formatDate(q.data.ts, locale, "datetime")) : undefined}
          actions={q.data ? <ProvenanceBadge provenance={q.data.provenance} /> : null}
          className="self-start"
        >
          <QueryState query={q} isEmpty={(d) => d.stages.length === 0}>
            {(d) => (
              <>
                <p className="text-2xs text-muted-foreground">{t.twin.clickHint}</p>
                <div className="relative hidden overflow-x-auto pb-1 md:block">
                  <TwinDiagram stages={d.stages} edges={d.edges} selected={selected} onSelect={select} />
                </div>
                <ul className="flex flex-wrap gap-2 text-2xs" aria-label={t.twin.legend}>
                  {(["normal", "warning", "maintenance_required", "critical"] as const).map((s) => (
                    <li key={s}>
                      <AlertBadge state={s} />
                    </li>
                  ))}
                </ul>
                <div className="md:hidden">
                  <StageList stages={d.stages} edges={d.edges} selected={selected} onSelect={select} />
                </div>
                <details className="hidden md:block">
                  <summary className="cursor-pointer text-xs font-medium text-accent-text">{t.twin.textAlt}</summary>
                  <div className="mt-2">
                    <StageList stages={d.stages} edges={d.edges} selected={selected} onSelect={select} />
                  </div>
                </details>
                {d.health_rule ? (
                  <p className="text-2xs text-muted-foreground">
                    {t.twin.healthRule}: <ApiText>{d.health_rule}</ApiText>
                  </p>
                ) : null}
                <Disclaimer kind="advisory" className="text-2xs" />
                <p className="text-2xs text-subtle-foreground">{t.twin.sim}</p>
              </>
            )}
          </QueryState>
        </Section>
        {sel ? <StagePanel key={sel.code} code={sel.code} name={locale === "th" ? sel.name_th : sel.name_en} /> : null}
      </div>
      <span className="sr-only" aria-live="polite">
        {sel ? `${t.twin.selected}: ${locale === "th" ? sel.name_th : sel.name_en} — ${tc.health[sel.status]}` : ""}
      </span>
    </OperationsLayout>
  );
}
