# API Contract - Digital Mill Lab

> **GENERATED** by `make contracts` from the FastAPI OpenAPI spec (`packages/contracts/openapi.json`).
> Do not edit the endpoint table by hand - change the router / schema and regenerate.
> Status `stub` = endpoint + response model exist, handler returns HTTP 501 `not_implemented` (planned).

## Conventions

| Topic | Rule |
|---|---|
| Prefix | `/api/v1` (plus `/health`, `/ready` at root) |
| JSON | `snake_case`; datetimes ISO-8601 UTC |
| Errors | `{"error": {"code", "message", "details"}}` for every non-2xx (`ErrorEnvelope`) |
| Demo clock | query `as_of` (ISO date -> 18:00 mill time, naive datetime -> Asia/Bangkok) must be inside the 120-day window; `scenario_id` (ScenarioCode) resolves to the scenario's `focus_ts` when `as_of` is omitted |
| Sandbox | header `X-Demo-Session` (uuid) - required for writes (428 `session_required`); seeded rows are a shared read-only baseline (ADR-006) |
| Role | header `X-Demo-Role` (one of 8, default `public_viewer`) - simulated viewpoint, enforced server-side (403 `forbidden`) |
| Provenance | every numeric payload carries `provenance {kind: synthetic_actual|forecast|what_if, source, as_of, model_version}` |
| Rate limit | token bucket per IP and per session -> 429 `rate_limited` + `Retry-After` |
| Contract metadata | each operation has `x-owner`, `x-task`, `x-status`, `x-permission`, `x-roles` |

## Shared type glossary (`app/schemas/common.py`)

| Type | Meaning |
|---|---|
| `Provenance` | Origin of a number: kind (`synthetic_actual` / `forecast` / `what_if`), source table/model, `as_of`, `model_version` |
| `SeriesPoint` | `{t, v}` chart point (t ISO UTC) |
| `BandPoint` / `BandSeries` | Forecast point with `lower`/`upper` interval + interval description |
| `Series` | Named line: `key`, `label`, `unit`, `points[]`, `provenance` |
| `Quantity` | Single value + unit + provenance |
| `KpiValue` | KPI with `previous`, `delta`, `delta_pct`, `good_direction`, `status`, `target`, `provenance` |
| `NormalRange` | low/high + unit + `basis` (how it was derived) |
| `Evidence` | Observed vs expected signal for an insight/anomaly - never a proven cause |
| `Formula` | Expression + named inputs + result + unit (what-if / ROI transparency) |
| `Assumption` | Editable input tagged with the SPEC fact taxonomy (`FactTag`) and a source |
| `EntityRef` | `{type, id, code, label}` link to another entity |
| `Disclaimer` | Keyed EN/TH disclaimer text |
| `ReportDocument` | Exported report body (markdown/csv/json) + disclaimers |
| `ErrorEnvelope` | `{error: {code, message, details}}` |
| `DemoContextOut` | Resolved clock/window/role/session echo |
| `FeatureStatus` | `implemented` / `partial` / `prototype` / `planned` (UI status chip) |
| Enums | `Role`, `ScenarioCode`, `StageCode`, `Severity`, `HealthState`, `AlertStatus`, `AnomalyStatus`, `RecommendationStatus`, `WorkOrderStatus`, `WorkOrderPriority`, `WorkOrderSource`, `Period`, `Granularity`, `ExportFormat` |

## Role abbreviations

`EX` executive · `FM` factory_manager · `PE` production_engineer · `ME` maintenance_engineer · `LO` logistics_officer · `AI` ai_analyst · `SA` system_admin · `PV` public_viewer · `*` no permission check

## Summary

97 operations. Status: implemented 95, prototype 2.

Owners: architect 3, backend-a 31, backend-b 38, copilot 7, ml 18.

## Endpoints

### ai

