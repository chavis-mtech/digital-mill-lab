"""Production domain: shifts, processing batches, hourly mill state, quality, CPO lots, by-products.

Mass-balance relationships the data engine must respect (ranges sourced from docs/business/):
  cpo_t ~= ffb_processed_t * oer_pct / 100 ; kernel_t ~= ffb_processed_t * ker_pct / 100
  by-products (EFB, fibre, shell, POME) are fractions of FFB processed.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, data_kind_column
from app.models.enums import TraceMethod, enum_check, nonneg_check, range_check


class ProductionShift(Base):
    __tablename__ = "production_shifts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), index=True)
    business_date: Mapped[date] = mapped_column(Date, index=True)  # mill-local (Asia/Bangkok) date
    shift_code: Mapped[str] = mapped_column(String(4))  # A (day) | B (night)
    start_ts: Mapped[datetime]
    end_ts: Mapped[datetime]
    ffb_processed_t: Mapped[float] = mapped_column(Float, default=0)
    cpo_t: Mapped[float] = mapped_column(Float, default=0)
    kernel_t: Mapped[float] = mapped_column(Float, default=0)
    oer_pct: Mapped[float | None] = mapped_column(Float)
    ker_pct: Mapped[float | None] = mapped_column(Float)
    operating_hours: Mapped[float] = mapped_column(Float, default=0)
    downtime_min: Mapped[float] = mapped_column(Float, default=0)
    supervisor_code: Mapped[str | None] = mapped_column(String(32))  # fictional staff code
    data_kind: Mapped[str] = data_kind_column("synthetic_actual")

    __table_args__ = (
        UniqueConstraint("facility_id", "business_date", "shift_code", name="uq_production_shifts_fac_date_shift"),
        CheckConstraint("end_ts > start_ts", name="time_order"),
        range_check("oer_pct", 0, 35),
        range_check("ker_pct", 0, 15),
        range_check("operating_hours", 0, 12),
        nonneg_check("ffb_processed_t"),
        nonneg_check("cpo_t"),
        nonneg_check("kernel_t"),
        nonneg_check("downtime_min"),
    )


class ProductionBatch(Base):
    """A processing batch (e.g. one sterilizer-cycle group / time block) fed by one or more FFB batches."""

    __tablename__ = "production_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), index=True)
    line_id: Mapped[int | None] = mapped_column(ForeignKey("production_lines.id"), index=True)
    shift_id: Mapped[int | None] = mapped_column(ForeignKey("production_shifts.id"), index=True)
    start_ts: Mapped[datetime] = mapped_column(index=True)
    end_ts: Mapped[datetime]
    ffb_input_t: Mapped[float] = mapped_column(Float)
    cpo_t: Mapped[float] = mapped_column(Float)
    kernel_t: Mapped[float] = mapped_column(Float)
    oer_pct: Mapped[float] = mapped_column(Float)
    ker_pct: Mapped[float] = mapped_column(Float)
    sterilizer_cycle_min: Mapped[float | None] = mapped_column(Float)
    trace_method: Mapped[str] = mapped_column(String(16), default=TraceMethod.mass_balance.value)
    status: Mapped[str] = mapped_column(String(16), default="completed")
    data_kind: Mapped[str] = data_kind_column("synthetic_actual")

    __table_args__ = (
        CheckConstraint("end_ts > start_ts", name="time_order"),
        CheckConstraint("ffb_input_t > 0", name="ffb_pos"),
        CheckConstraint("cpo_t >= 0 AND cpo_t <= ffb_input_t", name="cpo_le_ffb"),
        CheckConstraint("kernel_t >= 0 AND kernel_t <= ffb_input_t", name="kernel_le_ffb"),
        range_check("oer_pct", 0, 35),
        range_check("ker_pct", 0, 15),
        enum_check("trace_method", TraceMethod),
        CheckConstraint("status IN ('in_progress', 'completed', 'aborted')", name="status_enum"),
    )


class ProcessHourly(Base):
    """Hourly mill state: one row per facility/line/hour. Drives the process twin and production analytics."""

    __tablename__ = "process_hourly"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    line_id: Mapped[int | None] = mapped_column(ForeignKey("production_lines.id"))
    ts: Mapped[datetime]  # start of hour, UTC
    running_minutes: Mapped[float] = mapped_column(Float, default=60)
    downtime_min: Mapped[float] = mapped_column(Float, default=0)
    ffb_received_t: Mapped[float] = mapped_column(Float, default=0)
    ffb_processed_t: Mapped[float] = mapped_column(Float, default=0)
    throughput_tph: Mapped[float] = mapped_column(Float, default=0)
    ffb_waiting_t: Mapped[float | None] = mapped_column(Float)  # loading-ramp inventory
    avg_wait_to_process_h: Mapped[float | None] = mapped_column(Float)
    sterilizer_cycles: Mapped[int | None] = mapped_column(Integer)
    sterilizer_cycle_min: Mapped[float | None] = mapped_column(Float)
    steam_pressure_bar: Mapped[float | None] = mapped_column(Float)  # sterilizer steam header
    boiler_steam_t: Mapped[float | None] = mapped_column(Float)
    digester_temp_c: Mapped[float | None] = mapped_column(Float)
    press_load_a: Mapped[float | None] = mapped_column(Float)
    press_cone_pressure_bar: Mapped[float | None] = mapped_column(Float)
    clarifier_temp_c: Mapped[float | None] = mapped_column(Float)
    oil_loss_press_fibre_pct: Mapped[float | None] = mapped_column(Float)  # % of FFB
    oil_loss_efb_pct: Mapped[float | None] = mapped_column(Float)
    oil_loss_sludge_pct: Mapped[float | None] = mapped_column(Float)
    oil_loss_nut_pct: Mapped[float | None] = mapped_column(Float)
    oil_loss_total_pct: Mapped[float | None] = mapped_column(Float)
    cpo_t: Mapped[float] = mapped_column(Float, default=0)
    kernel_t: Mapped[float] = mapped_column(Float, default=0)
    oer_pct: Mapped[float | None] = mapped_column(Float)
    ker_pct: Mapped[float | None] = mapped_column(Float)
    ffb_ripe_pct: Mapped[float | None] = mapped_column(Float)  # weighted quality of FFB processed this hour
    data_kind: Mapped[str] = data_kind_column("synthetic_actual")

    __table_args__ = (
        UniqueConstraint("facility_id", "line_id", "ts", name="uq_process_hourly_fac_line_ts"),
        Index("ix_process_hourly_ts", "ts"),
        range_check("running_minutes", 0, 60),
        range_check("downtime_min", 0, 60),
        range_check("oer_pct", 0, 35),
        range_check("ker_pct", 0, 15),
        range_check("oil_loss_total_pct", 0, 10),
        range_check("ffb_ripe_pct", 0, 100),
        range_check("steam_pressure_bar", 0, 10),
        range_check("digester_temp_c", 0, 150),
        nonneg_check("ffb_processed_t"),
        nonneg_check("throughput_tph"),
        nonneg_check("cpo_t"),
        nonneg_check("kernel_t"),
        CheckConstraint("cpo_t <= ffb_processed_t OR ffb_processed_t = 0", name="cpo_le_ffb"),
    )


class CpoOutputLot(Base):
    """A CPO storage-tank lot (fill window). Composition by processing batch lives in lot_compositions."""

    __tablename__ = "cpo_output_lots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), index=True)
    tank_code: Mapped[str] = mapped_column(String(16))
    fill_start_ts: Mapped[datetime]
    fill_end_ts: Mapped[datetime | None]
    quantity_t: Mapped[float] = mapped_column(Float)
    ffa_pct: Mapped[float | None] = mapped_column(Float)
    moisture_pct: Mapped[float | None] = mapped_column(Float)
    dirt_pct: Mapped[float | None] = mapped_column(Float)
    dobi: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default="in_storage")
    dispatched_at: Mapped[datetime | None]
    data_kind: Mapped[str] = data_kind_column("synthetic_actual")

    __table_args__ = (
        CheckConstraint("quantity_t >= 0", name="qty_nonneg"),
        range_check("ffa_pct", 0, 20),
        range_check("moisture_pct", 0, 5),
        range_check("dirt_pct", 0, 5),
        range_check("dobi", 0, 6),
        CheckConstraint("status IN ('filling', 'in_storage', 'dispatched')", name="status_enum"),
    )


class ByproductOutput(Base):
    """Kernel and by-product/waste outputs per processing batch (mass balance relative to FFB)."""

    __tablename__ = "byproduct_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    production_batch_id: Mapped[int] = mapped_column(ForeignKey("production_batches.id"), index=True)
    product: Mapped[str] = mapped_column(String(16))
    quantity_t: Mapped[float] = mapped_column(Float)
    pct_of_ffb: Mapped[float | None] = mapped_column(Float)
    destination: Mapped[str | None] = mapped_column(String(32))  # boiler_fuel, sale, mulch, biogas, ...
    data_kind: Mapped[str] = data_kind_column("synthetic_actual")

    __table_args__ = (
        UniqueConstraint("production_batch_id", "product", name="uq_byproduct_outputs_batch_product"),
        CheckConstraint(
            "product IN ('kernel', 'shell', 'fibre', 'efb', 'pome', 'decanter_cake', 'boiler_ash')", name="product_enum"
        ),
        nonneg_check("quantity_t"),
        range_check("pct_of_ffb", 0, 100),
    )


class QualityMeasurement(Base):
    """Lab / QC results (LIMS-like). Linked to whichever entity was sampled."""

    __tablename__ = "quality_measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    sample_ts: Mapped[datetime] = mapped_column(index=True)
    sample_point: Mapped[str] = mapped_column(String(32))  # ffb_grading, press_fibre, efb, sludge, cpo_tank, kernel, effluent
    parameter: Mapped[str] = mapped_column(String(32))  # ffa, moisture, dirt, dobi, oil_loss, ripeness, ...
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))
    production_batch_id: Mapped[int | None] = mapped_column(ForeignKey("production_batches.id"), index=True)
    cpo_lot_id: Mapped[int | None] = mapped_column(ForeignKey("cpo_output_lots.id"), index=True)
    ffb_delivery_id: Mapped[int | None] = mapped_column(ForeignKey("ffb_deliveries.id"), index=True)
    method: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)
    data_kind: Mapped[str] = data_kind_column("synthetic_actual")

    __table_args__ = (Index("ix_quality_point_param_ts", "sample_point", "parameter", "sample_ts"),)
