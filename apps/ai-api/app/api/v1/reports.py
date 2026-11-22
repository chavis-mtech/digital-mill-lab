"""Report export (executive, production, maintenance, logistics, energy). Owner: backend-a.

ROI export: POST /roi/export. Traceability report: GET /traceability/lots/{id}/report.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.v1._contract import STD_RESPONSES, contract
from app.db.session import get_db
from app.deps import require_permission
from app.errors import bad_request
from app.schemas.common import ExportFormat, Period, ReportDocument
from app.schemas.reports import HtmlReport
from app.services import kpi_reports
from app.services.demo_context import DemoContext
from app.services.rbac import Permission as P

OWNER = "backend-a"
router = APIRouter(prefix="/reports", tags=["reports"], responses=STD_RESPONSES)


@router.get("/{report_type}", response_model=ReportDocument, summary="Export a report as markdown / csv / json",
            openapi_extra=contract(P.report_export, OWNER, "DML-042", status="implemented"))
def export_report(
    report_type: str = Path(pattern="^(executive|production|maintenance|logistics|energy)$"),
    format: ExportFormat = Query(ExportFormat.markdown),
    period: Period = Query(Period.today),
    ctx: DemoContext = Depends(require_permission(P.report_export)),
    db: Session = Depends(get_db),
):
    if period == Period.custom:
        bad_request("invalid_period", "Use today, 7d or 30d")
    return kpi_reports.document(db, ctx, report_type, format.value, period)


@router.get("/{report_type}/html", response_model=HtmlReport, summary="Print-ready HTML report (JSON-wrapped; raw=true returns text/html)",
            openapi_extra=contract(P.report_export, OWNER, "DML-042", status="implemented"))
def export_report_html(
    report_type: str = Path(pattern="^(executive|production|maintenance|logistics|energy)$"),
    period: Period = Query(Period.today),
    raw: bool = Query(False, description="true -> respond with text/html directly (open in a browser tab and print)"),
    ctx: DemoContext = Depends(require_permission(P.report_export)),
    db: Session = Depends(get_db),
):
    if period == Period.custom:
        bad_request("invalid_period", "Use today, 7d or 30d")
    doc = kpi_reports.html_document(db, ctx, report_type, period)
    if raw:
        return HTMLResponse(doc["html"])
    return doc
