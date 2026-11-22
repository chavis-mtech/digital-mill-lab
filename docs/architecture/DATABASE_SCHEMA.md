# Database Schema

> **GENERATED** from `apps/ai-api/app/models/**` by `make docs` (`python -m app.db.schema_doc`). Do not edit by hand.
> Portable SQLAlchemy 2.0 models: SQLite (default) and PostgreSQL (via `DATABASE_URL`). Alembic revision `0001` creates the same schema
> (verified by `tests/test_migrations.py`). All timestamps are stored as UTC (`UTCDateTime`).

**44 tables.** Private (never exposed via API): `injected_events`. Session-scoped (ADR-006, `session_id` NULL = seeded baseline): `alert_status_changes, anomaly_status_changes, audit_logs, business_scenarios, copilot_messages, copilot_sessions, maintenance_events, recommendation_decisions, work_order_status_history, work_orders`.

## Domain `core` (`app/models/core.py`)

### `companies`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `code` | VARCHAR(32) | no | unique |  |
| `name` | VARCHAR(200) | no |  |  |
| `is_fictional` | BOOLEAN | no |  | 1 |
| `data_kind` | VARCHAR(32) | no |  | synthetic |

Unique: `(code)`

Checks:
- `is_fictional = true`

### `equipment`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `facility_id` | INTEGER | no | FK -> `facilities.id`, indexed |  |
| `line_id` | INTEGER | yes | FK -> `production_lines.id`, indexed |  |
| `process_stage_id` | INTEGER | no | FK -> `process_stages.id`, indexed |  |
| `code` | VARCHAR(32) | no | unique |  |
| `name` | VARCHAR(200) | no |  |  |
| `equipment_type` | VARCHAR(32) | no |  |  |
| `manufacturer` | VARCHAR(100) | yes |  |  |
| `install_date` | DATE | yes |  |  |
| `criticality` | VARCHAR(1) | no |  | B |
| `rated_power_kw` | FLOAT | yes |  |  |
| `rated_capacity` | FLOAT | yes |  |  |
| `rated_capacity_unit` | VARCHAR(16) | yes |  |  |
| `is_active` | BOOLEAN | no |  | 1 |
| `data_kind` | VARCHAR(32) | no |  | synthetic |

Unique: `(code)`

Checks:
- `rated_power_kw IS NULL OR rated_power_kw >= 0`
- `equipment_type IN ('boiler', 'sterilizer', 'conveyor', 'thresher', 'digester', 'screw_press', 'pump', 'motor', 'generator', 'turbine', 'centrifuge', 'clarifier_tank', 'storage_tank', 'weighbridge', 'kernel_plant', 'other_rotating')`
- `criticality IN ('A', 'B', 'C')`

### `facilities`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `company_id` | INTEGER | no | FK -> `companies.id`, indexed |  |
| `code` | VARCHAR(32) | no | unique |  |
| `name` | VARCHAR(200) | no |  |  |
| `facility_type` | VARCHAR(32) | no |  | palm_oil_mill |
| `capacity_tph` | FLOAT | no |  |  |
| `timezone` | VARCHAR(64) | no |  | Asia/Bangkok |
| `region` | VARCHAR(100) | yes |  |  |
| `data_kind` | VARCHAR(32) | no |  | synthetic |

Unique: `(code)`

Checks:
- `capacity_tph > 0`

### `process_stages`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `facility_id` | INTEGER | no | FK -> `facilities.id`, indexed |  |
| `code` | VARCHAR(32) | no |  |  |
| `name_en` | VARCHAR(100) | no |  |  |
| `name_th` | VARCHAR(100) | no |  |  |
| `sequence` | INTEGER | no |  |  |
| `kind` | VARCHAR(16) | no |  | main |
| `description` | TEXT | yes |  |  |

Unique: `(facility_id, code)`

Checks:
- `kind IN ('main', 'support')`
- `code IN ('FFB_RECEPTION', 'STERILIZATION', 'THRESHING', 'DIGESTION', 'PRESSING', 'CLARIFICATION', 'CPO_STORAGE', 'KERNEL_RECOVERY', 'BOILER_STEAM', 'POWER', 'WATER_TREATMENT', 'POME_TREATMENT')`

### `production_lines`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `facility_id` | INTEGER | no | FK -> `facilities.id`, indexed |  |
| `code` | VARCHAR(32) | no | unique |  |
| `name` | VARCHAR(200) | no |  |  |
| `capacity_tph` | FLOAT | no |  |  |

Unique: `(code)`

Checks:
- `capacity_tph > 0`

### `sensors`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `equipment_id` | INTEGER | no | FK -> `equipment.id`, indexed |  |
| `code` | VARCHAR(48) | no | unique |  |
| `name` | VARCHAR(200) | no |  |  |
| `sensor_type` | VARCHAR(24) | no |  |  |
| `unit` | VARCHAR(16) | no |  |  |
| `normal_min` | FLOAT | yes |  |  |
| `normal_max` | FLOAT | yes |  |  |
| `warn_limit` | FLOAT | yes |  |  |
| `crit_limit` | FLOAT | yes |  |  |
| `low_is_bad` | BOOLEAN | no |  | 0 |
| `sampling_seconds` | INTEGER | no |  | 600 |
| `data_kind` | VARCHAR(32) | no |  | synthetic |

Unique: `(code)`

Checks:
- `sampling_seconds IS NULL OR (sampling_seconds >= 1 AND sampling_seconds <= 86400)`
- `normal_min IS NULL OR normal_max IS NULL OR normal_min <= normal_max`
- `sensor_type IN ('temperature', 'vibration', 'current', 'pressure', 'rpm', 'running_hours', 'load', 'state', 'flow', 'level')`

## Domain `readings` (`app/models/readings.py`)

### `sensor_readings`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | BIGINT | no | PK |  |
| `sensor_id` | INTEGER | no | FK -> `sensors.id` |  |
| `ts` | DATETIME | no |  |  |
| `value` | FLOAT | no |  |  |
| `quality` | VARCHAR(12) | no |  | good |

Unique: `(sensor_id, ts)`

Checks:
- `quality IN ('good', 'uncertain', 'bad')`

## Domain `production` (`app/models/production.py`)

### `byproduct_outputs`

