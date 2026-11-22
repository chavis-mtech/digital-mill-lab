"use client";

import type { ReactNode } from "react";
import { Plus } from "lucide-react";
import { ApiRequestError } from "@/lib/api/errors";
import { FX_ACTUAL, FX_ASSUMPTIONS, FX_BAND, FX_BASELINE, FX_EVIDENCE, FX_FORMULAS, FX_HEAT, FX_KPIS, FX_ROWS, FX_SERIES_A, FX_SERIES_B, FX_SERIES_C, type FxRow } from "@/fixtures/ui-kit";
import { AppShell } from "@/components/shell/app-shell";
import { OperationsLayout } from "@/components/layouts/layouts";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ProvenanceBadge } from "@/components/demo/provenance-badge";
import { StatusChip, StatusLegend } from "@/components/demo/status-chip";
import { AlertBadge, SeverityPill } from "@/components/demo/severity";
import { Disclaimer } from "@/components/demo/disclaimer";
import { KpiCard } from "@/components/data/kpi-card";
import { DataTable, type DataTableColumn } from "@/components/data/data-table";
import { EvidencePanel } from "@/components/data/evidence-panel";
import { FormulaPanel } from "@/components/data/formula-panel";
import { ConfirmDialog } from "@/components/data/confirm-dialog";
import { AreaBandChart, BarChart, GaugeChart, HeatmapChart, Sparkline, TimeSeriesChart } from "@/components/charts/charts";
import { EmptyState, ErrorState, LoadingState, NotImplementedState } from "@/components/states/states";
import { toast } from "@/components/ui/toast";

const COLUMNS: DataTableColumn<FxRow>[] = [
  { id: "id", header: "ID", value: (r) => r.id, className: "font-mono text-xs" },
  { id: "name", header: "Name", value: (r) => r.name },
  { id: "area", header: "Area", value: (r) => r.area },
  { id: "state", header: "Health", value: (r) => r.state, cell: (r) => <AlertBadge state={r.state} /> },
  { id: "severity", header: "Severity", value: (r) => r.severity, cell: (r) => <SeverityPill severity={r.severity} /> },
  { id: "value", header: "Value", value: (r) => r.value, align: "right" },
];

const STUB = new ApiRequestError({ status: 501, code: "not_implemented", message: "stub", details: { owner: "backend-a", task: "DML-036" }, path: "/api/v1/x" });
const DOWN = new ApiRequestError({ status: 0, code: "network_error", message: "down", path: "/api/v1/x" });
const FORBID = new ApiRequestError({ status: 403, code: "forbidden", message: "nope", path: "/api/v1/x" });
const FAIL = new ApiRequestError({ status: 500, code: "internal_error", message: "Unexpected server error (fixture)", requestId: "req-123", path: "/api/v1/x" });

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-xs font-semibold tracking-[0.08em] text-muted-foreground uppercase">{title}</h2>
      {children}
    </section>
  );
}