| Method | Path | Summary | Request body | Response model | Permission | Roles | Owner | Task | Status |
|---|---|---|---|---|---|---|---|---|---|
| GET | `/api/v1/ai/oer/forecast` | OER forecast with uncertainty band + naive baseline |  | `OerForecastResponse` | read:ai | EX FM PE ME AI SA PV | ml | DML-047 | implemented |
| GET | `/api/v1/ai/oer/explanation` | Feature contributions for an OER prediction |  | `OerExplanationResponse` | read:ai | EX FM PE ME AI SA PV | ml | DML-049 | implemented |
| GET | `/api/v1/ai/oer/model` | Active OER model version + measured metrics |  | `ModelInfo` | read:ai | EX FM PE ME AI SA PV | ml | DML-047 | implemented |
| GET | `/api/v1/ai/anomalies/production` | Production anomalies (OER, steam, rate, energy, loss) |  | `AnomalyListResponse` | read:ai | EX FM PE ME AI SA PV | ml | DML-048 | implemented |
| GET | `/api/v1/ai/anomalies/equipment` | Equipment anomalies with contributing sensors |  | `AnomalyListResponse` | read:ai | EX FM PE ME AI SA PV | ml | DML-053 | implemented |
| GET | `/api/v1/ai/anomalies/{anomaly_id}` | Anomaly detail (evidence, normal range, possible factors) |  | `AnomalyOut` | read:ai | EX FM PE ME AI SA PV | ml | DML-049 | implemented |
| POST | `/api/v1/ai/anomalies/{anomaly_id}/status` | Human verification: acknowledge / verify / dismiss | `AnomalyStatusRequest` | `AnomalyOut` | anomaly:verify | FM PE ME AI SA | ml | DML-048 | implemented |
| GET | `/api/v1/ai/failure-risk` | Relative failure-risk ranking (not a probability) |  | `FailureRiskResponse` | read:ai | EX FM PE ME AI SA PV | ml | DML-054 | implemented |
| GET | `/api/v1/ai/energy/forecast` | Energy consumption forecast |  | `ForecastResponse` | read:ai | EX FM PE ME AI SA PV | ml | DML-067 | implemented |
| GET | `/api/v1/ai/energy/anomalies` | Energy high vs production volume |  | `AnomalyListResponse` | read:ai | EX FM PE ME AI SA PV | ml | DML-068 | implemented |
| GET | `/api/v1/ai/logistics/queue-prediction` | Predicted waiting time for trucks in queue |  | `QueuePredictionResponse` | read:ai | EX FM PE ME AI SA PV | ml | DML-062 | implemented |
| GET | `/api/v1/ai/logistics/arrival-forecast` | Truck arrival pattern forecast |  | `ForecastResponse` | read:ai | EX FM PE ME AI SA PV | ml | DML-062 | implemented |
| GET | `/api/v1/ai/logistics/anomalies` | Implausible weights / excessive waits (review flags, not accusations) |  | `AnomalyListResponse` | read:ai | EX FM PE ME AI SA PV | ml | DML-062 | implemented |
| GET | `/api/v1/ai/models` | All model cards with measured metrics vs baselines |  | `ModelCardListResponse` | read:ai | EX FM PE ME AI SA PV | ml | DML-111 | implemented |
| GET | `/api/v1/ai/models/{name}` | One model card |  | `ModelCard` | read:ai | EX FM PE ME AI SA PV | ml | DML-111 | implemented |
| POST | `/api/v1/ai/models/{name}/run` | Run inference at the demo clock (AI Analyst) | `ModelRunRequest` | `ModelRunResponse` | model:run | AI SA | ml | DML-102 | implemented |

### alerts

| Method | Path | Summary | Request body | Response model | Permission | Roles | Owner | Task | Status |
|---|---|---|---|---|---|---|---|---|---|
| GET | `/api/v1/alerts` | Prioritised alerts (risk level, team, impact) as of the demo clock |  | `AlertListResponse` | read:executive | all | backend-a | DML-039 | implemented |
| GET | `/api/v1/alerts/{alert_id}` | Alert detail with evidence and estimated impact |  | `AlertOut` | read:executive | all | backend-a | DML-039 | implemented |
| POST | `/api/v1/alerts/{alert_id}/status` | Acknowledge / resolve / dismiss (session-scoped, audited) | `AlertAcknowledgeRequest` | `AlertOut` | alert:acknowledge | FM PE ME LO SA | backend-a | DML-039 | implemented |

### copilot

