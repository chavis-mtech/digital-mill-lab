"""Demo knowledge base - newly authored SAMPLE documents (owner: copilot)."""

from __future__ import annotations

from app.schemas.common import ApiModel


class KbDocumentSummary(ApiModel):
    slug: str
    lang: str
    title: str
    doc_type: str
    version: str
    chunk_count: int = 0
    data_kind: str = "sample_document"


class KbDocumentListResponse(ApiModel):
    items: list[KbDocumentSummary]
    notice: str = "Sample documents authored for this demo; clearly separate from any real company documents."


class KbDocumentDetail(KbDocumentSummary):
    body_md: str
