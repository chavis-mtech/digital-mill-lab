"""Traceability: Supplier -> Delivery -> FFB batch -> Processing batch -> CPO output lot.

Palm mills mix FFB from many suppliers in sterilizer cages and the oil stream is continuous, so
physical segregation is rarely possible. The demo therefore uses MASS-BALANCE attribution by default
(`trace_method = 'mass_balance'`): each processing batch records which FFB batches fed it and the mass share;
each CPO lot records the processing batches that filled it and their share. `lot_based` is kept for
segregated runs. This is a data-model sketch for RSPO-style audits, not a certification claim.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, data_kind_column
from app.models.enums import FfbGrade, TraceMethod, enum_check


class FfbBatch(Base):
    """A graded receiving batch on the loading ramp (normally 1 per delivery; split deliveries allowed)."""

    __tablename__ = "ffb_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    delivery_id: Mapped[int] = mapped_column(ForeignKey("ffb_deliveries.id"), index=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), index=True)
    received_ts: Mapped[datetime]
    mass_kg: Mapped[int] = mapped_column(Integer)
    grade: Mapped[str] = mapped_column(String(8))
    ramp_code: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="processed")
    processed_start_ts: Mapped[datetime | None]
    data_kind: Mapped[str] = data_kind_column("synthetic_actual")

    __table_args__ = (
        enum_check("grade", FfbGrade),
        CheckConstraint("mass_kg > 0", name="mass_pos"),
        CheckConstraint("status IN ('waiting', 'partially_processed', 'processed', 'rejected')", name="status_enum"),
    )


class BatchInput(Base):
    """Many-to-many FFB batch -> processing batch with mass share (supports multi-supplier mixing)."""

    __tablename__ = "batch_inputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ffb_batch_id: Mapped[int] = mapped_column(ForeignKey("ffb_batches.id"), index=True)
    production_batch_id: Mapped[int] = mapped_column(ForeignKey("production_batches.id"), index=True)
    mass_kg: Mapped[float] = mapped_column(Float)
    mass_share: Mapped[float] = mapped_column(Float)  # fraction of the processing batch's FFB input (0..1]
    trace_method: Mapped[str] = mapped_column(String(16), default=TraceMethod.mass_balance.value)

    __table_args__ = (
        UniqueConstraint("ffb_batch_id", "production_batch_id", name="uq_batch_inputs_ffb_prod"),
        CheckConstraint("mass_kg > 0", name="mass_pos"),
        CheckConstraint("mass_share > 0 AND mass_share <= 1", name="share_range"),
        enum_check("trace_method", TraceMethod),
    )


class LotComposition(Base):
    """Processing batch -> CPO output lot attribution."""

    __tablename__ = "lot_compositions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cpo_lot_id: Mapped[int] = mapped_column(ForeignKey("cpo_output_lots.id"), index=True)
    production_batch_id: Mapped[int] = mapped_column(ForeignKey("production_batches.id"), index=True)
    cpo_t: Mapped[float] = mapped_column(Float)
    share: Mapped[float] = mapped_column(Float)  # fraction of the lot (0..1]
    trace_method: Mapped[str] = mapped_column(String(16), default=TraceMethod.mass_balance.value)

    __table_args__ = (
        UniqueConstraint("cpo_lot_id", "production_batch_id", name="uq_lot_compositions_lot_batch"),
        CheckConstraint("cpo_t >= 0", name="cpo_nonneg"),
        CheckConstraint("share > 0 AND share <= 1", name="share_range"),
        enum_check("trace_method", TraceMethod),
    )