| Method | Path | Summary | Request body | Response model | Permission | Roles | Owner | Task | Status |
|---|---|---|---|---|---|---|---|---|---|
| POST | `/api/v1/copilot/chat` | Ask a question; answer grounded in tool results + cited sample docs | `ChatRequest` | `ChatResponse` | copilot:chat | all | copilot | DML-072 | implemented |
| GET | `/api/v1/copilot/tools` | Tool catalog with per-role allow flags |  | `ToolListResponse` | copilot:chat | all | copilot | DML-071 | implemented |
| GET | `/api/v1/copilot/sessions` | Copilot conversations in this demo session |  | `CopilotSessionListResponse` | copilot:chat | all | copilot | DML-077 | implemented |
| GET | `/api/v1/copilot/sessions/{copilot_session_id}` | Conversation with messages, tool calls, citations |  | `CopilotSessionDetail` | copilot:chat | all | copilot | DML-077 | implemented |
| GET | `/api/v1/copilot/sources/{ref}` | Open a cited source chunk (sample document) |  | `SourceDocumentResponse` | read:kb | all | copilot | DML-077 | implemented |

### cv-prototype

| Method | Path | Summary | Request body | Response model | Permission | Roles | Owner | Task | Status |
|---|---|---|---|---|---|---|---|---|---|
| POST | `/api/v1/cv/ffb-assessment` | PROTOTYPE: upload an FFB image for a non-validated assessment | `Body_ffb_assessment_api_v1_cv_ffb_assessment_post` | `CvPrototypeResponse` | cv:upload | PE AI SA | ml | P2-CV | prototype |
| GET | `/api/v1/cv/protocol` | Dataset / camera / labelling / validation protocol for a real grader |  | `CvProtocolResponse` | read:ai | EX FM PE ME AI SA PV | ml | P2-CV | prototype |

### demo

| Method | Path | Summary | Request body | Response model | Permission | Roles | Owner | Task | Status |
|---|---|---|---|---|---|---|---|---|---|
| GET | `/api/v1/demo/roles` | Simulated roles with permissions and copilot tools |  | `RoleListResponse` | - | * | backend-b | DML-103 | implemented |
| POST | `/api/v1/demo/session` | Issue a new sandbox session id |  | `SessionCreateResponse` | demo:session | all | backend-b | DML-034 | implemented |
| GET | `/api/v1/demo/context` | Echo the resolved DemoContext (clock, window, role, session) |  | `DemoContextResponse` | demo:session | all | backend-b | DML-034 | implemented |
| POST | `/api/v1/demo/session/reset` | Delete this session's rows (audit log kept) |  | `SessionResetResponse` | demo:session | all | backend-b | DML-034 | implemented |
| POST | `/api/v1/demo/reset-all` | Admin: clear all visitor sessions |  | `ResetAllResponse` | demo:reset_all | SA | backend-b | DML-034 | implemented |
| POST | `/api/v1/demo/tick` | Simulated live mode: next as_of + headline deltas | `TickRequest` | `TickResponse` | demo:session | all | backend-b | DML-037 | implemented |

### energy

| Method | Path | Summary | Request body | Response model | Permission | Roles | Owner | Task | Status |
|---|---|---|---|---|---|---|---|---|---|
| GET | `/api/v1/energy/summary` | Energy KPIs (kWh/t, steam/t, water/t, cost/t) and stage breakdown |  | `EnergySummaryResponse` | read:energy | all | backend-a | DML-065 | implemented |
| GET | `/api/v1/energy/series` | Energy time-series |  | `EnergySeriesResponse` | read:energy | all | backend-a | DML-066 | implemented |
| POST | `/api/v1/energy/what-if` | Energy what-if (efficiency, idle, energy mix) with limits | `EnergyWhatIfRequest` | `EnergyWhatIfResponse` | scenario:calculate | all | backend-a | DML-069 | implemented |

### executive

| Method | Path | Summary | Request body | Response model | Permission | Roles | Owner | Task | Status |
|---|---|---|---|---|---|---|---|---|---|
| GET | `/api/v1/executive/overview` | Dashboard first paint: KPIs + top alerts + insight |  | `ExecutiveOverviewResponse` | read:executive | all | backend-a | DML-036 | implemented |
| GET | `/api/v1/executive/kpis` | 12 control-tower KPIs, current vs previous period |  | `ExecutiveKpisResponse` | read:executive | all | backend-a | DML-035 | implemented |
| GET | `/api/v1/executive/series` | KPI time-series for trend charts / drill-down |  | `KpiSeriesResponse` | read:executive | all | backend-a | DML-037 | implemented |
| GET | `/api/v1/executive/insights` | AI insight summary: what is abnormal, impact, who checks first |  | `AiInsightSummaryResponse` | read:executive | all | backend-a | DML-040 | implemented |
| GET | `/api/v1/executive/bottlenecks` | Bottleneck overview by process stage |  | `BottleneckOverviewResponse` | read:executive | all | backend-a | DML-036 | implemented |
| GET | `/api/v1/executive/cost-productivity` | Cost & productivity analysis (illustrative) |  | `CostProductivityResponse` | read:executive | all | backend-a | DML-041 | implemented |
| GET | `/api/v1/executive/scenario-comparison` | KPIs per scenario vs NORMAL_DAY |  | `ScenarioComparisonResponse` | read:executive | all | backend-a | DML-041 | implemented |

