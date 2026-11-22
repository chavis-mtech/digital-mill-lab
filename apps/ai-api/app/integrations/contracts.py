"""FUTURE INTEGRATION CONTRACTS - CONTRACT ONLY. NOT CONNECTED TO ANY REAL SYSTEM.

These Protocols describe how a real deployment *could* plug plant/enterprise systems into the platform.
No adapter here talks to ERP/MES/SCADA/PLC/OPC UA/MQTT/weighbridge/LIMS/GPS/accounting/HR systems,
and nothing implies integration with any real company system (SPEC honesty rule 3).

Design rules for any future real adapter (see docs/architecture/INTEGRATION_CONTRACTS.md):
- READ-ONLY toward OT (SCADA/PLC/OPC UA): the platform never writes setpoints or commands (rule 4).
- Adapters return domain DTOs below, not vendor payloads; mapping lives inside the adapter.
- Every call is time-bounded (as_of / window) so playback and live modes share one interface.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable

CONTRACT_STATUS = "planned"  # contract only - no implementation exists


# ---------------------------------------------------------------- DTOs
@dataclass(frozen=True)
class TagReading:
    tag: str  # e.g. OPC UA node id / historian tag, mapped to sensors.code
    ts: datetime
    value: float
    quality: str = "good"


@dataclass(frozen=True)
class WeighEvent:
    ticket_no: str
    plate_masked: str
    gross_kg: int | None
    tare_kg: int | None
    ts: datetime
    bridge_code: str


@dataclass(frozen=True)
class LabResult:
    sample_id: str
    sample_point: str
    parameter: str
    value: float
    unit: str
    ts: datetime


@dataclass(frozen=True)
class WorkOrderRecord:
    external_id: str
    equipment_code: str
    status: str
    title: str
    opened_at: datetime
    closed_at: datetime | None = None


@dataclass(frozen=True)
class ProductionOrder:
    external_id: str
    business_date: str
    planned_ffb_t: float
    actual_ffb_t: float | None = None


@dataclass(frozen=True)
class VehiclePosition:
    vehicle_ref: str
    ts: datetime
    lat: float
    lon: float
    eta_minutes: float | None = None


@dataclass(frozen=True)
class CostEntry:
    account: str
    cost_center: str
    period: str
    amount_thb: float
    tags: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------- Protocols
@runtime_checkable
class ScadaHistorianSource(Protocol):
    """SCADA / PLC via historian or OPC UA (read-only subscription/polling)."""

    def read_tags(self, tags: Iterable[str], start: datetime, end: datetime) -> list[TagReading]: ...


@runtime_checkable
class OpcUaClient(Protocol):
    """OPC UA browse + read. Write methods are deliberately absent."""

    def browse(self, node_id: str) -> list[str]: ...
    def read_values(self, node_ids: Iterable[str]) -> list[TagReading]: ...


@runtime_checkable
class MqttTelemetrySource(Protocol):
    """MQTT / Sparkplug B telemetry (subscribe only)."""

    def subscribe(self, topic_filter: str) -> Iterable[TagReading]: ...


@runtime_checkable
class WeighbridgeSource(Protocol):
    def events(self, start: datetime, end: datetime) -> list[WeighEvent]: ...


@runtime_checkable
class LimsSource(Protocol):
    def results(self, start: datetime, end: datetime, sample_point: str | None = None) -> list[LabResult]: ...


@runtime_checkable
class MesSource(Protocol):
    def production_orders(self, business_date: str) -> list[ProductionOrder]: ...


@runtime_checkable
class ErpConnector(Protocol):
    """ERP / CMMS: read master data and work orders; WRITE only human-confirmed work orders (outbox pattern)."""

    def list_work_orders(self, since: datetime) -> list[WorkOrderRecord]: ...
    def submit_confirmed_work_order(self, record: WorkOrderRecord, idempotency_key: str) -> str: ...


@runtime_checkable
class FleetGpsSource(Protocol):
    def positions(self, since: datetime) -> list[VehiclePosition]: ...


@runtime_checkable
class AccountingHrSource(Protocol):
    def cost_entries(self, period: str) -> list[CostEntry]: ...


# ---------------------------------------------------------------- synthetic stub
class SyntheticAdapter:
    """Placeholder showing where the synthetic data engine would satisfy the same contracts.

    STUB: every method raises NotImplementedError. The demo reads synthetic data directly from the database;
    this class exists only to document the seam between ingestion and analytics.
    """

    status = CONTRACT_STATUS
    label = "Synthetic adapter (contract stub, not connected to any real system)"

    def read_tags(self, tags: Iterable[str], start: datetime, end: datetime) -> list[TagReading]:
        raise NotImplementedError("contract only - synthetic data is read from the DB")

    def events(self, start: datetime, end: datetime) -> list[WeighEvent]:
        raise NotImplementedError("contract only - synthetic data is read from the DB")

    def results(self, start: datetime, end: datetime, sample_point: str | None = None) -> list[LabResult]:
        raise NotImplementedError("contract only - synthetic data is read from the DB")


INTEGRATION_CATALOG = [
    {"system": "ERP / CMMS", "protocol": "ErpConnector", "direction": "read + confirmed WO outbox", "status": CONTRACT_STATUS},
    {"system": "MES", "protocol": "MesSource", "direction": "read", "status": CONTRACT_STATUS},
    {"system": "SCADA / PLC (historian)", "protocol": "ScadaHistorianSource", "direction": "read-only", "status": CONTRACT_STATUS},
    {"system": "OPC UA", "protocol": "OpcUaClient", "direction": "read-only", "status": CONTRACT_STATUS},
    {"system": "MQTT / Sparkplug B", "protocol": "MqttTelemetrySource", "direction": "subscribe-only", "status": CONTRACT_STATUS},
    {"system": "Weighbridge", "protocol": "WeighbridgeSource", "direction": "read", "status": CONTRACT_STATUS},
    {"system": "LIMS", "protocol": "LimsSource", "direction": "read", "status": CONTRACT_STATUS},
    {"system": "GPS / fleet", "protocol": "FleetGpsSource", "direction": "read", "status": CONTRACT_STATUS},
    {"system": "Accounting / HR", "protocol": "AccountingHrSource", "direction": "read (aggregated)", "status": CONTRACT_STATUS},
]
