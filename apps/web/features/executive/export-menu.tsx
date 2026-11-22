"use client";

import { useState } from "react";
import { Download, FileCode, FileSpreadsheet, Printer } from "lucide-react";
import { apiGet } from "@/lib/api/client";
import { useDemo } from "@/lib/demo/context";
import { useT } from "@/lib/i18n/client";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { toast } from "@/components/ui/toast";
import messages from "./executive.i18n";
import { downloadText, reserveWindow, showHtmlIn } from "./shared/download";

type ReportType = "executive" | "production";

/** Export via the backend report endpoints (DML-042): print-ready HTML and CSV / Markdown documents. */
export function ExportMenu({ reportType = "executive" }: { reportType?: ReportType }) {
  const t = useT(messages);
  const demo = useDemo();
  const [busy, setBusy] = useState(false);
  const period = demo.period === "custom" ? "today" : demo.period;

  async function run(kind: "html" | "csv" | "markdown") {
    const win = kind === "html" ? reserveWindow() : null;
    setBusy(true);
    const id = toast.loading(t.export.working);
    try {
      if (kind === "html") {
        const doc = await apiGet(
          "/api/v1/reports/{report_type}/html",
          { params: { path: { report_type: reportType }, query: { period } } },
          demo.request,
        );
        if (!showHtmlIn(win, doc.html)) {
          toast.message(t.export.popupBlocked);
          downloadText(doc.filename, doc.html, "html");
        }
      } else {
        const doc = await apiGet(
          "/api/v1/reports/{report_type}",
          { params: { path: { report_type: reportType }, query: { period, format: kind } } },
          demo.request,
        );
        downloadText(doc.filename, doc.content, kind);
      }
      toast.success(t.export.done, { id });
    } catch (e) {
      win?.close();
      toast.error(t.export.failed, { id, description: e instanceof Error ? e.message : undefined });
    } finally {
      setBusy(false);
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" disabled={busy}>
          <Download aria-hidden /> {t.export.label}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onSelect={() => void run("html")}>
          <Printer aria-hidden /> {t.export.html}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => void run("csv")}>
          <FileSpreadsheet aria-hidden /> {t.export.csv}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => void run("markdown")}>
          <FileCode aria-hidden /> {t.export.markdown}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