### kb

| Method | Path | Summary | Request body | Response model | Permission | Roles | Owner | Task | Status |
|---|---|---|---|---|---|---|---|---|---|
| GET | `/api/v1/kb/documents` | List sample KB documents |  | `KbDocumentListResponse` | read:kb | all | copilot | DML-073 | implemented |
| GET | `/api/v1/kb/documents/{slug}` | Full sample document (markdown) |  | `KbDocumentDetail` | read:kb | all | copilot | DML-073 | implemented |

### logistics

| Method | Path | Summary | Request body | Response model | Permission | Roles | Owner | Task | Status |
|---|---|---|---|---|---|---|---|---|---|
| GET | `/api/v1/logistics/queue` | Trucks waiting / unloading at the demo clock |  | `QueueNowResponse` | read:logistics | all | backend-a | DML-061 | implemented |
| GET | `/api/v1/logistics/tickets` | Weighbridge tickets (gross/tare/net) with review flags |  | `TicketListResponse` | read:logistics | all | backend-a | DML-060 | implemented |
| GET | `/api/v1/logistics/suppliers` | Suppliers with volume / quality / wait KPIs |  | `SupplierListResponse` | read:logistics | all | backend-a | DML-059 | implemented |
| GET | `/api/v1/logistics/suppliers/{supplier_id}` | Supplier detail with plantations and trends |  | `SupplierDetail` | read:logistics | all | backend-a | DML-059 | implemented |
| GET | `/api/v1/logistics/kpis` | Waiting time, turnaround, queue length, utilisation |  | `LogisticsKpisResponse` | read:logistics | all | backend-a | DML-064 | implemented |
| GET | `/api/v1/logistics/arrival-pattern` | Arrivals by hour vs typical pattern |  | `ArrivalPatternResponse` | read:logistics | all | backend-a | DML-061 | implemented |
| POST | `/api/v1/logistics/queue-simulation` | FIFO vs constraint-aware slot scheduling (simulated) | `QueueSimulationRequest` | `QueueSimulationResponse` | scenario:calculate | all | backend-a | DML-063 | implemented |

### maintenance

| Method | Path | Summary | Request body | Response model | Permission | Roles | Owner | Task | Status |
|---|---|---|---|---|---|---|---|---|---|
| GET | `/api/v1/maintenance/equipment` | Equipment registry with computed health state |  | `EquipmentListResponse` | read:maintenance | all | backend-b | DML-051 | implemented |
| GET | `/api/v1/maintenance/equipment/{equipment_id}` | Equipment detail with sensors and health |  | `EquipmentDetail` | read:maintenance | all | backend-b | DML-051 | implemented |
| GET | `/api/v1/maintenance/equipment/{equipment_id}/health` | Health state with the explicit criteria that produced it |  | `EquipmentHealth` | read:maintenance | all | backend-b | DML-052 | implemented |
| GET | `/api/v1/maintenance/equipment/{equipment_id}/history` | Maintenance history, MTBF/MTTR |  | `MaintenanceHistoryResponse` | read:maintenance | all | backend-b | DML-057 | implemented |
| GET | `/api/v1/maintenance/equipment/{equipment_id}/sensors` | Sensor time-series (downsampled server-side) |  | `SensorSeriesResponse` | read:maintenance | all | backend-b | DML-052 | implemented |
| GET | `/api/v1/maintenance/recommendations` | Advisory maintenance recommendations |  | `RecommendationListResponse` | read:maintenance | all | backend-b | DML-055 | implemented |
| POST | `/api/v1/maintenance/recommendations/{recommendation_id}/decision` | Human approve / reject (optionally create a work order); audited | `RecommendationDecisionRequest` | `RecommendationOut` | recommendation:decide | FM ME SA | backend-b | DML-055 | implemented |
| POST | `/api/v1/maintenance/impact` | Downtime impact what-if with formulas and assumptions | `MaintenanceImpactRequest` | `MaintenanceImpactResponse` | scenario:calculate | all | backend-b | DML-058 | implemented |
| GET | `/api/v1/maintenance/downtime` | Downtime analysis by equipment, cause, hour of day |  | `DowntimeAnalysisResponse` | read:maintenance | all | backend-b | DML-057 | implemented |
| GET | `/api/v1/maintenance/technicians` | Technicians (fictional) and open assignments |  | `TechnicianListResponse` | read:maintenance | all | backend-b | DML-056 | implemented |