Kernel and by-product/waste outputs per processing batch (mass balance relative to FFB).

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `production_batch_id` | INTEGER | no | FK -> `production_batches.id`, indexed |  |
| `product` | VARCHAR(16) | no |  |  |
| `quantity_t` | FLOAT | no |  |  |
| `pct_of_ffb` | FLOAT | yes |  |  |
| `destination` | VARCHAR(32) | yes |  |  |
| `data_kind` | VARCHAR(32) | no |  | synthetic_actual |

Unique: `(production_batch_id, product)`

Checks:
- `product IN ('kernel', 'shell', 'fibre', 'efb', 'pome', 'decanter_cake', 'boiler_ash')`
- `quantity_t IS NULL OR quantity_t >= 0`
- `pct_of_ffb IS NULL OR (pct_of_ffb >= 0 AND pct_of_ffb <= 100)`

### `cpo_output_lots`

A CPO storage-tank lot (fill window). Composition by processing batch lives in lot_compositions.

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `code` | VARCHAR(40) | no | unique |  |
| `facility_id` | INTEGER | no | FK -> `facilities.id`, indexed |  |
| `tank_code` | VARCHAR(16) | no |  |  |
| `fill_start_ts` | DATETIME | no |  |  |
| `fill_end_ts` | DATETIME | yes |  |  |
| `quantity_t` | FLOAT | no |  |  |
| `ffa_pct` | FLOAT | yes |  |  |
| `moisture_pct` | FLOAT | yes |  |  |
| `dirt_pct` | FLOAT | yes |  |  |
| `dobi` | FLOAT | yes |  |  |
| `status` | VARCHAR(16) | no |  | in_storage |
| `dispatched_at` | DATETIME | yes |  |  |
| `data_kind` | VARCHAR(32) | no |  | synthetic_actual |

Unique: `(code)`

Checks:
- `dobi IS NULL OR (dobi >= 0 AND dobi <= 6)`
- `ffa_pct IS NULL OR (ffa_pct >= 0 AND ffa_pct <= 20)`
- `quantity_t >= 0`
- `status IN ('filling', 'in_storage', 'dispatched')`
- `moisture_pct IS NULL OR (moisture_pct >= 0 AND moisture_pct <= 5)`
- `dirt_pct IS NULL OR (dirt_pct >= 0 AND dirt_pct <= 5)`

### `process_hourly`

Hourly mill state: one row per facility/line/hour. Drives the process twin and production analytics.

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `facility_id` | INTEGER | no | FK -> `facilities.id` |  |
| `line_id` | INTEGER | yes | FK -> `production_lines.id` |  |
| `ts` | DATETIME | no |  |  |
| `running_minutes` | FLOAT | no |  | 60 |
| `downtime_min` | FLOAT | no |  | 0 |
| `ffb_received_t` | FLOAT | no |  | 0 |
| `ffb_processed_t` | FLOAT | no |  | 0 |
| `throughput_tph` | FLOAT | no |  | 0 |
| `ffb_waiting_t` | FLOAT | yes |  |  |
| `avg_wait_to_process_h` | FLOAT | yes |  |  |
| `sterilizer_cycles` | INTEGER | yes |  |  |
| `sterilizer_cycle_min` | FLOAT | yes |  |  |
| `steam_pressure_bar` | FLOAT | yes |  |  |
| `boiler_steam_t` | FLOAT | yes |  |  |
| `digester_temp_c` | FLOAT | yes |  |  |
| `press_load_a` | FLOAT | yes |  |  |
| `press_cone_pressure_bar` | FLOAT | yes |  |  |
| `clarifier_temp_c` | FLOAT | yes |  |  |
| `oil_loss_press_fibre_pct` | FLOAT | yes |  |  |
| `oil_loss_efb_pct` | FLOAT | yes |  |  |
| `oil_loss_sludge_pct` | FLOAT | yes |  |  |
| `oil_loss_nut_pct` | FLOAT | yes |  |  |
| `oil_loss_total_pct` | FLOAT | yes |  |  |
| `cpo_t` | FLOAT | no |  | 0 |
| `kernel_t` | FLOAT | no |  | 0 |
| `oer_pct` | FLOAT | yes |  |  |
| `ker_pct` | FLOAT | yes |  |  |
| `ffb_ripe_pct` | FLOAT | yes |  |  |
| `data_kind` | VARCHAR(32) | no |  | synthetic_actual |

Unique: `(facility_id, line_id, ts)`

Checks:
- `ffb_ripe_pct IS NULL OR (ffb_ripe_pct >= 0 AND ffb_ripe_pct <= 100)`
- `cpo_t <= ffb_processed_t OR ffb_processed_t = 0`
- `oer_pct IS NULL OR (oer_pct >= 0 AND oer_pct <= 35)`
- `steam_pressure_bar IS NULL OR (steam_pressure_bar >= 0 AND steam_pressure_bar <= 10)`
- `running_minutes IS NULL OR (running_minutes >= 0 AND running_minutes <= 60)`
- `throughput_tph IS NULL OR throughput_tph >= 0`
- `ker_pct IS NULL OR (ker_pct >= 0 AND ker_pct <= 15)`
- `digester_temp_c IS NULL OR (digester_temp_c >= 0 AND digester_temp_c <= 150)`
- `cpo_t IS NULL OR cpo_t >= 0`
- `oil_loss_total_pct IS NULL OR (oil_loss_total_pct >= 0 AND oil_loss_total_pct <= 10)`
- `kernel_t IS NULL OR kernel_t >= 0`
- `ffb_processed_t IS NULL OR ffb_processed_t >= 0`
- `downtime_min IS NULL OR (downtime_min >= 0 AND downtime_min <= 60)`

### `production_batches`

A processing batch (e.g. one sterilizer-cycle group / time block) fed by one or more FFB batches.

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `code` | VARCHAR(40) | no | unique |  |
| `facility_id` | INTEGER | no | FK -> `facilities.id`, indexed |  |
| `line_id` | INTEGER | yes | FK -> `production_lines.id`, indexed |  |
| `shift_id` | INTEGER | yes | FK -> `production_shifts.id`, indexed |  |
| `start_ts` | DATETIME | no | indexed |  |
| `end_ts` | DATETIME | no |  |  |
| `ffb_input_t` | FLOAT | no |  |  |
| `cpo_t` | FLOAT | no |  |  |
| `kernel_t` | FLOAT | no |  |  |
| `oer_pct` | FLOAT | no |  |  |
| `ker_pct` | FLOAT | no |  |  |
| `sterilizer_cycle_min` | FLOAT | yes |  |  |
| `trace_method` | VARCHAR(16) | no |  | mass_balance |
| `status` | VARCHAR(16) | no |  | completed |
| `data_kind` | VARCHAR(32) | no |  | synthetic_actual |

