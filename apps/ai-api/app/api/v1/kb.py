"""Demo knowledge base (sample documents for RAG). Owner: copilot."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1._contract import STD_RESPONSES, contract
from app.copilot.kb import SAMPLE_NOTICE, ensure_ingested
from app.db.session import get_db
from app.deps import require_permission
from app.errors import ApiError
from app.models.platform import KbChunk, KbDocument
from app.schemas.kb import KbDocumentDetail, KbDocumentListResponse
from app.services.demo_context import DemoContext
from app.services.rbac import Permission as P

OWNER = "copilot"
router = APIRouter(prefix="/kb", tags=["kb"], responses=STD_RESPONSES)
_read = require_permission(P.read_kb)


def _summary(d: KbDocument, n: int) -> dict:
    return {"slug": d.slug, "lang": d.lang, "title": d.title, "doc_type": d.doc_type, "version": d.version, "chunk_count": n, "data_kind": "sample_document"}


@router.get("/documents", response_model=KbDocumentListResponse, summary="List sample KB documents",
            openapi_extra=contract(P.read_kb, OWNER, "DML-073", status="implemented"))
def list_documents(lang: str | None = Query(None, pattern="^(th|en)$"), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    ensure_ingested(db)
    counts = dict(db.execute(select(KbChunk.document_id, func.count(KbChunk.id)).group_by(KbChunk.document_id)).all())
    q = select(KbDocument).order_by(KbDocument.slug)
    if lang:
        q = q.where(KbDocument.lang == lang)
    return {"items": [_summary(d, counts.get(d.id, 0)) for d in db.execute(q).scalars()], "notice": SAMPLE_NOTICE}


@router.get("/documents/{slug}", response_model=KbDocumentDetail, summary="Full sample document (markdown)",
            openapi_extra=contract(P.read_kb, OWNER, "DML-073", status="implemented"))
def get_document(
    slug: str = Path(max_length=80, pattern="^[a-z0-9-]+$"),
    lang: str = Query("en", pattern="^(th|en)$"),
    ctx: DemoContext = Depends(_read),
    db: Session = Depends(get_db),
):
    ensure_ingested(db)
    d = db.execute(select(KbDocument).where(KbDocument.slug == slug, KbDocument.lang == lang)).scalar_one_or_none()
    if d is None:  # documents are bilingual (en+th) in one file, stored under lang=en
        d = db.execute(select(KbDocument).where(KbDocument.slug == slug)).scalars().first()
    if d is None:
        raise ApiError(404, "not_found", "Unknown sample document.")
    n = db.execute(select(func.count(KbChunk.id)).where(KbChunk.document_id == d.id)).scalar_one()
    body = f"> {SAMPLE_NOTICE}\n\n{d.body_md}"
    return {**_summary(d, n), "body_md": body}