### meta

| Method | Path | Summary | Request body | Response model | Permission | Roles | Owner | Task | Status |
|---|---|---|---|---|---|---|---|---|---|
| GET | `/health` | Liveness (no DB access) |  | `HealthResponse` | - | * | architect | - | implemented |
| GET | `/ready` | Readiness: DB reachable, schema present, data seeded |  | `ReadyResponse` | - | * | architect | - | implemented |
| GET | `/api/v1/meta` | Product name, disclaimers, version, data window, anchor date |  | `MetaResponse` | - | * | architect | DML-011 | implemented |

### process

| Method | Path | Summary | Request body | Response model | Permission | Roles | Owner | Task | Status |
|---|---|---|---|---|---|---|---|---|---|
| GET | `/api/v1/process/stages` | Process stages with live state + material-flow edges |  | `ProcessStageListResponse` | read:production | all | backend-a | DML-079 | implemented |
| GET | `/api/v1/process/stages/{stage_code}` | Stage detail: equipment, sensors, KPIs, alerts, recommendations |  | `StageDetailResponse` | read:production | all | backend-a | DML-080 | implemented |

### production

| Method | Path | Summary | Request body | Response model | Permission | Roles | Owner | Task | Status |
|---|---|---|---|---|---|---|---|---|---|
| GET | `/api/v1/production/summary` | Business-day production summary + mass balance |  | `ProductionSummaryResponse` | read:production | all | backend-a | DML-043 | implemented |
| GET | `/api/v1/production/oer-trend` | OER/KER trend with expected OER for comparison |  | `OerTrendResponse` | read:production | all | backend-a | DML-045 | implemented |
| GET | `/api/v1/production/process-state` | Current hourly mill state vs normal ranges |  | `ProcessStateResponse` | read:production | all | backend-a | DML-044 | implemented |
| GET | `/api/v1/production/shifts` | Shift results |  | `ShiftListResponse` | read:production | all | backend-a | DML-043 | implemented |
| GET | `/api/v1/production/losses` | Oil-loss breakdown vs industry-practice benchmarks |  | `OilLossResponse` | read:production | all | backend-a | DML-045 | implemented |
| GET | `/api/v1/production/batches` | Processing batches |  | `BatchListResponse` | read:production | all | backend-a | DML-043 | implemented |
| GET | `/api/v1/production/quality` | Lab / QC parameters (FFA, moisture, dirt, DOBI, losses) |  | `QualityResponse` | read:production | all | backend-a | DML-043 | implemented |

### reports

| Method | Path | Summary | Request body | Response model | Permission | Roles | Owner | Task | Status |
|---|---|---|---|---|---|---|---|---|---|
| GET | `/api/v1/reports/{report_type}` | Export a report as markdown / csv / json |  | `ReportDocument` | report:export | all | backend-a | DML-042 | implemented |
| GET | `/api/v1/reports/{report_type}/html` | Print-ready HTML report (JSON-wrapped; raw=true returns text/html) |  | `HtmlReport` | report:export | all | backend-a | DML-042 | implemented |

### roi

| Method | Path | Summary | Request body | Response model | Permission | Roles | Owner | Task | Status |
|---|---|---|---|---|---|---|---|---|---|
| GET | `/api/v1/roi/defaults` | Default inputs (from synthetic baseline) + tagged assumptions |  | `RoiDefaultsResponse` | roi:calculate | all | backend-b | DML-085 | implemented |
| POST | `/api/v1/roi/calculate` | Baseline / Conservative / Expected / Optimistic cases | `RoiInputs` | `RoiResponse` | roi:calculate | all | backend-b | DML-086 | implemented |
| POST | `/api/v1/roi/sensitivity` | Tornado sensitivity of net benefit | `SensitivityRequest` | `SensitivityResponse` | roi:calculate | all | backend-b | DML-088 | implemented |
| POST | `/api/v1/roi/export` | Export ROI report (markdown/csv/json) with disclaimer | `RoiExportRequest` | `ReportDocument` | report:export | all | backend-b | DML-090 | implemented |
| POST | `/api/v1/roi/export/printable` | Printable HTML ROI report (render in an iframe, print to PDF) with the disclaimer | `RoiExportRequest` | `PrintableDocument` | report:export | all | backend-b | DML-090 | implemented |