Unique: `(code)`

Checks:
- `cpo_t >= 0 AND cpo_t <= ffb_input_t`
- `trace_method IN ('lot_based', 'mass_balance')`
- `kernel_t >= 0 AND kernel_t <= ffb_input_t`
- `status IN ('in_progress', 'completed', 'aborted')`
- `ffb_input_t > 0`
- `oer_pct IS NULL OR (oer_pct >= 0 AND oer_pct <= 35)`
- `end_ts > start_ts`
- `ker_pct IS NULL OR (ker_pct >= 0 AND ker_pct <= 15)`

### `production_shifts`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `facility_id` | INTEGER | no | FK -> `facilities.id`, indexed |  |
| `business_date` | DATE | no | indexed |  |
| `shift_code` | VARCHAR(4) | no |  |  |
| `start_ts` | DATETIME | no |  |  |
| `end_ts` | DATETIME | no |  |  |
| `ffb_processed_t` | FLOAT | no |  | 0 |
| `cpo_t` | FLOAT | no |  | 0 |
| `kernel_t` | FLOAT | no |  | 0 |
| `oer_pct` | FLOAT | yes |  |  |
| `ker_pct` | FLOAT | yes |  |  |
| `operating_hours` | FLOAT | no |  | 0 |
| `downtime_min` | FLOAT | no |  | 0 |
| `supervisor_code` | VARCHAR(32) | yes |  |  |
| `data_kind` | VARCHAR(32) | no |  | synthetic_actual |

Unique: `(facility_id, business_date, shift_code)`

Checks:
- `operating_hours IS NULL OR (operating_hours >= 0 AND operating_hours <= 12)`
- `downtime_min IS NULL OR downtime_min >= 0`
- `ffb_processed_t IS NULL OR ffb_processed_t >= 0`
- `oer_pct IS NULL OR (oer_pct >= 0 AND oer_pct <= 35)`
- `cpo_t IS NULL OR cpo_t >= 0`
- `ker_pct IS NULL OR (ker_pct >= 0 AND ker_pct <= 15)`
- `kernel_t IS NULL OR kernel_t >= 0`
- `end_ts > start_ts`

### `quality_measurements`

Lab / QC results (LIMS-like). Linked to whichever entity was sampled.

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `facility_id` | INTEGER | no | FK -> `facilities.id` |  |
| `sample_ts` | DATETIME | no | indexed |  |
| `sample_point` | VARCHAR(32) | no |  |  |
| `parameter` | VARCHAR(32) | no |  |  |
| `value` | FLOAT | no |  |  |
| `unit` | VARCHAR(16) | no |  |  |
| `production_batch_id` | INTEGER | yes | FK -> `production_batches.id`, indexed |  |
| `cpo_lot_id` | INTEGER | yes | FK -> `cpo_output_lots.id`, indexed |  |
| `ffb_delivery_id` | INTEGER | yes | FK -> `ffb_deliveries.id`, indexed |  |
| `method` | VARCHAR(64) | yes |  |  |
| `notes` | TEXT | yes |  |  |
| `data_kind` | VARCHAR(32) | no |  | synthetic_actual |

Indexes: `ix_quality_point_param_ts(sample_point, parameter, sample_ts)`

## Domain `logistics` (`app/models/logistics.py`)

### `ffb_deliveries`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `code` | VARCHAR(40) | no | unique |  |
| `facility_id` | INTEGER | no | FK -> `facilities.id`, indexed |  |
| `supplier_id` | INTEGER | no | FK -> `suppliers.id`, indexed |  |
| `plantation_id` | INTEGER | yes | FK -> `plantations.id`, indexed |  |
| `truck_trip_id` | INTEGER | no | FK -> `truck_trips.id`, unique |  |
| `ticket_id` | INTEGER | yes | FK -> `weighbridge_tickets.id`, unique |  |
| `business_date` | DATE | no | indexed |  |
| `received_ts` | DATETIME | no |  |  |
| `net_kg` | INTEGER | no |  |  |
| `grade` | VARCHAR(8) | no |  |  |
| `ripe_pct` | FLOAT | yes |  |  |
| `unripe_pct` | FLOAT | yes |  |  |
| `overripe_pct` | FLOAT | yes |  |  |
| `empty_bunch_pct` | FLOAT | yes |  |  |
| `long_stalk_pct` | FLOAT | yes |  |  |
| `deduction_pct` | FLOAT | no |  | 0 |
| `accepted_kg` | INTEGER | no |  |  |
| `harvest_to_mill_h` | FLOAT | yes |  |  |
| `data_kind` | VARCHAR(32) | no |  | synthetic_actual |

Unique: `(truck_trip_id)`; `(ticket_id)`; `(code)`

Checks:
- `net_kg > 0`
- `accepted_kg >= 0 AND accepted_kg <= net_kg`
- `ripe_pct IS NULL OR (ripe_pct >= 0 AND ripe_pct <= 100)`
- `unripe_pct IS NULL OR (unripe_pct >= 0 AND unripe_pct <= 100)`
- `overripe_pct IS NULL OR (overripe_pct >= 0 AND overripe_pct <= 100)`
- `empty_bunch_pct IS NULL OR (empty_bunch_pct >= 0 AND empty_bunch_pct <= 100)`
- `long_stalk_pct IS NULL OR (long_stalk_pct >= 0 AND long_stalk_pct <= 100)`
- `deduction_pct IS NULL OR (deduction_pct >= 0 AND deduction_pct <= 100)`
- `harvest_to_mill_h IS NULL OR harvest_to_mill_h >= 0`
- `grade IN ('A', 'B', 'C', 'reject')`

### `plantations`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `supplier_id` | INTEGER | no | FK -> `suppliers.id`, indexed |  |
| `code` | VARCHAR(32) | no | unique |  |
| `name` | VARCHAR(200) | no |  |  |
| `area_ha` | FLOAT | yes |  |  |
| `district` | VARCHAR(100) | yes |  |  |
| `lat` | FLOAT | yes |  |  |
| `lon` | FLOAT | yes |  |  |
| `planting_year` | INTEGER | yes |  |  |
| `sustainability_json` | TEXT | yes |  |  |
| `data_kind` | VARCHAR(32) | no |  | synthetic |

