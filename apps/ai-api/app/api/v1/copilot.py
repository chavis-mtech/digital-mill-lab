"""Industrial Operations Copilot (SPEC 4.F). Owner: copilot. Read-only; per-role tool permissions (app/copilot/**)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Path, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1._contract import STD_RESPONSES, contract
from app.config import Settings, get_settings
from app.copilot import engine, kb
from app.copilot.llm import provider_from_settings
from app.copilot.tools import TOOLS
from app.db.session import get_db
from app.deps import require_permission
from app.errors import ApiError
from app.models.platform import CopilotMessage, CopilotSession
from app.schemas.copilot import (
    ChatRequest,
    ChatResponse,
    CopilotSessionDetail,
    CopilotSessionListResponse,
    SourceDocumentResponse,
    ToolListResponse,
)
from app.services.demo_context import DemoContext
from app.services.rbac import Permission as P
from app.services.rbac import has_permission

OWNER = "copilot"
router = APIRouter(prefix="/copilot", tags=["copilot"], responses=STD_RESPONSES)
_chat = require_permission(P.copilot_chat)


def _settings(request: Request) -> Settings:
    return getattr(request.app.state, "settings", None) or get_settings()


@router.post("/chat", response_model=ChatResponse, summary="Ask a question; answer grounded in tool results + cited sample docs",
             openapi_extra=contract(P.copilot_chat, OWNER, "DML-072", status="implemented"))
def chat(body: ChatRequest, request: Request, ctx: DemoContext = Depends(_chat), db: Session = Depends(get_db)):
    client = request.client.host if request.client else None
    return engine.answer(db, ctx, body.message, lang=body.lang, copilot_session_id=body.copilot_session_id, settings=_settings(request), client_key=client)


@router.get("/tools", response_model=ToolListResponse, summary="Tool catalog with per-role allow flags",
            openapi_extra=contract(P.copilot_chat, OWNER, "DML-071", status="implemented"))
def list_tools(request: Request, ctx: DemoContext = Depends(_chat)):
    mode = "llm" if provider_from_settings(_settings(request)) is not None else "deterministic"
    tools = [{"name": t.name, "description": f"{t.description} (max rows {t.max_rows}; units: {t.units})", "parameters_schema": t.schema(),
              "permission": t.permission.value, "allowed_for_role": has_permission(ctx.role, t.permission), "read_only": t.read_only}
             for t in TOOLS.values()]  # fmt: skip
    return {"role": ctx.role.value, "mode": mode, "tools": tools}


def _calls(raw: str | None) -> list[dict]:
    if not raw:
        return []
    d = json.loads(raw)
    return d.get("tool_calls", []) if isinstance(d, dict) else d


def _own(db: Session, ctx: DemoContext, conv_id: str) -> CopilotSession:
    conv = db.get(CopilotSession, conv_id)
    if conv is None or not ctx.session_id or conv.session_id != ctx.session_id:
        raise ApiError(404, "not_found", "Conversation not found in this demo session.")
    return conv


@router.get("/sessions", response_model=CopilotSessionListResponse, summary="Copilot conversations in this demo session",
            openapi_extra=contract(P.copilot_chat, OWNER, "DML-077", status="implemented"))
def list_sessions(ctx: DemoContext = Depends(_chat), db: Session = Depends(get_db)):
    if not ctx.session_id:
        return {"items": []}
    counts = dict(db.execute(select(CopilotMessage.copilot_session_id, func.count(CopilotMessage.id)).where(CopilotMessage.session_id == ctx.session_id)
                             .group_by(CopilotMessage.copilot_session_id)).all())  # fmt: skip
    rows = db.execute(select(CopilotSession).where(CopilotSession.session_id == ctx.session_id).order_by(CopilotSession.created_at.desc()).limit(100)).scalars()
    return {"items": [{"id": c.id, "title": c.title, "role": c.role, "mode": c.mode, "created_at": c.created_at, "message_count": counts.get(c.id, 0)} for c in rows]}


@router.get("/sessions/{copilot_session_id}", response_model=CopilotSessionDetail, summary="Conversation with messages, tool calls, citations",
            openapi_extra=contract(P.copilot_chat, OWNER, "DML-077", status="implemented"))
def get_session(copilot_session_id: str = Path(max_length=36), ctx: DemoContext = Depends(_chat), db: Session = Depends(get_db)):
    conv = _own(db, ctx, copilot_session_id)
    msgs = db.execute(select(CopilotMessage).where(CopilotMessage.copilot_session_id == conv.id).order_by(CopilotMessage.id)).scalars().all()
    return {"id": conv.id, "title": conv.title, "role": conv.role, "mode": conv.mode, "created_at": conv.created_at, "message_count": len(msgs),
            "messages": [{"id": m.id, "sender": m.sender, "content": m.content, "intent": m.intent, "tool_calls": _calls(m.tool_calls_json),
                          "citations": json.loads(m.citations_json) if m.citations_json else [], "created_at": m.created_at} for m in msgs]}  # fmt: skip


@router.get("/sources/{ref}", response_model=SourceDocumentResponse, summary="Open a cited source chunk (sample document)",
            openapi_extra=contract(P.read_kb, OWNER, "DML-077", status="implemented"))
def get_source(ref: str = Path(max_length=120, pattern=r"^[A-Za-z0-9_:#.\-]+$"), ctx: DemoContext = Depends(require_permission(P.read_kb)), db: Session = Depends(get_db)):
    ch = kb.get_chunk(db, ref)
    if ch is None:
        raise ApiError(404, "not_found", "Unknown source reference (expected kb:<document-slug>#<chunk-index>).")
    return {**ch, "data_kind": "sample_document", "notice": kb.SAMPLE_NOTICE}
