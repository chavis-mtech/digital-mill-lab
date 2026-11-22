"""Maintenance: technicians, maintenance events (history), work orders + status history.

Work-order flow (AI-C05): AI alert -> engineer review -> work order (open) -> assigned -> in_progress
-> resolved (maintenance record written) -> closed. ADR-006: visitor-created rows carry session_id;
seeded rows (session_id NULL) are a read-only shared baseline - a visitor transition on a seeded
work order creates a session-scoped copy (cloned_from_id) instead of UPDATE-ing the baseline row.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, data_kind_column, session_id_column, utcnow
from app.models.enums import Role, WorkOrderPriority, WorkOrderSource, WorkOrderStatus, enum_check, nonneg_check


class Technician(Base):
    __tablename__ = "technicians"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))  # fictional
    skill: Mapped[str] = mapped_column(String(16))
    shift_code: Mapped[str | None] = mapped_column(String(4))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    data_kind: Mapped[str] = data_kind_column()

    __table_args__ = (
        CheckConstraint("skill IN ('mechanical', 'electrical', 'instrument', 'general')", name="skill_enum"),
    )


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    session_id: Mapped[str | None] = session_id_column()
    cloned_from_id: Mapped[int | None] = mapped_column(ForeignKey("work_orders.id"))
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(8), default=WorkOrderPriority.medium.value)
    status: Mapped[str] = mapped_column(String(16), default=WorkOrderStatus.open.value)
    source_type: Mapped[str] = mapped_column(String(16), default=WorkOrderSource.manual.value)
    alert_id: Mapped[int | None] = mapped_column(ForeignKey("alerts.id"), index=True)
    recommendation_id: Mapped[int | None] = mapped_column(ForeignKey("ai_recommendations.id"), index=True)
    anomaly_event_id: Mapped[int | None] = mapped_column(ForeignKey("anomaly_events.id"), index=True)
    assigned_technician_id: Mapped[int | None] = mapped_column(ForeignKey("technicians.id"), index=True)
    created_by_role: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    demo_as_of: Mapped[datetime | None]  # the demo clock (as_of) at creation - for playback consistency
    due_at: Mapped[datetime | None]
    resolved_at: Mapped[datetime | None]
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    estimated_downtime_h: Mapped[float | None] = mapped_column(Float)
    data_kind: Mapped[str] = data_kind_column("synthetic")

    __table_args__ = (
        enum_check("priority", WorkOrderPriority),
        enum_check("status", WorkOrderStatus),
        enum_check("source_type", WorkOrderSource),
        enum_check("created_by_role", Role),
        nonneg_check("estimated_downtime_h"),
        Index("ix_work_orders_session_status", "session_id", "status"),
    )


class WorkOrderStatusHistory(Base):
    __tablename__ = "work_order_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"), index=True)
    session_id: Mapped[str | None] = session_id_column()
    from_status: Mapped[str | None] = mapped_column(String(16))
    to_status: Mapped[str] = mapped_column(String(16))
    actor_role: Mapped[str] = mapped_column(String(32))
    changed_at: Mapped[datetime] = mapped_column(default=utcnow)
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        enum_check("from_status", WorkOrderStatus, nullable=True),
        enum_check("to_status", WorkOrderStatus),
        enum_check("actor_role", Role),
    )


class MaintenanceEvent(Base):
    """Maintenance history (seeded) and records written when a work order is resolved."""

    __tablename__ = "maintenance_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)
    work_order_id: Mapped[int | None] = mapped_column(ForeignKey("work_orders.id"), index=True)
    session_id: Mapped[str | None] = session_id_column()
    event_type: Mapped[str] = mapped_column(String(16))
    start_ts: Mapped[datetime] = mapped_column(index=True)
    end_ts: Mapped[datetime | None]
    downtime_min: Mapped[float] = mapped_column(Float, default=0)
    planned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    description: Mapped[str | None] = mapped_column(Text)
    parts_cost_thb: Mapped[float | None] = mapped_column(Float)  # synthetic
    labour_cost_thb: Mapped[float | None] = mapped_column(Float)  # synthetic
    technician_id: Mapped[int | None] = mapped_column(ForeignKey("technicians.id"))
    data_kind: Mapped[str] = data_kind_column("synthetic_actual")

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('breakdown', 'corrective', 'preventive', 'inspection', 'lubrication', 'calibration', "
            "'overhaul')",
            name="type_enum",
        ),
        CheckConstraint("end_ts IS NULL OR end_ts >= start_ts", name="time_order"),
        nonneg_check("downtime_min"),
        nonneg_check("parts_cost_thb"),
        nonneg_check("labour_cost_thb"),
    )