Unique: `(code)`

Checks:
- `lat IS NULL OR (lat >= -90 AND lat <= 90)`
- `area_ha IS NULL OR area_ha >= 0`
- `lon IS NULL OR (lon >= -180 AND lon <= 180)`

### `queue_events`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `truck_trip_id` | INTEGER | no | FK -> `truck_trips.id`, indexed |  |
| `ts` | DATETIME | no |  |  |
| `event_type` | VARCHAR(20) | no |  |  |
| `queue_length` | INTEGER | yes |  |  |
| `location` | VARCHAR(32) | yes |  |  |

Checks:
- `queue_length IS NULL OR queue_length >= 0`
- `event_type IN ('arrived', 'queued', 'called', 'weigh_in', 'graded', 'unload_start', 'unload_end', 'weigh_out', 'exited')`

### `suppliers`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `code` | VARCHAR(32) | no | unique |  |
| `name` | VARCHAR(200) | no |  |  |
| `supplier_type` | VARCHAR(16) | no |  |  |
| `province` | VARCHAR(100) | yes |  |  |
| `registered_on` | DATE | yes |  |  |
| `is_active` | BOOLEAN | no |  | 1 |
| `sustainability_status` | VARCHAR(24) | no |  | not_assessed |
| `quality_tier` | VARCHAR(8) | yes |  |  |
| `data_kind` | VARCHAR(32) | no |  | synthetic |

Unique: `(code)`

Checks:
- `supplier_type IN ('smallholder', 'dealer', 'estate', 'own_estate')`
- `sustainability_status IN ('not_assessed', 'data_collected', 'gap_identified', 'documented')`

### `truck_trips`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `code` | VARCHAR(40) | no | unique |  |
| `facility_id` | INTEGER | no | FK -> `facilities.id`, indexed |  |
| `supplier_id` | INTEGER | no | FK -> `suppliers.id`, indexed |  |
| `plate_masked` | VARCHAR(16) | no |  |  |
| `truck_type` | VARCHAR(16) | yes |  |  |
| `arrival_ts` | DATETIME | no | indexed |  |
| `queue_start_ts` | DATETIME | yes |  |  |
| `weigh_in_ts` | DATETIME | yes |  |  |
| `grading_ts` | DATETIME | yes |  |  |
| `unload_start_ts` | DATETIME | yes |  |  |
| `unload_end_ts` | DATETIME | yes |  |  |
| `weigh_out_ts` | DATETIME | yes |  |  |
| `exit_ts` | DATETIME | yes |  |  |
| `status` | VARCHAR(16) | no |  | exited |
| `data_kind` | VARCHAR(32) | no |  | synthetic_actual |

Unique: `(code)`

Checks:
- `weigh_in_ts IS NULL OR weigh_in_ts >= arrival_ts`
- `status IN ('arriving', 'queued', 'weighing_in', 'grading', 'unloading', 'weighing_out', 'exited')`
- `exit_ts IS NULL OR exit_ts >= arrival_ts`

### `weighbridge_tickets`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `ticket_no` | VARCHAR(40) | no | unique |  |
| `truck_trip_id` | INTEGER | no | FK -> `truck_trips.id`, unique |  |
| `bridge_code` | VARCHAR(16) | no |  |  |
| `weigh_in_ts` | DATETIME | no |  |  |
| `weigh_out_ts` | DATETIME | yes |  |  |
| `gross_kg` | INTEGER | no |  |  |
| `tare_kg` | INTEGER | yes |  |  |
| `net_kg` | INTEGER | yes |  |  |
| `operator_code` | VARCHAR(32) | yes |  |  |
| `data_kind` | VARCHAR(32) | no |  | synthetic_actual |

Unique: `(truck_trip_id)`; `(ticket_no)`

Checks:
- `weigh_out_ts IS NULL OR weigh_out_ts >= weigh_in_ts`
- `tare_kg IS NULL OR (tare_kg > 0 AND tare_kg < gross_kg)`
- `gross_kg > 0`
- `net_kg IS NULL OR net_kg = gross_kg - tare_kg`

## Domain `traceability` (`app/models/traceability.py`)

### `batch_inputs`

Many-to-many FFB batch -> processing batch with mass share (supports multi-supplier mixing).

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `ffb_batch_id` | INTEGER | no | FK -> `ffb_batches.id`, indexed |  |
| `production_batch_id` | INTEGER | no | FK -> `production_batches.id`, indexed |  |
| `mass_kg` | FLOAT | no |  |  |
| `mass_share` | FLOAT | no |  |  |
| `trace_method` | VARCHAR(16) | no |  | mass_balance |

Unique: `(ffb_batch_id, production_batch_id)`

Checks:
- `trace_method IN ('lot_based', 'mass_balance')`
- `mass_kg > 0`
- `mass_share > 0 AND mass_share <= 1`

### `ffb_batches`

A graded receiving batch on the loading ramp (normally 1 per delivery; split deliveries allowed).

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `code` | VARCHAR(40) | no | unique |  |
| `delivery_id` | INTEGER | no | FK -> `ffb_deliveries.id`, indexed |  |
| `facility_id` | INTEGER | no | FK -> `facilities.id`, indexed |  |
| `received_ts` | DATETIME | no |  |  |
| `mass_kg` | INTEGER | no |  |  |
| `grade` | VARCHAR(8) | no |  |  |
| `ramp_code` | VARCHAR(16) | yes |  |  |
| `status` | VARCHAR(16) | no |  | processed |
| `processed_start_ts` | DATETIME | yes |  |  |
| `data_kind` | VARCHAR(32) | no |  | synthetic_actual |

Unique: `(code)`

Checks:
- `status IN ('waiting', 'partially_processed', 'processed', 'rejected')`
- `grade IN ('A', 'B', 'C', 'reject')`
- `mass_kg > 0`

### `lot_compositions`

Processing batch -> CPO output lot attribution.

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `cpo_lot_id` | INTEGER | no | FK -> `cpo_output_lots.id`, indexed |  |
| `production_batch_id` | INTEGER | no | FK -> `production_batches.id`, indexed |  |
| `cpo_t` | FLOAT | no |  |  |
| `share` | FLOAT | no |  |  |
| `trace_method` | VARCHAR(16) | no |  | mass_balance |

