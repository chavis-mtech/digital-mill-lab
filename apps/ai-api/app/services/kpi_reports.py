"""Report export (DML-042): markdown / csv / json via GET /reports/{type}, plus a print-ready HTML page via
GET /reports/{type}/html (JSON-wrapped; ?raw=true serves text/html for the browser "Print -> Save as PDF"). PDF rendering on the server was deliberately NOT built
(would add a native dependency to the image for no extra information). Owner: backend-a.

Every figure is taken from the same services the screens use (no separate numbers), with provenance kind + source
per row and the product disclaimers.
"""

from __future__ import annotations

import csv
import html
import io
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.schemas.common import Period
from app.services import energy, kpi, kpi_alerts, kpi_insights, logistics, production
from app.services.demo_context import DemoContext
from app.services.kpi_health import equipment_health

DISCLAIMERS = [
    {"key": "independent_concept", "text_en": "Independent portfolio / concept demo. Not an official system of any company and not affiliated with or endorsed by any company.",
     "text_th": "โครงการแนวคิดอิสระเพื่อการนำเสนอผลงาน ไม่ใช่ระบบทางการของบริษัทใด ๆ"},
    {"key": "synthetic_data", "text_en": "All plant, supplier and production data are synthetic (deterministically generated). No internal company data is used.",
     "text_th": "ข้อมูลทั้งหมดเป็นข้อมูลสังเคราะห์ ไม่มีการใช้ข้อมูลภายในของบริษัทใด"},
    {"key": "advisory_ai", "text_en": "Insights and estimates are advisory; costs and impacts are illustrative, not any company's financial results.", "text_th": None},
]  # fmt: skip
TITLES = {
    "executive": "Executive Control Tower report",
    "production": "Production report",
    "maintenance": "Maintenance status report",
    "logistics": "Logistics & weighbridge report",
    "energy": "Energy report",
}


def _kpi_rows(section: str, kpis: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"section": section, "key": k["key"], "label": k["label"], "value": k["value"], "unit": k["unit"], "previous": k.get("previous"),
             "delta": k.get("delta"), "status": k.get("status"), "provenance_kind": k["provenance"]["kind"], "source": k["provenance"]["source"]}
            for k in kpis]  # fmt: skip


def build(db: Session, ctx: DemoContext, report_type: str, period: Period) -> dict[str, Any]:
    """Structured report: sections of KPI rows + text items."""
    sections: list[dict[str, Any]] = []
    if report_type == "executive":
        k = kpi.executive_kpis(db, ctx, period)
        sections.append({"title": "Control-tower KPIs (current vs previous period)", "rows": _kpi_rows("kpis", k["kpis"])})
        ins = kpi_insights.insights(db, ctx)
        sections.append({"title": "AI insight summary (deterministic rules)", "text": [ins["summary"]] + [f"[{i['severity']}] {i['headline']} - {i['detail']}" for i in ins["items"]]})
        cards = kpi.impact_cards(db, ctx, period)
        sections.append({"title": "Business impact estimates (what_if)", "rows": [
            {"section": "impact", "key": c["key"], "label": c["label"], "value": c["value"], "unit": c["unit"], "previous": None, "delta": None, "status": None,
             "provenance_kind": "what_if", "source": c["formula"]["expression"]} for c in cards]})  # fmt: skip
        b = kpi_insights.bottlenecks(db, ctx, period)
        sections.append({"title": "Bottleneck overview", "text": [f"{s['stage_code']}: utilisation {s['utilisation_pct']}%{' (BOTTLENECK)' if s['is_bottleneck'] else ''}" for s in b["stages"]]})
    elif report_type == "production":
        s = production.summary(db, ctx, None)
        sections.append({"title": f"Business day {s['business_date']} (up to as_of)", "rows": _kpi_rows("production", s["kpis"])})
        p = Period.last_7d if period == Period.today else period
        losses = production.losses(db, ctx, p)
        sections.append({"title": f"Oil losses ({p.value}) vs industry-practice reference", "text": [
            f"{c['label']}: {c['pct_of_ffb']}% of FFB (reference {c['benchmark_pct']}%), {c['lost_cpo_t']} t oil" for c in losses["components"]]})  # fmt: skip
    elif report_type == "maintenance":
        health = equipment_health(db, ctx)
        counts: dict[str, int] = {}
        for h in health.values():
            counts[h["state"]] = counts.get(h["state"], 0) + 1
        sections.append({"title": "Equipment health (shared rule engine, maintenance_health.py)", "text": [f"{k}: {v}" for k, v in sorted(counts.items())]})
        al = kpi_alerts.list_alerts(db, ctx, module="maintenance", active_only=True, limit=50)
        sections.append({"title": "Active maintenance alerts", "text": [f"[{a['severity']}] {a['title']} (raised {a['raised_at']:%Y-%m-%d %H:%M} UTC)" for a in al["items"]] or ["none"]})
        k = kpi.executive_kpis(db, ctx, period)
        sections.append({"title": "Availability and downtime", "rows": _kpi_rows("maintenance", [x for x in k["kpis"] if x["key"] in ("equipment_availability_pct", "plant_downtime_h", "active_maintenance_alerts")])})
    elif report_type == "logistics":
        sections.append({"title": "Logistics KPIs", "rows": _kpi_rows("logistics", logistics.kpis(db, ctx, period)["kpis"])})
        q = logistics.queue_now(db, ctx)
        sections.append({"title": "Queue at as_of", "text": [f"Trucks waiting: {q['trucks_waiting']}, unloading: {q['trucks_unloading']}, max wait so far: {q['max_wait_min']} min"]})
    elif report_type == "energy":
        e = energy.summary(db, ctx, period)
        sections.append({"title": "Energy KPIs", "rows": _kpi_rows("energy", e["kpis"])})
        sections.append({"title": "Abnormal-consumption days (production-adjusted z-score)", "text": [
            f"{m['t']:%Y-%m-%d}: {m['actual_kwh']} kWh vs expected {m['expected_kwh']} (z {m['z_score']})" for m in e["abnormal_days"]] or ["none in the period"]})  # fmt: skip
    return {"report_type": report_type, "title": TITLES[report_type], "period": period.value, "as_of": ctx.as_of, "sections": sections}