export function UiKit() {
  return (
    <AppShell area="demo">
      <OperationsLayout title="UI kit (internal)" description="Every shared component with FIXTURE data (fixtures/ui-kit.ts) for visual QA. Not demo data." feature="design_system">
        <Block title="Buttons & badges">
          <div className="flex flex-wrap items-center gap-2">
            <Button>Primary</Button>
            <Button variant="accent">Accent</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="destructive">Destructive</Button>
            <Button size="sm">Small</Button>
            <Button size="icon" aria-label="Add">
              <Plus aria-hidden />
            </Button>
          </div>
          <div className="flex flex-wrap gap-2">
            {(["neutral", "accent", "success", "warning", "critical", "maintenance", "info", "outline"] as const).map((t) => (
              <Badge key={t} tone={t}>
                {t}
              </Badge>
            ))}
          </div>
        </Block>

        <Block title="Provenance · status · severity · health">
          <div className="flex flex-wrap items-center gap-2">
            <ProvenanceBadge kind="synthetic_actual" />
            <ProvenanceBadge kind="forecast" />
            <ProvenanceBadge kind="what_if" />
            <ProvenanceBadge provenance={FX_KPIS[2]!.provenance} compact />
          </div>
          <StatusLegend />
          <div className="flex flex-wrap items-center gap-2">
            <StatusChip feature="executive_control_tower" />
            <StatusChip feature="cv_grading" />
            {(["info", "low", "medium", "high", "critical"] as const).map((s) => (
              <SeverityPill key={s} severity={s} />
            ))}
            {(["normal", "warning", "critical", "maintenance_required"] as const).map((s) => (
              <AlertBadge key={s} state={s} count={s === "critical" ? 2 : undefined} />
            ))}
          </div>
        </Block>

        <Block title="KPI cards">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {FX_KPIS.map((k, i) => (
              <KpiCard key={k.key} kpi={k} sparkline={i < 3 ? FX_SERIES_A.points : undefined} feature={i === 0 ? "executive_control_tower" : undefined} href={i === 1 ? "/ui-kit" : undefined} />
            ))}
            <KpiCard loading />
            <KpiCard error={STUB} />
            <div className="flex items-center gap-3 rounded-xl border border-border bg-surface p-4">
              <Sparkline points={FX_SERIES_A.points} label="Sparkline fixture" />
              <Sparkline points={FX_SERIES_B.points} kind="forecast" />
              <Sparkline points={FX_SERIES_C.points} kind="what_if" />
            </div>
          </div>
        </Block>

        <Block title="Charts">
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <Card>
              <CardContent className="pt-4">
                <TimeSeriesChart
                  title="TimeSeries with anomaly, normal band, threshold"
                  description="Three provenance kinds (solid / dashed / dotted)"
                  series={[FX_SERIES_A, FX_SERIES_B, FX_SERIES_C]}
                  anomalies={[{ t: FX_SERIES_A.points[25]!.t, label: "fixture anomaly", severity: "high" }]}
                  normalRange={{ low: 19.5, high: 20.8 }}
                  thresholds={[{ value: 19, label: "threshold", tone: "critical" }]}
                  timeStyle="date"
                />
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <AreaBandChart title="Forecast with uncertainty band" band={FX_BAND} actual={FX_ACTUAL} baseline={FX_BASELINE} />
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <BarChart
                  title="Bar chart (grouped)"
                  categories={["Reception", "Sterilisation", "Pressing", "Clarification", "Boiler"]}
                  series={[
                    { key: "x", label: "Baseline (fixture)", values: [4, 6, 9, 3, 5] },
                    { key: "y", label: "What-if (fixture)", values: [3, 5, 6, 3, 4], kind: "what_if" },
                  ]}
                  unit="h"
                />
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <BarChart title="Bar chart (horizontal)" horizontal categories={["Bearing", "Lubrication", "Alignment", "Sensor check"]} series={[{ key: "z", label: "Count", values: [7, 5, 3, 2] }]} />
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <HeatmapChart title="Heatmap (sequential)" x={FX_HEAT.x} y={FX_HEAT.y} values={FX_HEAT.values} unit="trucks" />
              </CardContent>
            </Card>
            <Card>
              <CardContent className="grid gap-4 pt-4 sm:grid-cols-2">
                <GaugeChart
                  title="Gauge"
                  value={72}
                  unit="%"
                  bands={[
                    { to: 60, tone: "critical" },
                    { to: 80, tone: "warning" },
                    { to: 100, tone: "success" },
                  ]}
                />
                <TimeSeriesChart title="Loading state" series={undefined} loading height={180} />
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <TimeSeriesChart title="Chart in 501 state" series={undefined} error={STUB} height={180} />
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <TimeSeriesChart title="Chart empty state" series={[]} height={180} />
              </CardContent>
            </Card>
          </div>
        </Block>

        <Block title="Data table">
          <Card>
            <CardContent className="pt-4">
              <DataTable data={FX_ROWS} columns={COLUMNS} caption="Fixture equipment table" exportName="ui-kit-fixture" pageSize={10} />
            </CardContent>
          </Card>
          <div className="grid gap-4 lg:grid-cols-2">
            <DataTable data={undefined} loading columns={COLUMNS} caption="Loading table" />
            <DataTable data={undefined} error={STUB} columns={COLUMNS} caption="501 table" />
          </div>
        </Block>

        <Block title="Evidence · formula · disclaimers">
          <div className="grid gap-4 lg:grid-cols-2">
            <EvidencePanel evidence={FX_EVIDENCE} factors={["Fixture factor one", "Fixture factor two"]} assumptions={FX_ASSUMPTIONS} />
            <div className="flex flex-col gap-4">
              <FormulaPanel formulas={FX_FORMULAS} />
              <Disclaimer kind="roi" variant="block" />
              <Disclaimer kind="riskScore" />
              <Disclaimer kind="simulatedLive" />
            </div>
          </div>
        </Block>

        <Block title="States">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <LoadingState />
            <EmptyState />
            <NotImplementedState owner="backend-b" task="DML-056" />
            <ErrorState error={DOWN} onRetry={() => toast("retry")} />
            <ErrorState error={FORBID} />
            <ErrorState error={FAIL} onRetry={() => toast("retry")} />
          </div>
        </Block>

        <Block title="Confirm dialog · toast">
          <Card>
            <CardHeader>
              <CardTitle>Record-changing action</CardTitle>
              <CardDescription>Confirmation is mandatory before modifying records.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <ConfirmDialog
                trigger={<Button>Create work order…</Button>}
                title="Create work order?"
                description="A fixture work order would be created in your sandbox session."
                details={<p>Equipment: Press 1 · Priority: high</p>}
                onConfirm={async () => {
                  await new Promise((r) => setTimeout(r, 600));
                  toast.success("Fixture confirmed (nothing was sent)");
                }}
              />
              <Button variant="outline" onClick={() => toast("Plain toast")}>
                Toast
              </Button>
              <Button variant="outline" onClick={() => toast.error("Error toast")}>
                Error toast
              </Button>
            </CardContent>
          </Card>
        </Block>
      </OperationsLayout>
    </AppShell>
  );
}
