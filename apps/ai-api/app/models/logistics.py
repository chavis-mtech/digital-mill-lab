"""Logistics & weighbridge: suppliers, plantations, truck trips, queue events, tickets, FFB deliveries.

Flow: Supplier -> Truck arrival -> Queue -> Weighbridge (in) -> Grading -> Unloading -> Weighbridge (out) -> Exit.
Suppliers and plates are synthetic; no personal data. A logistics anomaly is never an accusation.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, data_kind_column
from app.models.enums import FfbGrade, TruckStatus, enum_check, nonneg_check, range_check


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(200))  # fictional
    supplier_type: Mapped[str] = mapped_column(String(16))
    province: Mapped[str | None] = mapped_column(String(100))
    registered_on: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    # Sustainability data-model sketch only - never a certification claim.
    sustainability_status: Mapped[str] = mapped_column(String(24), default="not_assessed")
    quality_tier: Mapped[str | None] = mapped_column(String(8))  # synthetic generator parameter (A/B/C)
    data_kind: Mapped[str] = data_kind_column()

    __table_args__ = (
        CheckConstraint("supplier_type IN ('smallholder', 'dealer', 'estate', 'own_estate')", name="type_enum"),
        CheckConstraint(
            "sustainability_status IN ('not_assessed', 'data_collected', 'gap_identified', 'documented')",
            name="sustainability_enum",
        ),
    )


class Plantation(Base):
    __tablename__ = "plantations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    area_ha: Mapped[float | None] = mapped_column(Float)
    district: Mapped[str | None] = mapped_column(String(100))
    lat: Mapped[float | None] = mapped_column(Float)  # coarse synthetic coordinates
    lon: Mapped[float | None] = mapped_column(Float)
    planting_year: Mapped[int | None] = mapped_column(Integer)
    sustainability_json: Mapped[str | None] = mapped_column(Text)  # RSPO-style audit fields (sketch)
    data_kind: Mapped[str] = data_kind_column()

    __table_args__ = (
        nonneg_check("area_ha"),
        range_check("lat", -90, 90),
        range_check("lon", -180, 180),
    )


class TruckTrip(Base):
    __tablename__ = "truck_trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    plate_masked: Mapped[str] = mapped_column(String(16))  # synthetic, masked (e.g. "XX-1234")
    truck_type: Mapped[str | None] = mapped_column(String(16))  # pickup, 6-wheel, 10-wheel
    arrival_ts: Mapped[datetime] = mapped_column(index=True)
    queue_start_ts: Mapped[datetime | None]
    weigh_in_ts: Mapped[datetime | None]
    grading_ts: Mapped[datetime | None]
    unload_start_ts: Mapped[datetime | None]
    unload_end_ts: Mapped[datetime | None]
    weigh_out_ts: Mapped[datetime | None]
    exit_ts: Mapped[datetime | None]
    status: Mapped[str] = mapped_column(String(16), default=TruckStatus.exited.value)
    data_kind: Mapped[str] = data_kind_column("synthetic_actual")

    __table_args__ = (
        enum_check("status", TruckStatus),
        CheckConstraint("weigh_in_ts IS NULL OR weigh_in_ts >= arrival_ts", name="weigh_in_after_arrival"),
        CheckConstraint("exit_ts IS NULL OR exit_ts >= arrival_ts", name="exit_after_arrival"),
    )


class QueueEvent(Base):
    __tablename__ = "queue_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    truck_trip_id: Mapped[int] = mapped_column(ForeignKey("truck_trips.id"), index=True)
    ts: Mapped[datetime]
    event_type: Mapped[str] = mapped_column(String(20))
    queue_length: Mapped[int | None] = mapped_column(Integer)  # trucks waiting at the moment of the event
    location: Mapped[str | None] = mapped_column(String(32))  # gate, bridge-1, ramp-2

    __table_args__ = (
        Index("ix_queue_events_ts", "ts"),
        CheckConstraint(
            "event_type IN ('arrived', 'queued', 'called', 'weigh_in', 'graded', 'unload_start', 'unload_end', "
            "'weigh_out', 'exited')",
            name="event_enum",
        ),
        nonneg_check("queue_length"),
    )


class WeighbridgeTicket(Base):
    __tablename__ = "weighbridge_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_no: Mapped[str] = mapped_column(String(40), unique=True)
    truck_trip_id: Mapped[int] = mapped_column(ForeignKey("truck_trips.id"), unique=True)
    bridge_code: Mapped[str] = mapped_column(String(16))
    weigh_in_ts: Mapped[datetime]
    weigh_out_ts: Mapped[datetime | None]
    gross_kg: Mapped[int] = mapped_column(Integer)
    tare_kg: Mapped[int | None] = mapped_column(Integer)
    net_kg: Mapped[int | None] = mapped_column(Integer)
    operator_code: Mapped[str | None] = mapped_column(String(32))  # fictional staff code
    data_kind: Mapped[str] = data_kind_column("synthetic_actual")

    __table_args__ = (
        CheckConstraint("gross_kg > 0", name="gross_pos"),
        CheckConstraint("tare_kg IS NULL OR (tare_kg > 0 AND tare_kg < gross_kg)", name="tare_lt_gross"),
        CheckConstraint("net_kg IS NULL OR net_kg = gross_kg - tare_kg", name="net_eq_gross_minus_tare"),
        CheckConstraint("weigh_out_ts IS NULL OR weigh_out_ts >= weigh_in_ts", name="time_order"),
    )


class FfbDelivery(Base):
    __tablename__ = "ffb_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    plantation_id: Mapped[int | None] = mapped_column(ForeignKey("plantations.id"), index=True)
    truck_trip_id: Mapped[int] = mapped_column(ForeignKey("truck_trips.id"), unique=True)
    ticket_id: Mapped[int | None] = mapped_column(ForeignKey("weighbridge_tickets.id"), unique=True)
    business_date: Mapped[date] = mapped_column(Date, index=True)
    received_ts: Mapped[datetime]
    net_kg: Mapped[int] = mapped_column(Integer)
    grade: Mapped[str] = mapped_column(String(8))
    ripe_pct: Mapped[float | None] = mapped_column(Float)
    unripe_pct: Mapped[float | None] = mapped_column(Float)
    overripe_pct: Mapped[float | None] = mapped_column(Float)
    empty_bunch_pct: Mapped[float | None] = mapped_column(Float)
    long_stalk_pct: Mapped[float | None] = mapped_column(Float)
    deduction_pct: Mapped[float] = mapped_column(Float, default=0)
    accepted_kg: Mapped[int] = mapped_column(Integer)
    harvest_to_mill_h: Mapped[float | None] = mapped_column(Float)  # freshness proxy (FFA risk)
    data_kind: Mapped[str] = data_kind_column("synthetic_actual")

    __table_args__ = (
        enum_check("grade", FfbGrade),
        CheckConstraint("net_kg > 0", name="net_pos"),
        CheckConstraint("accepted_kg >= 0 AND accepted_kg <= net_kg", name="accepted_le_net"),
        range_check("ripe_pct", 0, 100),
        range_check("unripe_pct", 0, 100),
        range_check("overripe_pct", 0, 100),
        range_check("empty_bunch_pct", 0, 100),
        range_check("long_stalk_pct", 0, 100),
        range_check("deduction_pct", 0, 100),
        nonneg_check("harvest_to_mill_h"),
    )
