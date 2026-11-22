"""Sensor time-series (largest table). Indexed by (sensor_id, ts)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# BIGINT on PostgreSQL; INTEGER on SQLite so it stays the rowid alias (autoincrement works).
BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    sensor_id: Mapped[int] = mapped_column(ForeignKey("sensors.id"))
    ts: Mapped[datetime]
    value: Mapped[float] = mapped_column(Float)
    quality: Mapped[str] = mapped_column(String(12), default="good", server_default="good")

    __table_args__ = (
        UniqueConstraint("sensor_id", "ts", name="uq_sensor_readings_sensor_ts"),  # also the (sensor_id, ts) index
        CheckConstraint("quality IN ('good', 'uncertain', 'bad')", name="quality_enum"),
    )
