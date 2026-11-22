"""Energy & utilities: hourly consumption, plant-wide (process_stage_id NULL) or sub-metered by stage.

Palm mills are largely self-powered from fibre/shell-fired boilers + steam turbine; grid import tops up.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, data_kind_column
from app.models.enums import nonneg_check


class EnergyConsumption(Base):
    __tablename__ = "energy_consumption"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    process_stage_id: Mapped[int | None] = mapped_column(ForeignKey("process_stages.id"))
    ts: Mapped[datetime] = mapped_column(index=True)  # start of hour, UTC
    electricity_kwh: Mapped[float] = mapped_column(Float, default=0)
    grid_import_kwh: Mapped[float | None] = mapped_column(Float)
    self_generated_kwh: Mapped[float | None] = mapped_column(Float)
    steam_t: Mapped[float | None] = mapped_column(Float)
    boiler_fibre_t: Mapped[float | None] = mapped_column(Float)
    boiler_shell_t: Mapped[float | None] = mapped_column(Float)
    diesel_l: Mapped[float | None] = mapped_column(Float)
    water_m3: Mapped[float | None] = mapped_column(Float)
    ffb_processed_t: Mapped[float | None] = mapped_column(Float)  # denominator for energy/tonne
    idle_kwh: Mapped[float | None] = mapped_column(Float)  # consumption while not processing
    cost_thb: Mapped[float | None] = mapped_column(Float)  # synthetic tariff x import + diesel
    data_kind: Mapped[str] = data_kind_column("synthetic_actual")

    __table_args__ = (
        UniqueConstraint("facility_id", "process_stage_id", "ts", name="uq_energy_consumption_fac_stage_ts"),
        nonneg_check("electricity_kwh"),
        nonneg_check("grid_import_kwh"),
        nonneg_check("self_generated_kwh"),
        nonneg_check("steam_t"),
        nonneg_check("diesel_l"),
        nonneg_check("water_m3"),
        nonneg_check("ffb_processed_t"),
        nonneg_check("idle_kwh"),
        CheckConstraint("idle_kwh IS NULL OR idle_kwh <= electricity_kwh", name="idle_le_total"),
    )
