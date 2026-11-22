"""Platform tables: audit log, scenario runs, saved business scenarios, copilot sessions, KB, prices,
injected_events (ML ground truth - NEVER exposed through the public API).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, data_kind_column, session_id_column, utcnow
from app.models.enums import Role, ScenarioCode, enum_check
from app.models.readings import BigIntPK


class AuditLog(Base):
    """Append-only. Each row stores sha256(prev_hash + canonical row) -> tamper-evident hash chain.

    Never UPDATE or DELETE rows (except the whole session's rows on demo session reset, which is itself audited).
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    ts: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    session_id: Mapped[str | None] = session_id_column()
    role: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(64))  # simulated actor label, e.g. "demo:maintenance_engineer"
    action: Mapped[str] = mapped_column(String(64))  # e.g. work_order.create, work_order.transition
    entity_type: Mapped[str] = mapped_column(String(48))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    before_json: Mapped[str | None] = mapped_column(Text)
    after_json: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(64))
    demo_as_of: Mapped[datetime | None]
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)

    __table_args__ = (enum_check("role", Role), Index("ix_audit_logs_entity", "entity_type", "entity_id"))


class ScenarioRun(Base):
    """Named deterministic episode embedded in the single 120-day synthetic timeline (ADR-005, ADR-011)."""

    __tablename__ = "scenario_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name_en: Mapped[str] = mapped_column(String(120))
    name_th: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    start_ts: Mapped[datetime]
    end_ts: Mapped[datetime]
    focus_ts: Mapped[datetime]  # default as_of when the scenario is selected
    baseline_ts: Mapped[datetime | None]  # comparable "normal" moment for before/after views
    primary_stage_code: Mapped[str | None] = mapped_column(String(32))
    primary_equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"))
    expected_effects_json: Mapped[str | None] = mapped_column(Text)  # cross-module effects the UI should show
    seed: Mapped[int | None] = mapped_column(Integer)
    data_kind: Mapped[str] = data_kind_column("synthetic")

    __table_args__ = (
        enum_check("code", ScenarioCode),
        CheckConstraint("end_ts > start_ts", name="time_order"),
        CheckConstraint("focus_ts >= start_ts AND focus_ts <= end_ts", name="focus_in_window"),
    )


class InjectedEvent(Base):
    """Ground-truth labels of injected anomalies/episodes. Used ONLY by ML evaluation (app/ml). Never in API output."""

    __tablename__ = "injected_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    scenario_code: Mapped[str | None] = mapped_column(String(32))
    event_type: Mapped[str] = mapped_column(String(48))  # bearing_wear, steam_drop, ffb_quality_drop, queue_surge, ...
    domain: Mapped[str] = mapped_column(String(16))
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"))
    process_stage_id: Mapped[int | None] = mapped_column(ForeignKey("process_stages.id"))
    start_ts: Mapped[datetime]
    end_ts: Mapped[datetime]
    magnitude: Mapped[float | None] = mapped_column(Float)
    params_json: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        enum_check("scenario_code", ScenarioCode, nullable=True),
        CheckConstraint("domain IN ('production', 'equipment', 'energy', 'logistics', 'quality')", name="domain_enum"),
        CheckConstraint("end_ts >= start_ts", name="time_order"),
    )


class BusinessScenario(Base):
    """Saved what-if runs (production, maintenance impact, energy, ROI, queue). Session-scoped."""

    __tablename__ = "business_scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str | None] = session_id_column()
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(32))
    inputs_json: Mapped[str] = mapped_column(Text)
    outputs_json: Mapped[str] = mapped_column(Text)
    formula_version: Mapped[str | None] = mapped_column(String(16))
    demo_as_of: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    data_kind: Mapped[str] = data_kind_column("what_if")

    __table_args__ = (
        CheckConstraint("kind IN ('production', 'maintenance', 'energy', 'roi', 'queue')", name="kind_enum"),
        enum_check("role", Role),
    )


class CopilotSession(Base):
    __tablename__ = "copilot_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # uuid
    session_id: Mapped[str | None] = session_id_column()
    role: Mapped[str] = mapped_column(String(32))
    title: Mapped[str | None] = mapped_column(String(200))
    mode: Mapped[str] = mapped_column(String(16), default="deterministic")  # deterministic | llm
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (
        enum_check("role", Role),
        CheckConstraint("mode IN ('deterministic', 'llm')", name="mode_enum"),
    )


class CopilotMessage(Base):
    __tablename__ = "copilot_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    copilot_session_id: Mapped[str] = mapped_column(ForeignKey("copilot_sessions.id"), index=True)
    session_id: Mapped[str | None] = session_id_column()
    sender: Mapped[str] = mapped_column(String(12))  # user | assistant | tool
    content: Mapped[str] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(48))
    tool_calls_json: Mapped[str | None] = mapped_column(Text)
    citations_json: Mapped[str | None] = mapped_column(Text)
    refused: Mapped[bool | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (CheckConstraint("sender IN ('user', 'assistant', 'tool')", name="sender_enum"),)


class KbDocument(Base):
    """Newly authored SAMPLE documents for RAG (data_kind = sample_document). Not real company documents."""

    __tablename__ = "kb_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80))
    lang: Mapped[str] = mapped_column(String(2), default="en")
    title: Mapped[str] = mapped_column(String(200))
    doc_type: Mapped[str] = mapped_column(String(32))  # process_overview, inspection_procedure, kpi_guide, ...
    body_md: Mapped[str] = mapped_column(Text)
    source_path: Mapped[str | None] = mapped_column(String(300))  # data/kb/...
    version: Mapped[str] = mapped_column(String(16), default="1")
    data_kind: Mapped[str] = data_kind_column("sample_document")

    __table_args__ = (
        UniqueConstraint("slug", "lang", name="uq_kb_documents_slug_lang"),
        CheckConstraint("lang IN ('en', 'th')", name="lang_enum"),
    )


class KbChunk(Base):
    __tablename__ = "kb_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("kb_documents.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    heading: Mapped[str | None] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int | None] = mapped_column(Integer)
    vector_json: Mapped[str | None] = mapped_column(Text)  # optional sparse/dense vector; retrieval is copilot's choice

    __table_args__ = (UniqueConstraint("document_id", "chunk_index", name="uq_kb_chunks_doc_idx"),)


class Price(Base):
    """Synthetic / illustrative price series (CPO, kernel, FFB, electricity, diesel). Not market data."""

    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    commodity: Mapped[str] = mapped_column(String(16))
    price_date: Mapped[date] = mapped_column(Date)
    price: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))  # THB/kg, THB/kWh, THB/L
    currency: Mapped[str] = mapped_column(String(3), default="THB")
    source_note: Mapped[str | None] = mapped_column(String(300))
    data_kind: Mapped[str] = data_kind_column("synthetic")

    __table_args__ = (
        UniqueConstraint("commodity", "price_date", name="uq_prices_commodity_date"),
        CheckConstraint(
            "commodity IN ('cpo', 'kernel', 'ffb', 'electricity', 'diesel', 'shell', 'efb')", name="commodity_enum"
        ),
        CheckConstraint("price >= 0", name="price_nonneg"),
    )
