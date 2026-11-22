"""AI domain: model registry, predictions, anomaly events, recommendations, unified alerts.

Honesty constraints encoded in the schema:
- ai_recommendations.advisory is always TRUE (AI never controls machines).
- anomaly events carry evidence + "contributing factors", never a proven cause.
- risk scores are relative scores (0-100), NOT calibrated failure probabilities.
Visitor decisions on seeded rows are stored in *_status_changes / recommendation_decisions
(session-scoped, ADR-006) so the shared baseline is never mutated.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, data_kind_column, session_id_column, utcnow
from app.models.enums import (
    AlertSource,
    AlertStatus,
    AnomalyStatus,
    RecommendationStatus,
    Role,
    ScenarioCode,
    Severity,
    enum_check,
    range_check,
)


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64))  # e.g. oer_forecast, equipment_anomaly
    version: Mapped[str] = mapped_column(String(32))
    task: Mapped[str] = mapped_column(String(24))  # regression | anomaly | classification | forecast
    algorithm: Mapped[str] = mapped_column(String(64))
    features_json: Mapped[str | None] = mapped_column(Text)
    metrics_json: Mapped[str | None] = mapped_column(Text)  # measured on temporal hold-out, incl. baseline
    beats_baseline: Mapped[bool | None] = mapped_column(Boolean)
    train_window_start: Mapped[datetime | None]
    train_window_end: Mapped[datetime | None]
    test_window_start: Mapped[datetime | None]
    test_window_end: Mapped[datetime | None]
    trained_at: Mapped[datetime] = mapped_column(default=utcnow)
    artifact_path: Mapped[str | None] = mapped_column(String(300))  # relative to repo root (data/models/...)
    model_card_path: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(16), default="trained")
    data_kind: Mapped[str] = data_kind_column("synthetic")  # trained on synthetic data

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_model_registry_name_version"),
        CheckConstraint("status IN ('trained', 'active', 'retired', 'failed')", name="status_enum"),
        CheckConstraint("task IN ('regression', 'anomaly', 'classification', 'forecast')", name="task_enum"),
    )


class AiPrediction(Base):
    __tablename__ = "ai_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("model_registry.id"), index=True)
    target: Mapped[str] = mapped_column(String(32))  # oer_pct, energy_kwh_per_t, queue_wait_min, arrivals, ...
    entity_type: Mapped[str] = mapped_column(String(32))  # facility, equipment, truck_trip, ...
    entity_id: Mapped[int | None] = mapped_column(Integer)
    target_ts: Mapped[datetime]
    made_at: Mapped[datetime]  # demo-clock time the forecast was issued (no look-ahead past this)
    horizon_minutes: Mapped[int | None] = mapped_column(Integer)
    value: Mapped[float] = mapped_column(Float)
    lower: Mapped[float | None] = mapped_column(Float)
    upper: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(16))
    explanation_json: Mapped[str | None] = mapped_column(Text)
    data_kind: Mapped[str] = data_kind_column("forecast")

    __table_args__ = (
        Index("ix_ai_predictions_target_ts", "target", "target_ts"),
        CheckConstraint("lower IS NULL OR upper IS NULL OR lower <= upper", name="interval_order"),
    )


class AnomalyEvent(Base):
    __tablename__ = "anomaly_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    detector: Mapped[str] = mapped_column(String(48))  # e.g. isolation_forest_equipment, zscore_production
    model_id: Mapped[int | None] = mapped_column(ForeignKey("model_registry.id"))
    domain: Mapped[str] = mapped_column(String(16))  # production | equipment | energy | logistics
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"), index=True)
    process_stage_id: Mapped[int | None] = mapped_column(ForeignKey("process_stages.id"), index=True)
    start_ts: Mapped[datetime] = mapped_column(index=True)
    end_ts: Mapped[datetime | None]
    peak_ts: Mapped[datetime | None]
    score: Mapped[float] = mapped_column(Float)  # 0..1 normalised anomaly score
    severity: Mapped[str] = mapped_column(String(10))
    evidence_json: Mapped[str | None] = mapped_column(Text)  # observed vs normal range, metrics
    contributing_json: Mapped[str | None] = mapped_column(Text)  # possible contributing factors (not causes)
    status: Mapped[str] = mapped_column(String(16), default=AnomalyStatus.new.value)
    scenario_code: Mapped[str | None] = mapped_column(String(32))
    data_kind: Mapped[str] = data_kind_column("synthetic")

    __table_args__ = (
        CheckConstraint("domain IN ('production', 'equipment', 'energy', 'logistics')", name="domain_enum"),
        range_check("score", 0, 1),
        enum_check("severity", Severity),
        enum_check("status", AnomalyStatus),
        enum_check("scenario_code", ScenarioCode, nullable=True),
        CheckConstraint("end_ts IS NULL OR end_ts >= start_ts", name="time_order"),
    )


class AnomalyStatusChange(Base):
    __tablename__ = "anomaly_status_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    anomaly_event_id: Mapped[int] = mapped_column(ForeignKey("anomaly_events.id"), index=True)
    session_id: Mapped[str | None] = session_id_column()
    from_status: Mapped[str | None] = mapped_column(String(16))
    to_status: Mapped[str] = mapped_column(String(16))
    actor_role: Mapped[str] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (enum_check("to_status", AnomalyStatus), enum_check("actor_role", Role))


class AiRecommendation(Base):
    __tablename__ = "ai_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    rec_type: Mapped[str] = mapped_column(String(32))  # inspect_bearing, lubrication, alignment, sensor_check, ...
    title: Mapped[str] = mapped_column(String(200))
    rationale: Mapped[str] = mapped_column(Text)
    evidence_json: Mapped[str | None] = mapped_column(Text)
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"), index=True)
    process_stage_id: Mapped[int | None] = mapped_column(ForeignKey("process_stages.id"), index=True)
    anomaly_event_id: Mapped[int | None] = mapped_column(ForeignKey("anomaly_events.id"), index=True)
    model_id: Mapped[int | None] = mapped_column(ForeignKey("model_registry.id"))
    priority: Mapped[str] = mapped_column(String(10), default=Severity.medium.value)
    risk_score: Mapped[float | None] = mapped_column(Float)  # 0-100 relative score, NOT a probability
    advisory: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    status: Mapped[str] = mapped_column(String(16), default=RecommendationStatus.proposed.value)
    created_at: Mapped[datetime]
    data_kind: Mapped[str] = data_kind_column("synthetic")

    __table_args__ = (
        CheckConstraint("advisory = true", name="always_advisory"),
        enum_check("priority", Severity),
        enum_check("status", RecommendationStatus),
        range_check("risk_score", 0, 100),
    )


class RecommendationDecision(Base):
    """Human approval/rejection of an AI recommendation (session-scoped)."""

    __tablename__ = "recommendation_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(ForeignKey("ai_recommendations.id"), index=True)
    session_id: Mapped[str | None] = session_id_column()
    decision: Mapped[str] = mapped_column(String(16))
    approver_role: Mapped[str] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(Text)
    work_order_id: Mapped[int | None] = mapped_column(ForeignKey("work_orders.id"))
    decided_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (
        CheckConstraint("decision IN ('approved', 'rejected')", name="decision_enum"),
        enum_check("approver_role", Role),
    )


class Alert(Base):
    """Unified alert table linking modules (production, equipment, energy, logistics, quality)."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    source: Mapped[str] = mapped_column(String(24))
    module: Mapped[str] = mapped_column(String(16))  # production | maintenance | energy | logistics | quality
    severity: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(16), default=AlertStatus.new.value)
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    raised_at: Mapped[datetime] = mapped_column(index=True)
    resolved_at: Mapped[datetime | None]
    facility_id: Mapped[int | None] = mapped_column(ForeignKey("facilities.id"))
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"), index=True)
    process_stage_id: Mapped[int | None] = mapped_column(ForeignKey("process_stages.id"), index=True)
    anomaly_event_id: Mapped[int | None] = mapped_column(ForeignKey("anomaly_events.id"), index=True)
    recommendation_id: Mapped[int | None] = mapped_column(ForeignKey("ai_recommendations.id"))
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"))
    truck_trip_id: Mapped[int | None] = mapped_column(ForeignKey("truck_trips.id"))
    business_impact_json: Mapped[str | None] = mapped_column(Text)  # estimated impact, with assumptions
    evidence_json: Mapped[str | None] = mapped_column(Text)
    scenario_code: Mapped[str | None] = mapped_column(String(32), index=True)
    data_kind: Mapped[str] = data_kind_column("synthetic")

    __table_args__ = (
        enum_check("source", AlertSource),
        enum_check("severity", Severity),
        enum_check("status", AlertStatus),
        enum_check("scenario_code", ScenarioCode, nullable=True),
        CheckConstraint(
            "module IN ('production', 'maintenance', 'energy', 'logistics', 'quality')", name="module_enum"
        ),
        CheckConstraint("resolved_at IS NULL OR resolved_at >= raised_at", name="time_order"),
    )


class AlertStatusChange(Base):
    __tablename__ = "alert_status_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id"), index=True)
    session_id: Mapped[str | None] = session_id_column()
    from_status: Mapped[str | None] = mapped_column(String(16))
    to_status: Mapped[str] = mapped_column(String(16))
    actor_role: Mapped[str] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (enum_check("to_status", AlertStatus), enum_check("actor_role", Role))