def render(rep: dict[str, Any], fmt: str) -> str:
    rows = [r for s in rep["sections"] for r in s.get("rows", [])]
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["section", "key", "label", "value", "unit", "previous", "delta", "status", "provenance_kind", "source"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
        buf.write(f"# as_of,{rep['as_of'].isoformat()}\n# Synthetic demonstration data - not any company's data\n")
        return buf.getvalue()
    if fmt == "json":
        return json.dumps(rep, default=str, ensure_ascii=False, indent=2)
    lines = [f"# {rep['title']}", "", f"As of {rep['as_of']:%Y-%m-%d %H:%M} UTC - period {rep['period']} - **Synthetic Data**", ""]
    for s in rep["sections"]:
        lines += [f"## {s['title']}", ""]
        if s.get("rows"):
            lines += ["| KPI | Value | Unit | Previous | Delta | Status | Provenance |", "|---|---|---|---|---|---|---|"]
            lines += [f"| {r['label']} | {r['value']} | {r['unit']} | {r['previous']} | {r['delta']} | {r['status'] or ''} | {r['provenance_kind']} ({r['source']}) |" for r in s["rows"]]
        for t in s.get("text", []):
            lines.append(f"- {t}")
        lines.append("")
    lines += ["---", *[f"*{d['text_en']}*" for d in DISCLAIMERS]]
    return "\n".join(lines)


def render_html(rep: dict[str, Any]) -> str:
    e = html.escape
    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<title>{e(rep['title'])}</title><style>body{{font-family:system-ui,sans-serif;margin:24px;color:#111;background:#fff}}"
        "h1{font-size:20px}h2{font-size:15px;margin-top:20px;border-bottom:1px solid #ccc}table{border-collapse:collapse;width:100%;font-size:12px}"
        "td,th{border:1px solid #ddd;padding:4px 6px;text-align:left}.badge{display:inline-block;border:1px solid #b45309;color:#b45309;padding:1px 6px;"
        "border-radius:4px;font-size:11px}.foot{font-size:11px;color:#444;margin-top:24px}@media print{body{margin:10mm}}</style></head><body>",
        f"<h1>{e(rep['title'])}</h1><p><span class='badge'>Synthetic Data</span> As of {rep['as_of']:%Y-%m-%d %H:%M} UTC &middot; period {e(rep['period'])}</p>",
    ]
    for s in rep["sections"]:
        parts.append(f"<h2>{e(s['title'])}</h2>")
        if s.get("rows"):
            parts.append("<table><tr><th>KPI</th><th>Value</th><th>Unit</th><th>Previous</th><th>Delta</th><th>Status</th><th>Provenance</th></tr>")
            for r in s["rows"]:
                parts.append("<tr>" + "".join(f"<td>{e(str(r[k]) if r[k] is not None else '')}</td>" for k in ("label", "value", "unit", "previous", "delta", "status"))
                             + f"<td>{e(r['provenance_kind'])} - {e(str(r['source']))}</td></tr>")  # fmt: skip
            parts.append("</table>")
        if s.get("text"):
            parts.append("<ul>" + "".join(f"<li>{e(t)}</li>" for t in s["text"]) + "</ul>")
    parts.append("<div class='foot'>" + "".join(f"<p>{e(d['text_en'])}</p>" for d in DISCLAIMERS) + "</div></body></html>")
    return "".join(parts)


def document(db: Session, ctx: DemoContext, report_type: str, fmt: str, period: Period) -> dict[str, Any]:
    rep = build(db, ctx, report_type, period)
    ext = {"markdown": "md", "csv": "csv", "json": "json"}[fmt]
    return {
        "report_type": report_type, "title": rep["title"], "format": fmt, "generated_at": datetime.now(UTC), "as_of": ctx.as_of,
        "filename": f"pc-ii-{report_type}-{ctx.local_as_of:%Y%m%d-%H%M}.{ext}", "content": render(rep, fmt), "disclaimers": DISCLAIMERS,
    }  # fmt: skip


def html_document(db: Session, ctx: DemoContext, report_type: str, period: Period) -> dict[str, Any]:
    rep = build(db, ctx, report_type, period)
    return {"report_type": report_type, "title": rep["title"], "generated_at": datetime.now(UTC), "as_of": ctx.as_of,
            "filename": f"pc-ii-{report_type}-{ctx.local_as_of:%Y%m%d-%H%M}.html", "html": render_html(rep), "disclaimers": DISCLAIMERS}  # fmt: skip