Unique: `(cpo_lot_id, production_batch_id)`

Checks:
- `share > 0 AND share <= 1`
- `trace_method IN ('lot_based', 'mass_balance')`
- `cpo_t >= 0`

## Domain `maintenance` (`app/models/maintenance.py`)

### `maintenance_events`

Maintenance history (seeded) and records written when a work order is resolved.

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `equipment_id` | INTEGER | no | FK -> `equipment.id`, indexed |  |
| `work_order_id` | INTEGER | yes | FK -> `work_orders.id`, indexed |  |
| `session_id` | VARCHAR(36) | yes | indexed |  |
| `event_type` | VARCHAR(16) | no |  |  |
| `start_ts` | DATETIME | no | indexed |  |
| `end_ts` | DATETIME | yes |  |  |
| `downtime_min` | FLOAT | no |  | 0 |
| `planned` | BOOLEAN | no |  | 0 |
| `description` | TEXT | yes |  |  |
| `parts_cost_thb` | FLOAT | yes |  |  |
| `labour_cost_thb` | FLOAT | yes |  |  |
| `technician_id` | INTEGER | yes | FK -> `technicians.id` |  |
| `data_kind` | VARCHAR(32) | no |  | synthetic_actual |

Checks:
- `end_ts IS NULL OR end_ts >= start_ts`
- `event_type IN ('breakdown', 'corrective', 'preventive', 'inspection', 'lubrication', 'calibration', 'overhaul')`
- `downtime_min IS NULL OR downtime_min >= 0`
- `parts_cost_thb IS NULL OR parts_cost_thb >= 0`
- `labour_cost_thb IS NULL OR labour_cost_thb >= 0`

### `technicians`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `code` | VARCHAR(32) | no | unique |  |
| `display_name` | VARCHAR(100) | no |  |  |
| `skill` | VARCHAR(16) | no |  |  |
| `shift_code` | VARCHAR(4) | yes |  |  |
| `is_active` | BOOLEAN | no |  | 1 |
| `data_kind` | VARCHAR(32) | no |  | synthetic |

Unique: `(code)`

Checks:
- `skill IN ('mechanical', 'electrical', 'instrument', 'general')`

### `work_order_status_history`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `work_order_id` | INTEGER | no | FK -> `work_orders.id`, indexed |  |
| `session_id` | VARCHAR(36) | yes | indexed |  |
| `from_status` | VARCHAR(16) | yes |  |  |
| `to_status` | VARCHAR(16) | no |  |  |
| `actor_role` | VARCHAR(32) | no |  |  |
| `changed_at` | DATETIME | no |  |  |
| `note` | TEXT | yes |  |  |

Checks:
- `actor_role IN ('executive', 'factory_manager', 'production_engineer', 'maintenance_engineer', 'logistics_officer', 'ai_analyst', 'system_admin', 'public_viewer')`
- `from_status IS NULL OR from_status IN ('open', 'assigned', 'in_progress', 'on_hold', 'resolved', 'closed', 'cancelled')`
- `to_status IN ('open', 'assigned', 'in_progress', 'on_hold', 'resolved', 'closed', 'cancelled')`

### `work_orders`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `code` | VARCHAR(40) | no | unique |  |
| `session_id` | VARCHAR(36) | yes | indexed |  |
| `cloned_from_id` | INTEGER | yes | FK -> `work_orders.id` |  |
| `equipment_id` | INTEGER | no | FK -> `equipment.id`, indexed |  |
| `title` | VARCHAR(200) | no |  |  |
| `description` | TEXT | yes |  |  |
| `priority` | VARCHAR(8) | no |  | medium |
| `status` | VARCHAR(16) | no |  | open |
| `source_type` | VARCHAR(16) | no |  | manual |
| `alert_id` | INTEGER | yes | FK -> `alerts.id`, indexed |  |
| `recommendation_id` | INTEGER | yes | FK -> `ai_recommendations.id`, indexed |  |
| `anomaly_event_id` | INTEGER | yes | FK -> `anomaly_events.id`, indexed |  |
| `assigned_technician_id` | INTEGER | yes | FK -> `technicians.id`, indexed |  |
| `created_by_role` | VARCHAR(32) | no |  |  |
| `created_at` | DATETIME | no |  |  |
| `demo_as_of` | DATETIME | yes |  |  |
| `due_at` | DATETIME | yes |  |  |
| `resolved_at` | DATETIME | yes |  |  |
| `resolution_notes` | TEXT | yes |  |  |
| `estimated_downtime_h` | FLOAT | yes |  |  |
| `data_kind` | VARCHAR(32) | no |  | synthetic |

Unique: `(code)`

Indexes: `ix_work_orders_session_status(session_id, status)`

Checks:
- `source_type IN ('alert', 'recommendation', 'manual', 'preventive')`
- `priority IN ('low', 'medium', 'high', 'urgent')`
- `created_by_role IN ('executive', 'factory_manager', 'production_engineer', 'maintenance_engineer', 'logistics_officer', 'ai_analyst', 'system_admin', 'public_viewer')`
- `status IN ('open', 'assigned', 'in_progress', 'on_hold', 'resolved', 'closed', 'cancelled')`
- `estimated_downtime_h IS NULL OR estimated_downtime_h >= 0`

## Domain `energy` (`app/models/energy.py`)

### `energy_consumption`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `facility_id` | INTEGER | no | FK -> `facilities.id` |  |
| `process_stage_id` | INTEGER | yes | FK -> `process_stages.id` |  |
| `ts` | DATETIME | no | indexed |  |
| `electricity_kwh` | FLOAT | no |  | 0 |
| `grid_import_kwh` | FLOAT | yes |  |  |
| `self_generated_kwh` | FLOAT | yes |  |  |
| `steam_t` | FLOAT | yes |  |  |
| `boiler_fibre_t` | FLOAT | yes |  |  |
| `boiler_shell_t` | FLOAT | yes |  |  |
| `diesel_l` | FLOAT | yes |  |  |
| `water_m3` | FLOAT | yes |  |  |
| `ffb_processed_t` | FLOAT | yes |  |  |
| `idle_kwh` | FLOAT | yes |  |  |
| `cost_thb` | FLOAT | yes |  |  |
| `data_kind` | VARCHAR(32) | no |  | synthetic_actual |

