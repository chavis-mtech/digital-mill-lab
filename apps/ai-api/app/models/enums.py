"""Shared enumerations. Stored as VARCHAR + CHECK constraint (portable), exposed as StrEnum in schemas."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import CheckConstraint


class Role(StrEnum):
    executive = "executive"
    factory_manager = "factory_manager"
    production_engineer = "production_engineer"
    maintenance_engineer = "maintenance_engineer"
    logistics_officer = "logistics_officer"
    ai_analyst = "ai_analyst"
    system_admin = "system_admin"
    public_viewer = "public_viewer"


class ProvenanceKind(StrEnum):
    synthetic_actual = "synthetic_actual"
    forecast = "forecast"
    what_if = "what_if"


class DataKind(StrEnum):
    synthetic = "synthetic"
    synthetic_actual = "synthetic_actual"
    forecast = "forecast"
    what_if = "what_if"
    sample_document = "sample_document"
    user_input = "user_input"


class ScenarioCode(StrEnum):
    NORMAL_DAY = "NORMAL_DAY"
    OER_DEGRADATION = "OER_DEGRADATION"
    PRESS_VIBRATION_ANOMALY = "PRESS_VIBRATION_ANOMALY"
    STEAM_PRESSURE_DEVIATION = "STEAM_PRESSURE_DEVIATION"
    TRUCK_QUEUE_CONGESTION = "TRUCK_QUEUE_CONGESTION"
    ENERGY_EFFICIENCY_DROP = "ENERGY_EFFICIENCY_DROP"


class StageCode(StrEnum):
    FFB_RECEPTION = "FFB_RECEPTION"
    STERILIZATION = "STERILIZATION"
    THRESHING = "THRESHING"
    DIGESTION = "DIGESTION"
    PRESSING = "PRESSING"
    CLARIFICATION = "CLARIFICATION"
    CPO_STORAGE = "CPO_STORAGE"
    KERNEL_RECOVERY = "KERNEL_RECOVERY"
    BOILER_STEAM = "BOILER_STEAM"
    POWER = "POWER"
    WATER_TREATMENT = "WATER_TREATMENT"
    POME_TREATMENT = "POME_TREATMENT"


class EquipmentType(StrEnum):
    boiler = "boiler"
    sterilizer = "sterilizer"
    conveyor = "conveyor"
    thresher = "thresher"
    digester = "digester"
    screw_press = "screw_press"
    pump = "pump"
    motor = "motor"
    generator = "generator"
    turbine = "turbine"
    centrifuge = "centrifuge"
    clarifier_tank = "clarifier_tank"
    storage_tank = "storage_tank"
    weighbridge = "weighbridge"
    kernel_plant = "kernel_plant"
    other_rotating = "other_rotating"


class SensorType(StrEnum):
    temperature = "temperature"
    vibration = "vibration"
    current = "current"
    pressure = "pressure"
    rpm = "rpm"
    running_hours = "running_hours"
    load = "load"
    state = "state"
    flow = "flow"
    level = "level"


class HealthState(StrEnum):
    normal = "normal"
    warning = "warning"
    critical = "critical"
    maintenance_required = "maintenance_required"


class Severity(StrEnum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AlertSource(StrEnum):
    production_anomaly = "production_anomaly"
    equipment_anomaly = "equipment_anomaly"
    energy_anomaly = "energy_anomaly"
    logistics_anomaly = "logistics_anomaly"
    quality = "quality"
    rule = "rule"


class AlertStatus(StrEnum):
    new = "new"
    acknowledged = "acknowledged"
    in_progress = "in_progress"
    resolved = "resolved"
    dismissed = "dismissed"


class AnomalyStatus(StrEnum):
    new = "new"
    acknowledged = "acknowledged"
    verified = "verified"
    dismissed = "dismissed"


class RecommendationStatus(StrEnum):
    proposed = "proposed"
    approved = "approved"
    rejected = "rejected"
    superseded = "superseded"


class WorkOrderStatus(StrEnum):
    open = "open"  # created after engineer review
    assigned = "assigned"
    in_progress = "in_progress"
    on_hold = "on_hold"
    resolved = "resolved"  # maintenance record written
    closed = "closed"  # verified by engineer
    cancelled = "cancelled"


class WorkOrderPriority(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class WorkOrderSource(StrEnum):
    alert = "alert"
    recommendation = "recommendation"
    manual = "manual"
    preventive = "preventive"


class FfbGrade(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    reject = "reject"


class TraceMethod(StrEnum):
    lot_based = "lot_based"
    mass_balance = "mass_balance"


class TruckStatus(StrEnum):
    arriving = "arriving"
    queued = "queued"
    weighing_in = "weighing_in"
    grading = "grading"
    unloading = "unloading"
    weighing_out = "weighing_out"
    exited = "exited"


def enum_check(column: str, enum_cls: type[StrEnum], name: str | None = None, nullable: bool = False) -> CheckConstraint:
    values = ", ".join(f"'{v.value}'" for v in enum_cls)
    expr = f"{column} IN ({values})"
    if nullable:
        expr = f"{column} IS NULL OR {expr}"
    return CheckConstraint(expr, name=name or f"{column}_enum")


def range_check(column: str, lo: float, hi: float, name: str | None = None) -> CheckConstraint:
    return CheckConstraint(f"{column} IS NULL OR ({column} >= {lo} AND {column} <= {hi})", name=name or f"{column}_range")


def nonneg_check(column: str, name: str | None = None) -> CheckConstraint:
    return CheckConstraint(f"{column} IS NULL OR {column} >= 0", name=name or f"{column}_nonneg")
