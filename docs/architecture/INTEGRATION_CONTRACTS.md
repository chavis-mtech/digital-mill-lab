# Integration Contracts (future — contract only)

> **Status: `planned` — CONTRACT ONLY.** Nothing in this repository connects to ERP, MES, SCADA, PLC, OPC UA, MQTT,
> weighbridge, LIMS, GPS/fleet, accounting or HR systems, and nothing implies integration with any real company system.
> Code: `apps/ai-api/app/integrations/contracts.py` (Python `Protocol`s + DTOs + a `SyntheticAdapter` stub that raises `NotImplementedError`).

## Principles for a real deployment

1. **Read-only toward OT.** SCADA/PLC/OPC UA/MQTT adapters subscribe or poll; there are no write/setpoint methods. AI never controls machines.
2. **Adapters map vendor payloads to domain DTOs** (`TagReading`, `WeighEvent`, `LabResult`, `WorkOrderRecord`, …) and then into the existing tables — analytics code does not change.
3. **Time-bounded calls** (`start`, `end`, `since`) so historical playback and live ingestion share one interface.
4. **Outbox for the only write path**: human-confirmed work orders to ERP/CMMS via `submit_confirmed_work_order(record, idempotency_key)`.
5. **Network segmentation**: OT data leaves the plant network through a one-way historian/DMZ replica, never by opening PLCs to the internet.
6. **Discovery first**: tag lists, data owners, sampling rates and data quality are unknown until the 30-day discovery phase.

## Catalog

| System | Protocol (contract) | Direction | Maps to tables | What a real plant would need |
|---|---|---|---|---|
| ERP / CMMS | `ErpConnector` | read + confirmed WO outbox | work_orders, equipment, prices | API access, master-data mapping (equipment codes), approval workflow |
| MES | `MesSource` | read | production_shifts, production_batches | Production order model, shift calendar |
| SCADA / PLC historian | `ScadaHistorianSource` | read-only | sensor_readings, process_hourly | Historian replica in DMZ, tag dictionary, units, sampling |
| OPC UA | `OpcUaClient` | read-only (browse/read) | sensor_readings | Server endpoint, certificates, read-only user, node map |
| MQTT / Sparkplug B | `MqttTelemetrySource` | subscribe-only | sensor_readings | Broker, topic namespace, TLS, ACLs |
| Weighbridge | `WeighbridgeSource` | read | truck_trips, weighbridge_tickets, queue_events | Indicator/software export, ticket numbering, calibration records |
| LIMS | `LimsSource` | read | quality_measurements | Sample-point codes, methods, result units |
| GPS / fleet | `FleetGpsSource` | read | truck_trips (ETA) | Fleet provider API, consent and privacy review |
| Accounting / HR | `AccountingHrSource` | read (aggregated) | cost model inputs | Cost-center mapping; aggregated only, no personal data |

## Status of each element

| Element | Status |
|---|---|
| Protocols + DTOs | implemented as **contracts** (no behaviour) |
| `SyntheticAdapter` | stub (raises `NotImplementedError`) |
| Any real adapter | planned — out of scope for the demo |