Unique: `(facility_id, process_stage_id, ts)`

Checks:
- `steam_t IS NULL OR steam_t >= 0`
- `idle_kwh IS NULL OR idle_kwh >= 0`
- `diesel_l IS NULL OR diesel_l >= 0`
- `idle_kwh IS NULL OR idle_kwh <= electricity_kwh`
- `grid_import_kwh IS NULL OR grid_import_kwh >= 0`
- `water_m3 IS NULL OR water_m3 >= 0`
- `self_generated_kwh IS NULL OR self_generated_kwh >= 0`
- `electricity_kwh IS NULL OR electricity_kwh >= 0`
- `ffb_processed_t IS NULL OR ffb_processed_t >= 0`

## Domain `ai` (`app/models/ai.py`)

### `ai_predictions`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `model_id` | INTEGER | no | FK -> `model_registry.id`, indexed |  |
| `target` | VARCHAR(32) | no |  |  |
| `entity_type` | VARCHAR(32) | no |  |  |
| `entity_id` | INTEGER | yes |  |  |
| `target_ts` | DATETIME | no |  |  |
| `made_at` | DATETIME | no |  |  |
| `horizon_minutes` | INTEGER | yes |  |  |
| `value` | FLOAT | no |  |  |
| `lower` | FLOAT | yes |  |  |
| `upper` | FLOAT | yes |  |  |
| `unit` | VARCHAR(16) | yes |  |  |
| `explanation_json` | TEXT | yes |  |  |
| `data_kind` | VARCHAR(32) | no |  | forecast |

Indexes: `ix_ai_predictions_target_ts(target, target_ts)`

Checks:
- `lower IS NULL OR upper IS NULL OR lower <= upper`

### `ai_recommendations`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `code` | VARCHAR(40) | no | unique |  |
| `rec_type` | VARCHAR(32) | no |  |  |
| `title` | VARCHAR(200) | no |  |  |
| `rationale` | TEXT | no |  |  |
| `evidence_json` | TEXT | yes |  |  |
| `equipment_id` | INTEGER | yes | FK -> `equipment.id`, indexed |  |
| `process_stage_id` | INTEGER | yes | FK -> `process_stages.id`, indexed |  |
| `anomaly_event_id` | INTEGER | yes | FK -> `anomaly_events.id`, indexed |  |
| `model_id` | INTEGER | yes | FK -> `model_registry.id` |  |
| `priority` | VARCHAR(10) | no |  | medium |
| `risk_score` | FLOAT | yes |  |  |
| `advisory` | BOOLEAN | no |  | 1 |
| `status` | VARCHAR(16) | no |  | proposed |
| `created_at` | DATETIME | no |  |  |
| `data_kind` | VARCHAR(32) | no |  | synthetic |

Unique: `(code)`

Checks:
- `advisory = true`
- `status IN ('proposed', 'approved', 'rejected', 'superseded')`
- `risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)`
- `priority IN ('info', 'low', 'medium', 'high', 'critical')`

### `alert_status_changes`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `alert_id` | INTEGER | no | FK -> `alerts.id`, indexed |  |
| `session_id` | VARCHAR(36) | yes | indexed |  |
| `from_status` | VARCHAR(16) | yes |  |  |
| `to_status` | VARCHAR(16) | no |  |  |
| `actor_role` | VARCHAR(32) | no |  |  |
| `note` | TEXT | yes |  |  |
| `changed_at` | DATETIME | no |  |  |

Checks:
- `actor_role IN ('executive', 'factory_manager', 'production_engineer', 'maintenance_engineer', 'logistics_officer', 'ai_analyst', 'system_admin', 'public_viewer')`
- `to_status IN ('new', 'acknowledged', 'in_progress', 'resolved', 'dismissed')`

### `alerts`

Unified alert table linking modules (production, equipment, energy, logistics, quality).

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `code` | VARCHAR(40) | no | unique |  |
| `source` | VARCHAR(24) | no |  |  |
| `module` | VARCHAR(16) | no |  |  |
| `severity` | VARCHAR(10) | no |  |  |
| `status` | VARCHAR(16) | no |  | new |
| `title` | VARCHAR(200) | no |  |  |
| `message` | TEXT | no |  |  |
| `raised_at` | DATETIME | no | indexed |  |
| `resolved_at` | DATETIME | yes |  |  |
| `facility_id` | INTEGER | yes | FK -> `facilities.id` |  |
| `equipment_id` | INTEGER | yes | FK -> `equipment.id`, indexed |  |
| `process_stage_id` | INTEGER | yes | FK -> `process_stages.id`, indexed |  |
| `anomaly_event_id` | INTEGER | yes | FK -> `anomaly_events.id`, indexed |  |
| `recommendation_id` | INTEGER | yes | FK -> `ai_recommendations.id` |  |
| `supplier_id` | INTEGER | yes | FK -> `suppliers.id` |  |
| `truck_trip_id` | INTEGER | yes | FK -> `truck_trips.id` |  |
| `business_impact_json` | TEXT | yes |  |  |
| `evidence_json` | TEXT | yes |  |  |
| `scenario_code` | VARCHAR(32) | yes | indexed |  |
| `data_kind` | VARCHAR(32) | no |  | synthetic |

Unique: `(code)`

Checks:
- `scenario_code IS NULL OR scenario_code IN ('NORMAL_DAY', 'OER_DEGRADATION', 'PRESS_VIBRATION_ANOMALY', 'STEAM_PRESSURE_DEVIATION', 'TRUCK_QUEUE_CONGESTION', 'ENERGY_EFFICIENCY_DROP')`
- `source IN ('production_anomaly', 'equipment_anomaly', 'energy_anomaly', 'logistics_anomaly', 'quality', 'rule')`
- `status IN ('new', 'acknowledged', 'in_progress', 'resolved', 'dismissed')`
- `severity IN ('info', 'low', 'medium', 'high', 'critical')`
- `module IN ('production', 'maintenance', 'energy', 'logistics', 'quality')`
- `resolved_at IS NULL OR resolved_at >= raised_at`

