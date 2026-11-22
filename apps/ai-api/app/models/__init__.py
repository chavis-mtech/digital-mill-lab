"""SQLAlchemy models for every domain (SPEC section 8). Import this package to register all tables on Base.metadata.

Frozen by the architect after wave 0: additive changes only, by agreement with the orchestrator.
"""

from app.db.base import Base
from app.models.ai import (
    AiPrediction,
    AiRecommendation,
    Alert,
    AlertStatusChange,
    AnomalyEvent,
    AnomalyStatusChange,
    ModelRegistry,
    RecommendationDecision,
)
from app.models.core import Company, Equipment, Facility, ProcessStage, ProductionLine, Sensor
from app.models.energy import EnergyConsumption
from app.models.logistics import FfbDelivery, Plantation, QueueEvent, Supplier, TruckTrip, WeighbridgeTicket
from app.models.maintenance import MaintenanceEvent, Technician, WorkOrder, WorkOrderStatusHistory
from app.models.platform import (
    AuditLog,
    BusinessScenario,
    CopilotMessage,
    CopilotSession,
    InjectedEvent,
    KbChunk,
    KbDocument,
    Price,
    ScenarioRun,
)
from app.models.production import (
    ByproductOutput,
    CpoOutputLot,
    ProcessHourly,
    ProductionBatch,
    ProductionShift,
    QualityMeasurement,
)
from app.models.readings import SensorReading
from app.models.traceability import BatchInput, FfbBatch, LotComposition

# Tables that must never be serialised by public API handlers.
PRIVATE_TABLES = frozenset({"injected_events"})

# Mutable tables scoped by X-Demo-Session (ADR-006). NULL session_id = seeded shared baseline.
SESSION_SCOPED_TABLES = frozenset(
    {
        "work_orders",
        "work_order_status_history",
        "maintenance_events",
        "anomaly_status_changes",
        "alert_status_changes",
        "recommendation_decisions",
        "business_scenarios",
        "copilot_sessions",
        "copilot_messages",
        "audit_logs",
    }
)

__all__ = [
    "Base",
    "PRIVATE_TABLES",
    "SESSION_SCOPED_TABLES",
    "AiPrediction",
    "AiRecommendation",
    "Alert",
    "AlertStatusChange",
    "AnomalyEvent",
    "AnomalyStatusChange",
    "AuditLog",
    "BatchInput",
    "BusinessScenario",
    "ByproductOutput",
    "Company",
    "CopilotMessage",
    "CopilotSession",
    "CpoOutputLot",
    "EnergyConsumption",
    "Equipment",
    "Facility",
    "FfbBatch",
    "FfbDelivery",
    "InjectedEvent",
    "KbChunk",
    "KbDocument",
    "LotComposition",
    "MaintenanceEvent",
    "ModelRegistry",
    "Plantation",
    "Price",
    "ProcessHourly",
    "ProcessStage",
    "ProductionBatch",
    "ProductionLine",
    "ProductionShift",
    "QualityMeasurement",
    "QueueEvent",
    "RecommendationDecision",
    "ScenarioRun",
    "Sensor",
    "SensorReading",
    "Supplier",
    "Technician",
    "TruckTrip",
    "WeighbridgeTicket",
    "WorkOrder",
    "WorkOrderStatusHistory",
]
