"""Core plant registry: company -> facility -> production line -> process stage -> equipment -> sensor.

All entities are FICTIONAL ("Demo Palm Oil Co. (fictional)", "Demo Palm Mill A").
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, data_kind_column
from app.models.enums import EquipmentType, SensorType, StageCode, enum_check, nonneg_check, range_check


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    is_fictional: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    data_kind: Mapped[str] = data_kind_column()

    __table_args__ = (CheckConstraint("is_fictional = true", name="must_be_fictional"),)


class Facility(Base):
    __tablename__ = "facilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    facility_type: Mapped[str] = mapped_column(String(32), default="palm_oil_mill")
    capacity_tph: Mapped[float] = mapped_column(Float)  # rated FFB throughput, tonnes/hour
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Bangkok")
    region: Mapped[str | None] = mapped_column(String(100))
    data_kind: Mapped[str] = data_kind_column()

    __table_args__ = (CheckConstraint("capacity_tph > 0", name="capacity_pos"),)


class ProductionLine(Base):
    __tablename__ = "production_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    capacity_tph: Mapped[float] = mapped_column(Float)

    __table_args__ = (CheckConstraint("capacity_tph > 0", name="capacity_pos"),)


class ProcessStage(Base):
    __tablename__ = "process_stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), index=True)
    code: Mapped[str] = mapped_column(String(32))  # StageCode
    name_en: Mapped[str] = mapped_column(String(100))
    name_th: Mapped[str] = mapped_column(String(100))
    sequence: Mapped[int] = mapped_column(Integer)  # order in the main flow (support stages >= 100)
    kind: Mapped[str] = mapped_column(String(16), default="main")  # main | support
    description: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("facility_id", "code", name="uq_process_stages_facility_code"),
        enum_check("code", StageCode),
        CheckConstraint("kind IN ('main', 'support')", name="kind_enum"),
    )


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), index=True)
    line_id: Mapped[int | None] = mapped_column(ForeignKey("production_lines.id"), index=True)
    process_stage_id: Mapped[int] = mapped_column(ForeignKey("process_stages.id"), index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)  # e.g. PRS-02
    name: Mapped[str] = mapped_column(String(200))
    equipment_type: Mapped[str] = mapped_column(String(32))
    manufacturer: Mapped[str | None] = mapped_column(String(100))  # fictional / generic
    install_date: Mapped[date | None] = mapped_column(Date)
    criticality: Mapped[str] = mapped_column(String(1), default="B")  # A (line-stopping) .. C
    rated_power_kw: Mapped[float | None] = mapped_column(Float)
    rated_capacity: Mapped[float | None] = mapped_column(Float)
    rated_capacity_unit: Mapped[str | None] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    data_kind: Mapped[str] = data_kind_column()

    __table_args__ = (
        enum_check("equipment_type", EquipmentType),
        CheckConstraint("criticality IN ('A', 'B', 'C')", name="criticality_enum"),
        nonneg_check("rated_power_kw"),
    )


class Sensor(Base):
    __tablename__ = "sensors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)
    code: Mapped[str] = mapped_column(String(48), unique=True)  # e.g. PRS-02-VIB-DE
    name: Mapped[str] = mapped_column(String(200))
    sensor_type: Mapped[str] = mapped_column(String(24))
    unit: Mapped[str] = mapped_column(String(16))  # degC, mm/s, A, bar, rpm, h, %, state
    # Engineering ranges used by computed health states (AI-C01). warn/crit are upper limits
    # unless the sensor is low-is-bad (see low_is_bad).
    normal_min: Mapped[float | None] = mapped_column(Float)
    normal_max: Mapped[float | None] = mapped_column(Float)
    warn_limit: Mapped[float | None] = mapped_column(Float)
    crit_limit: Mapped[float | None] = mapped_column(Float)
    low_is_bad: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    sampling_seconds: Mapped[int] = mapped_column(Integer, default=600)
    data_kind: Mapped[str] = data_kind_column()

    __table_args__ = (
        enum_check("sensor_type", SensorType),
        CheckConstraint("normal_min IS NULL OR normal_max IS NULL OR normal_min <= normal_max", name="normal_order"),
        range_check("sampling_seconds", 1, 86400, name="sampling_range"),
    )
