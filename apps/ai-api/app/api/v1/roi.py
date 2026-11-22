"""ROI & Value Simulator. Owner: backend-b. Illustrative only (SPEC rule 5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1._contract import STD_RESPONSES, contract
from app.db.session import get_db
from app.deps import require_permission
from app.schemas.common import ReportDocument
from app.schemas.roi import (
    PrintableDocument,
    RoiDefaultsResponse,
    RoiExportRequest,
    RoiInputs,
    RoiResponse,
    SensitivityRequest,
    SensitivityResponse,
)
from app.services import roi as svc
from app.services.demo_context import DemoContext
from app.services.rbac import Permission as P

OWNER = "backend-b"
router = APIRouter(prefix="/roi", tags=["roi"], responses=STD_RESPONSES)
_calc = require_permission(P.roi_calculate)


@router.get("/defaults", response_model=RoiDefaultsResponse, summary="Default inputs (from synthetic baseline) + tagged assumptions",
            openapi_extra=contract(P.roi_calculate, OWNER, "DML-085", status="implemented"))
def roi_defaults(ctx: DemoContext = Depends(_calc), db: Session = Depends(get_db)):
    return svc.defaults(db, ctx)


@router.post("/calculate", response_model=RoiResponse, summary="Baseline / Conservative / Expected / Optimistic cases",
             openapi_extra=contract(P.roi_calculate, OWNER, "DML-086", status="implemented"))
def roi_calculate(body: RoiInputs, ctx: DemoContext = Depends(_calc), db: Session = Depends(get_db)):
    return svc.calculate(ctx, body)


@router.post("/sensitivity", response_model=SensitivityResponse, summary="Tornado sensitivity of net benefit",
             openapi_extra=contract(P.roi_calculate, OWNER, "DML-088", status="implemented"))
def roi_sensitivity(body: SensitivityRequest, ctx: DemoContext = Depends(_calc), db: Session = Depends(get_db)):
    return svc.sensitivity(ctx, body)


@router.post("/export", response_model=ReportDocument, summary="Export ROI report (markdown/csv/json) with disclaimer",
             openapi_extra=contract(P.report_export, OWNER, "DML-090", status="implemented"))
def roi_export(body: RoiExportRequest, ctx: DemoContext = Depends(require_permission(P.report_export)), db: Session = Depends(get_db)):
    return svc.export(ctx, body)


@router.post("/export/printable", response_model=PrintableDocument, summary="Printable HTML ROI report (render in an iframe, print to PDF) with the disclaimer",
             openapi_extra=contract(P.report_export, OWNER, "DML-090", status="implemented"))
def roi_export_printable(body: RoiExportRequest, ctx: DemoContext = Depends(require_permission(P.report_export))):
    return svc.printable_document(ctx, body.inputs)
