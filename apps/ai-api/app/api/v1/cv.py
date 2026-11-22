"""Computer Vision FFB grading - RESEARCH PROTOTYPE (SPEC 4.G, P2). Owner: ml.

Uploads must go through app.security.uploads.read_validated_upload (size/type/magic-byte checks).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.v1._contract import STD_RESPONSES, contract
from app.config import Settings, get_settings
from app.deps import require_permission
from app.ml import cv as cvp
from app.schemas.common import ErrorEnvelope
from app.schemas.cv import CvProtocolResponse, CvPrototypeResponse
from app.security.uploads import read_validated_upload
from app.services.demo_context import DemoContext
from app.services.rbac import Permission as P

OWNER = "ml"
router = APIRouter(
    prefix="/cv",
    tags=["cv-prototype"],
    responses={**STD_RESPONSES, 413: {"model": ErrorEnvelope}, 415: {"model": ErrorEnvelope}},
)


@router.post("/ffb-assessment", response_model=CvPrototypeResponse, summary="PROTOTYPE: upload an FFB image for a non-validated assessment",
             openapi_extra=contract(P.cv_upload, OWNER, "P2-CV", status="prototype"))
async def ffb_assessment(file: UploadFile = File(...), ctx: DemoContext = Depends(require_permission(P.cv_upload)),
                         settings: Settings = Depends(get_settings)):
    up = await read_validated_upload(file, settings)
    res = cvp.assess(up.content_type, up.data)
    return {"filename": up.filename, "content_type": up.content_type, "size_bytes": up.size, **res}


@router.get("/protocol", response_model=CvProtocolResponse, summary="Dataset / camera / labelling / validation protocol for a real grader",
            openapi_extra=contract(P.read_ai, OWNER, "P2-CV", status="prototype"))
def cv_protocol(ctx: DemoContext = Depends(require_permission(P.read_ai))):
    return cvp.protocol()
