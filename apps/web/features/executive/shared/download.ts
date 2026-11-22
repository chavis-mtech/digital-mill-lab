/**
 * Browser-side file helpers for API-generated reports (frontend-exec). The report bodies are produced by the
 * API (ReportDocument / HtmlReport) — these helpers only hand them to the browser.
 */

const MIME: Record<string, string> = {
  csv: "text/csv;charset=utf-8",
  markdown: "text/markdown;charset=utf-8",
  json: "application/json;charset=utf-8",
  html: "text/html;charset=utf-8",
};

export function mimeFor(format: string): string {
  return MIME[format] ?? "text/plain;charset=utf-8";
}

/** Save text as a file. CSV gets a UTF-8 BOM so spreadsheet tools open Thai text correctly. */
export function downloadText(filename: string, content: string, format: string) {
  const parts: BlobPart[] = format === "csv" ? ["﻿", content] : [content];
  const blob = new Blob(parts, { type: mimeFor(format) });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

/**
 * Open a blank tab synchronously inside the click handler (so popup blockers allow it), then fill it with
 * API-rendered HTML once the request resolves via `showHtmlIn`. Returns null when the popup was blocked.
 */
export function reserveWindow(): Window | null {
  return window.open("about:blank", "_blank");
}

/** Put API-generated HTML into a reserved tab (user prints to PDF from there). False = no tab available. */
export function showHtmlIn(win: Window | null, html: string): boolean {
  if (!win || win.closed) return false;
  const blob = new Blob([html], { type: MIME.html });
  const url = URL.createObjectURL(blob);
  win.location.href = url;
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
  return true;
}

/** Narrow an untyped printable payload (`POST /roi/export/printable` has no response model in the contract). */
export function readPrintable(data: unknown): { html: string; filename: string } | null {
  if (typeof data !== "object" || data === null) return null;
  const d = data as Record<string, unknown>;
  if (typeof d.html !== "string") return null;
  return { html: d.html, filename: typeof d.filename === "string" ? d.filename : "report.html" };
}