### scenarios

| Method | Path | Summary | Request body | Response model | Permission | Roles | Owner | Task | Status |
|---|---|---|---|---|---|---|---|---|---|
| GET | `/api/v1/scenarios` | Deterministic scenario catalog (activate by sending focus_ts as as_of) |  | `ScenarioCatalogResponse` | read:executive | all | backend-b | DML-087 | implemented |
| GET | `/api/v1/scenarios/saved` | What-if runs saved in this session |  | `SavedScenarioListResponse` | scenario:calculate | all | backend-b | DML-087 | implemented |
| POST | `/api/v1/scenarios/saved` | Save a what-if run (session-scoped) | `SavedScenarioRequest` | `SavedScenarioOut` | scenario:save | EX FM PE ME LO AI SA | backend-b | DML-087 | implemented |
| POST | `/api/v1/scenarios/production/calculate` | Production what-if, recomputed with formulas echoed | `ProductionWhatIfRequest` | `ProductionWhatIfResponse` | scenario:calculate | all | backend-b | DML-050 | implemented |
| GET | `/api/v1/scenarios/{code}` | Scenario detail: window, focus time, expected cross-module effects |  | `ScenarioOut` | read:executive | all | backend-b | DML-087 | implemented |

### traceability

| Method | Path | Summary | Request body | Response model | Permission | Roles | Owner | Task | Status |
|---|---|---|---|---|---|---|---|---|---|
| GET | `/api/v1/traceability/lots` | CPO output lots |  | `LotListResponse` | read:traceability | all | backend-b | DML-083 | implemented |
| GET | `/api/v1/traceability/deliveries` | FFB deliveries (supplier, ticket, grade) |  | `DeliveryListResponse` | read:traceability | all | backend-b | DML-082 | implemented |
| GET | `/api/v1/traceability/forward` | Forward trace: supplier/delivery -> batches -> CPO lots |  | `TraceGraphResponse` | read:traceability | all | backend-b | DML-082 | implemented |
| GET | `/api/v1/traceability/backward` | Backward trace: CPO lot / batch -> suppliers (mass-balance shares) |  | `TraceGraphResponse` | read:traceability | all | backend-b | DML-083 | implemented |
| GET | `/api/v1/traceability/lots/{lot_id}/report` | Traceability report for a CPO lot |  | `TraceReportResponse` | read:traceability | all | backend-b | DML-084 | implemented |
| GET | `/api/v1/traceability/lots/{lot_id}/report/printable` | Printable HTML traceability report for a CPO lot (render in an iframe, print to PDF) |  | `PrintableDocument` | read:traceability | all | backend-b | DML-084 | implemented |

### work-orders

| Method | Path | Summary | Request body | Response model | Permission | Roles | Owner | Task | Status |
|---|---|---|---|---|---|---|---|---|---|
| GET | `/api/v1/work-orders` | Work orders (shared baseline + your session) |  | `WorkOrderListResponse` | read:maintenance | all | backend-b | DML-056 | implemented |
| POST | `/api/v1/work-orders` | Create (manual / from alert / from recommendation); requires confirm=true | `WorkOrderCreateRequest` | `WorkOrderOut` | workorder:create | FM PE ME SA | backend-b | DML-056 | implemented |
| GET | `/api/v1/work-orders/{work_order_id}` | Work order with status history |  | `WorkOrderDetail` | read:maintenance | all | backend-b | DML-056 | implemented |
| POST | `/api/v1/work-orders/{work_order_id}/assign` | Assign a technician | `WorkOrderAssignRequest` | `WorkOrderOut` | workorder:assign | FM ME SA | backend-b | DML-056 | implemented |
| POST | `/api/v1/work-orders/{work_order_id}/transition` | Change status (validated state machine) | `WorkOrderTransitionRequest` | `WorkOrderOut` | workorder:transition | FM ME SA | backend-b | DML-056 | implemented |
| GET | `/api/v1/work-orders/{work_order_id}/audit` | Audit trail with hash-chain verification |  | `AuditTrailResponse` | read:maintenance | all | backend-b | DML-056 | implemented |