### `anomaly_events`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `code` | VARCHAR(40) | no | unique |  |
| `detector` | VARCHAR(48) | no |  |  |
| `model_id` | INTEGER | yes | FK -> `model_registry.id` |  |
| `domain` | VARCHAR(16) | no |  |  |
| `entity_type` | VARCHAR(32) | no |  |  |
| `entity_id` | INTEGER | yes |  |  |
| `equipment_id` | INTEGER | yes | FK -> `equipment.id`, indexed |  |
| `process_stage_id` | INTEGER | yes | FK -> `process_stages.id`, indexed |  |
| `start_ts` | DATETIME | no | indexed |  |
| `end_ts` | DATETIME | yes |  |  |
| `peak_ts` | DATETIME | yes |  |  |
| `score` | FLOAT | no |  |  |
| `severity` | VARCHAR(10) | no |  |  |
| `evidence_json` | TEXT | yes |  |  |
| `contributing_json` | TEXT | yes |  |  |
| `status` | VARCHAR(16) | no |  | new |
| `scenario_code` | VARCHAR(32) | yes |  |  |
| `data_kind` | VARCHAR(32) | no |  | synthetic |

Unique: `(code)`

Checks:
- `status IN ('new', 'acknowledged', 'verified', 'dismissed')`
- `scenario_code IS NULL OR scenario_code IN ('NORMAL_DAY', 'OER_DEGRADATION', 'PRESS_VIBRATION_ANOMALY', 'STEAM_PRESSURE_DEVIATION', 'TRUCK_QUEUE_CONGESTION', 'ENERGY_EFFICIENCY_DROP')`
- `score IS NULL OR (score >= 0 AND score <= 1)`
- `end_ts IS NULL OR end_ts >= start_ts`
- `severity IN ('info', 'low', 'medium', 'high', 'critical')`
- `domain IN ('production', 'equipment', 'energy', 'logistics')`

### `anomaly_status_changes`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `anomaly_event_id` | INTEGER | no | FK -> `anomaly_events.id`, indexed |  |
| `session_id` | VARCHAR(36) | yes | indexed |  |
| `from_status` | VARCHAR(16) | yes |  |  |
| `to_status` | VARCHAR(16) | no |  |  |
| `actor_role` | VARCHAR(32) | no |  |  |
| `note` | TEXT | yes |  |  |
| `changed_at` | DATETIME | no |  |  |

Checks:
- `actor_role IN ('executive', 'factory_manager', 'production_engineer', 'maintenance_engineer', 'logistics_officer', 'ai_analyst', 'system_admin', 'public_viewer')`
- `to_status IN ('new', 'acknowledged', 'verified', 'dismissed')`

### `model_registry`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `name` | VARCHAR(64) | no |  |  |
| `version` | VARCHAR(32) | no |  |  |
| `task` | VARCHAR(24) | no |  |  |
| `algorithm` | VARCHAR(64) | no |  |  |
| `features_json` | TEXT | yes |  |  |
| `metrics_json` | TEXT | yes |  |  |
| `beats_baseline` | BOOLEAN | yes |  |  |
| `train_window_start` | DATETIME | yes |  |  |
| `train_window_end` | DATETIME | yes |  |  |
| `test_window_start` | DATETIME | yes |  |  |
| `test_window_end` | DATETIME | yes |  |  |
| `trained_at` | DATETIME | no |  |  |
| `artifact_path` | VARCHAR(300) | yes |  |  |
| `model_card_path` | VARCHAR(300) | yes |  |  |
| `status` | VARCHAR(16) | no |  | trained |
| `data_kind` | VARCHAR(32) | no |  | synthetic |

Unique: `(name, version)`

Checks:
- `task IN ('regression', 'anomaly', 'classification', 'forecast')`
- `status IN ('trained', 'active', 'retired', 'failed')`

### `recommendation_decisions`

Human approval/rejection of an AI recommendation (session-scoped).

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `recommendation_id` | INTEGER | no | FK -> `ai_recommendations.id`, indexed |  |
| `session_id` | VARCHAR(36) | yes | indexed |  |
| `decision` | VARCHAR(16) | no |  |  |
| `approver_role` | VARCHAR(32) | no |  |  |
| `note` | TEXT | yes |  |  |
| `work_order_id` | INTEGER | yes | FK -> `work_orders.id` |  |
| `decided_at` | DATETIME | no |  |  |

Checks:
- `decision IN ('approved', 'rejected')`
- `approver_role IN ('executive', 'factory_manager', 'production_engineer', 'maintenance_engineer', 'logistics_officer', 'ai_analyst', 'system_admin', 'public_viewer')`

## Domain `platform` (`app/models/platform.py`)

### `audit_logs`

