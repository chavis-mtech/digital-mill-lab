"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useApiQuery } from "@/lib/api/hooks";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatDate, formatValue } from "@/lib/format";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { SeverityPill } from "./sev";
import { ProvenanceBadge } from "@/components/demo/provenance-badge";
import { EvidencePanel } from "@/components/data/evidence-panel";
import { FormulaPanel } from "@/features/executive/shared/formulas";
import { QueryState } from "@/components/states/states";
import common from "@/messages/common.i18n";
import messages from "../executive.i18n";
import { alertHref, alertSourceKind, teamKey } from "./links";
import { ApiText } from "./section";

/** Alert detail drawer (GET /alerts/{id}) reused by the control tower and the process twin. */
export function AlertDetailDialog({ alertId, onOpenChange }: { alertId: number | null; onOpenChange: (open: boolean) => void }) {
  const t = useT(messages);
  const tc = useT(common);
  const { locale } = useLocale();
  const q = useApiQuery(
    "/api/v1/alerts/{alert_id}",
    { params: { path: { alert_id: alertId ?? 0 } } },
    { enabled: alertId !== null },
  );
  return (
    <Dialog open={alertId !== null} onOpenChange={onOpenChange}>
      <DialogContent side="right" className="w-[min(34rem,94vw)] overflow-y-auto p-5" closeLabel={tc.common.close}>
        <DialogTitle className="pr-8">{t.alerts.detail}</DialogTitle>
        <DialogDescription className="sr-only">{t.alerts.notDiagnosis}</DialogDescription>
        <QueryState query={q}>
          {(a) => (
            <div className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <div className="flex flex-wrap items-center gap-1.5">
                  <SeverityPill severity={a.severity} />
                  <Badge tone="outline">{t.alerts.status[a.status]}</Badge>
                  <Badge tone="neutral">{alertSourceKind(a.source) === "rule" ? t.alerts.sourceRule : t.alerts.sourceMl}</Badge>
                  <span className="font-mono text-2xs text-subtle-foreground">{a.code}</span>
                </div>
                <p className="text-sm font-medium">
                  <ApiText>{a.title}</ApiText>
                </p>
                <p className="text-xs text-muted-foreground">
                  <ApiText>{a.message}</ApiText>
                </p>
                <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
                  <dt className="text-muted-foreground">{t.alerts.raised}</dt>
                  <dd>{formatDate(a.raised_at, locale, "datetime")}</dd>
                  <dt className="text-muted-foreground">{t.alerts.team}</dt>
                  <dd>{t.team[teamKey(a.suggested_team)]}</dd>
                  {a.priority_score != null ? (
                    <>
                      <dt className="text-muted-foreground">{t.alerts.score}</dt>
                      <dd className="tabular">{formatValue(a.priority_score, null, locale, { digits: 1 })} / 100</dd>
                    </>
                  ) : null}
                </dl>
              </div>
              <EvidencePanel evidence={a.evidence} />
              {a.impact ? (
                <div className="flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold">{t.alerts.impact}</h3>
                    <ProvenanceBadge provenance={a.impact.provenance} />
                  </div>
                  {a.impact.formulas.length ? <FormulaPanel formulas={a.impact.formulas} /> : null}
                  {a.impact.assumptions_note ? (
                    <p className="text-2xs text-muted-foreground">
                      <ApiText>{a.impact.assumptions_note}</ApiText>
                    </p>
                  ) : null}
                </div>
              ) : null}
              <p className="text-2xs text-muted-foreground">{t.alerts.notDiagnosis}</p>
              <Button asChild variant="outline" size="sm" className="self-start">
                <Link href={alertHref(a)}>
                  {t.alerts.openModule} <ArrowRight aria-hidden />
                </Link>
              </Button>
            </div>
          )}
        </QueryState>
      </DialogContent>
    </Dialog>
  );
}