Append-only. Each row stores sha256(prev_hash + canonical row) -> tamper-evident hash chain. Never UPDATE or DELETE rows (except the whole session's rows on demo session reset, which is itself audited).

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | BIGINT | no | PK |  |
| `ts` | DATETIME | no | indexed |  |
| `session_id` | VARCHAR(36) | yes | indexed |  |
| `role` | VARCHAR(32) | no |  |  |
| `actor` | VARCHAR(64) | no |  |  |
| `action` | VARCHAR(64) | no |  |  |
| `entity_type` | VARCHAR(48) | no |  |  |
| `entity_id` | VARCHAR(64) | yes |  |  |
| `before_json` | TEXT | yes |  |  |
| `after_json` | TEXT | yes |  |  |
| `request_id` | VARCHAR(64) | yes |  |  |
| `demo_as_of` | DATETIME | yes |  |  |
| `prev_hash` | VARCHAR(64) | yes |  |  |
| `hash` | VARCHAR(64) | no | unique |  |

Unique: `(hash)`

Indexes: `ix_audit_logs_entity(entity_type, entity_id)`

Checks:
- `role IN ('executive', 'factory_manager', 'production_engineer', 'maintenance_engineer', 'logistics_officer', 'ai_analyst', 'system_admin', 'public_viewer')`

### `business_scenarios`

Saved what-if runs (production, maintenance impact, energy, ROI, queue). Session-scoped.

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `session_id` | VARCHAR(36) | yes | indexed |  |
| `kind` | VARCHAR(16) | no |  |  |
| `name` | VARCHAR(120) | no |  |  |
| `role` | VARCHAR(32) | no |  |  |
| `inputs_json` | TEXT | no |  |  |
| `outputs_json` | TEXT | no |  |  |
| `formula_version` | VARCHAR(16) | yes |  |  |
| `demo_as_of` | DATETIME | yes |  |  |
| `created_at` | DATETIME | no |  |  |
| `data_kind` | VARCHAR(32) | no |  | what_if |

Checks:
- `kind IN ('production', 'maintenance', 'energy', 'roi', 'queue')`
- `role IN ('executive', 'factory_manager', 'production_engineer', 'maintenance_engineer', 'logistics_officer', 'ai_analyst', 'system_admin', 'public_viewer')`

### `copilot_messages`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `copilot_session_id` | VARCHAR(36) | no | FK -> `copilot_sessions.id`, indexed |  |
| `session_id` | VARCHAR(36) | yes | indexed |  |
| `sender` | VARCHAR(12) | no |  |  |
| `content` | TEXT | no |  |  |
| `intent` | VARCHAR(48) | yes |  |  |
| `tool_calls_json` | TEXT | yes |  |  |
| `citations_json` | TEXT | yes |  |  |
| `refused` | BOOLEAN | yes |  |  |
| `created_at` | DATETIME | no |  |  |

Checks:
- `sender IN ('user', 'assistant', 'tool')`

### `copilot_sessions`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | VARCHAR(36) | no | PK |  |
| `session_id` | VARCHAR(36) | yes | indexed |  |
| `role` | VARCHAR(32) | no |  |  |
| `title` | VARCHAR(200) | yes |  |  |
| `mode` | VARCHAR(16) | no |  | deterministic |
| `created_at` | DATETIME | no |  |  |

Checks:
- `mode IN ('deterministic', 'llm')`
- `role IN ('executive', 'factory_manager', 'production_engineer', 'maintenance_engineer', 'logistics_officer', 'ai_analyst', 'system_admin', 'public_viewer')`

### `injected_events`

Ground-truth labels of injected anomalies/episodes. Used ONLY by ML evaluation (app/ml). Never in API output.

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `code` | VARCHAR(40) | no | unique |  |
| `scenario_code` | VARCHAR(32) | yes |  |  |
| `event_type` | VARCHAR(48) | no |  |  |
| `domain` | VARCHAR(16) | no |  |  |
| `entity_type` | VARCHAR(32) | no |  |  |
| `entity_id` | INTEGER | yes |  |  |
| `equipment_id` | INTEGER | yes | FK -> `equipment.id` |  |
| `process_stage_id` | INTEGER | yes | FK -> `process_stages.id` |  |
| `start_ts` | DATETIME | no |  |  |
| `end_ts` | DATETIME | no |  |  |
| `magnitude` | FLOAT | yes |  |  |
| `params_json` | TEXT | yes |  |  |
| `notes` | TEXT | yes |  |  |

Unique: `(code)`

Checks:
- `end_ts >= start_ts`
- `scenario_code IS NULL OR scenario_code IN ('NORMAL_DAY', 'OER_DEGRADATION', 'PRESS_VIBRATION_ANOMALY', 'STEAM_PRESSURE_DEVIATION', 'TRUCK_QUEUE_CONGESTION', 'ENERGY_EFFICIENCY_DROP')`
- `domain IN ('production', 'equipment', 'energy', 'logistics', 'quality')`

### `kb_chunks`

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `document_id` | INTEGER | no | FK -> `kb_documents.id`, indexed |  |
| `chunk_index` | INTEGER | no |  |  |
| `heading` | VARCHAR(200) | yes |  |  |
| `text` | TEXT | no |  |  |
| `token_count` | INTEGER | yes |  |  |
| `vector_json` | TEXT | yes |  |  |

Unique: `(document_id, chunk_index)`

### `kb_documents`

Newly authored SAMPLE documents for RAG (data_kind = sample_document). Not real company documents.

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `slug` | VARCHAR(80) | no |  |  |
| `lang` | VARCHAR(2) | no |  | en |
| `title` | VARCHAR(200) | no |  |  |
| `doc_type` | VARCHAR(32) | no |  |  |
| `body_md` | TEXT | no |  |  |
| `source_path` | VARCHAR(300) | yes |  |  |
| `version` | VARCHAR(16) | no |  | 1 |
| `data_kind` | VARCHAR(32) | no |  | sample_document |

Unique: `(slug, lang)`

Checks:
- `lang IN ('en', 'th')`

### `prices`

Synthetic / illustrative price series (CPO, kernel, FFB, electricity, diesel). Not market data.

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `commodity` | VARCHAR(16) | no |  |  |
| `price_date` | DATE | no |  |  |
| `price` | FLOAT | no |  |  |
| `unit` | VARCHAR(16) | no |  |  |
| `currency` | VARCHAR(3) | no |  | THB |
| `source_note` | VARCHAR(300) | yes |  |  |
| `data_kind` | VARCHAR(32) | no |  | synthetic |

Unique: `(commodity, price_date)`

Checks:
- `price >= 0`
- `commodity IN ('cpo', 'kernel', 'ffb', 'electricity', 'diesel', 'shell', 'efb')`

### `scenario_runs`

Named deterministic episode embedded in the single 120-day synthetic timeline (ADR-005, ADR-011).

| Column | Type | Null | Key / FK | Default |
|---|---|---|---|---|
| `id` | INTEGER | no | PK |  |
| `code` | VARCHAR(32) | no | unique |  |
| `name_en` | VARCHAR(120) | no |  |  |
| `name_th` | VARCHAR(120) | no |  |  |
| `description` | TEXT | no |  |  |
| `start_ts` | DATETIME | no |  |  |
| `end_ts` | DATETIME | no |  |  |
| `focus_ts` | DATETIME | no |  |  |
| `baseline_ts` | DATETIME | yes |  |  |
| `primary_stage_code` | VARCHAR(32) | yes |  |  |
| `primary_equipment_id` | INTEGER | yes | FK -> `equipment.id` |  |
| `expected_effects_json` | TEXT | yes |  |  |
| `seed` | INTEGER | yes |  |  |
| `data_kind` | VARCHAR(32) | no |  | synthetic |

Unique: `(code)`

Checks:
- `end_ts > start_ts`
- `code IN ('NORMAL_DAY', 'OER_DEGRADATION', 'PRESS_VIBRATION_ANOMALY', 'STEAM_PRESSURE_DEVIATION', 'TRUCK_QUEUE_CONGESTION', 'ENERGY_EFFICIENCY_DROP')`
- `focus_ts >= start_ts AND focus_ts <= end_ts`

