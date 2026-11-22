# API documentation — Digital Mill Lab

> Independent portfolio / concept demo on synthetic data. Not an official system of any company.
> The complete, generated endpoint table (97 operations, request/response models, permissions, roles, status) is
> [docs/architecture/API_CONTRACT.md](architecture/API_CONTRACT.md); the live OpenAPI document is served at `/openapi.json` and
> Swagger UI at `/docs` on the API port. This page explains the conventions and shows real requests.

## 1. Basics

| Topic | Rule |
|---|---|
| Base path | `/api/v1` (plus `/health` liveness and `/ready` readiness at the root) |
| Format | JSON, `snake_case`, datetimes ISO-8601 UTC (`Z`) |
| Through the web app | The browser calls `/api/v1/*` on the web origin; Next.js proxies to the API (same origin, no CORS) |
| Rate limit | Token bucket per client IP (1800/min, burst 200) and per `X-Demo-Session` (300/min, burst 100) -> `429 rate_limited` + `Retry-After` |
| Body size | JSON bodies above 256 KiB -> `413` (upload route: 5 MiB + 1 MiB) |

## 2. Headers

| Header | Meaning |
|---|---|
| `X-Demo-Role` | One of `executive`, `factory_manager`, `production_engineer`, `maintenance_engineer`, `logistics_officer`, `ai_analyst`, `system_admin`, `public_viewer` (default when absent). A **simulated viewpoint**, not authentication: permissions are enforced server-side (403 `forbidden`) to show how RBAC would work. Unknown value -> 422 `invalid_role` |
| `X-Demo-Session` | UUID of the visitor's sandbox (`POST /api/v1/demo/session` issues one; any UUID works). **Required for every write** (428 `session_required`). Rows created in a session are visible only to that session; seeded rows are a shared read-only baseline (changes to them are copy-on-write per session) |
| `X-Request-ID` | Optional; echoed back if it matches `[A-Za-z0-9-]{1,64}`, otherwise a new id is generated |

## 3. Demo clock and scenarios

* `as_of` (query): the demo "now". ISO datetime (`2026-11-20T08:00:00Z`; naive values are mill time, Asia/Bangkok) or a date
  (= 18:00 mill time that day). Must be inside the 120-day window (2026-07-23T17:00Z .. 2026-11-20T17:00Z), else 422 `as_of_out_of_window`.
  Nothing later than `as_of` is returned in actual data (tested on every GET operation); forecasts and what-ifs are labelled as such.
* `scenario_id` (query): one of `NORMAL_DAY`, `OER_DEGRADATION`, `PRESS_VIBRATION_ANOMALY`, `TRUCK_QUEUE_CONGESTION`,
  `STEAM_PRESSURE_DEVIATION`, `ENERGY_EFFICIENCY_DROP`. When `as_of` is omitted the clock jumps to that scenario's `focus_ts`
  (catalogue: `GET /api/v1/scenarios`). Scenarios are playback positions on one deterministic timeline, not data mutations.
* Neither given: the default clock (`default_as_of` in `/api/v1/meta`, currently 2026-11-20T11:00:00Z).

## 4. Error envelope

Every non-2xx response has the same shape:

```json
{"error": {"code": "forbidden", "message": "human-readable text", "details": {"role": "public_viewer", "permission": "workorder:create"}}}
```

Common codes: `validation_error` (422, `details` = list of field errors), `invalid_role`, `invalid_session`, `as_of_out_of_window`,
`forbidden` (403), `session_required` (428), `not_found` (404; ids of other sessions look exactly like missing ids), `invalid_transition` (409),
`duplicate_work_order` (409), `payload_too_large` (413), `rate_limited` (429), `value_out_of_range` (422), `internal_error` (500, no internals).

## 5. Provenance

Numeric payloads carry `provenance`:

```json
{"kind": "synthetic_actual | forecast | what_if", "source": "process_hourly", "as_of": "2026-11-20T08:00:00Z", "model_version": null}
```

`synthetic_actual` = computed from stored synthetic records up to `as_of`; `forecast` = model output (with its model version, interval and the
baseline it is compared with); `what_if` = scenario calculation with formulas and assumptions echoed. The UI renders a badge from it.
Known gap: anomaly objects (`AnomalyOut`) have no provenance block (they carry `model_version`).

## 6. Examples (actually run on 2026-11-22, port 8110, seeded + ML database; output trimmed)

`B=http://localhost:8110/api/v1`

**1. Product meta and disclaimers (public, no headers)**

```bash
curl -s "$B/meta"
```
```json
{"product": "Digital Mill Lab", "version": "0.1.0", "demo_mode": true,
 "data_window": {"start_date": "2026-07-24", "end_date": "2026-11-20", "days": 120, "timezone": "Asia/Bangkok"},
 "default_as_of": "2026-11-20T11:00:00Z", "copilot_mode": "deterministic",
 "disclaimers": [{"key": "independent_concept", "text_en": "Independent portfolio / concept demo. Not an official system of any company and not affiliated with or endorsed by any company.", "text_th": "..."}, ...]}
```

**2. Executive KPIs at a scenario's focus time**

```bash
curl -s "$B/executive/kpis?scenario_id=PRESS_VIBRATION_ANOMALY&period=today" -H "X-Demo-Role: executive"
```
```json
{"period": "today", "period_start": "2026-11-19T17:00:00Z", "period_end": "2026-11-20T08:00:00Z",
 "kpis": [..., {"key": "oer_pct", "label": "Oil extraction rate (OER)", "value": 18.305, "unit": "%", "previous": 18.467, "delta": -0.162,
   "delta_pct": -0.88, "good_direction": "up", "target": 18.403,
   "provenance": {"kind": "synthetic_actual", "source": "process_hourly", "as_of": "2026-11-20T08:00:00Z", "model_version": null}}, ...]}
```

**3. Open alerts at an explicit clock**

```bash
curl -s "$B/alerts?as_of=2026-11-20T08:00:00Z&status=new&limit=2" -H "X-Demo-Role: maintenance_engineer"
```
```json
{"total": 4, "counts_by_severity": {"critical": 2, "high": 1, "medium": 1, "low": 0, "info": 0},
 "items": [{"id": 83, "code": "MLA-00162", "source": "equipment_anomaly", "severity": "critical", "status": "new",
            "title": "PRS-03: abnormal current, temperature, vibration", "raised_at": "2026-11-20T06:00:00Z", ...},
           {"id": 18, "code": "ALR-20261119-0018", "source": "rule", "severity": "critical", "status": "new",
            "title": "PRS-03-VIB-DE HIGH-HIGH (critical): Twin-screw press 3 drive-end vibration (RMS velocity)", "raised_at": "2026-11-19T03:20:00Z", ...}]}
```

**4. Health state with the rule that produced it (public viewer)**

```bash
curl -s "$B/maintenance/equipment/18/health?scenario_id=PRESS_VIBRATION_ANOMALY"
```
```json
{"equipment_id": 18, "state": "critical",
 "criteria": [..., {"sensor_code": "PRS-03-VIB-DE", "rule": "latest reading of PRS-03-VIB-DE >= crit limit 4.5 mm/s -> Critical", "observed": 4.587, ...}],
 "provenance": {"kind": "synthetic_actual", "source": "sensor_readings + alerts + maintenance_events (rule-based health criteria)",
                "as_of": "2026-11-20T08:00:00Z", "model_version": "health-rules@1.0; risk-index@1.0"}, ...}
```

**5. Write with a role that lacks the permission -> 403**

```bash
curl -s -i -X POST "$B/work-orders?as_of=2026-11-20T08:00:00Z" -H "X-Demo-Role: public_viewer" -H "X-Demo-Session: $S" \
  -H 'Content-Type: application/json' -d '{"equipment_id":18,"title":"Inspect PRS-03","confirm":true}'
```
```
HTTP/1.1 403 Forbidden
{"error":{"code":"forbidden","message":"Role 'public_viewer' is not permitted to perform 'workorder:create' (simulated role, ADR-007).","details":{"role":"public_viewer","permission":"workorder:create"}}}
```

**6. Write without a sandbox session -> 428**

```bash
curl -s -i -X POST "$B/work-orders?as_of=2026-11-20T08:00:00Z" -H "X-Demo-Role: maintenance_engineer" \
  -H 'Content-Type: application/json' -d '{"equipment_id":18,"title":"Inspect PRS-03","confirm":true}'
```
```
HTTP/1.1 428 Precondition Required
{"error":{"code":"session_required","message":"This action needs a demo session. Create one via POST /api/v1/demo/session and send it as X-Demo-Session.","details":null}}
```

**7. Create a work order from an alert (human-confirmed, session-scoped, audited)**

```bash
S=$(uuidgen | tr A-Z a-z)
curl -s -i -X POST "$B/work-orders?as_of=2026-11-20T08:00:00Z" -H "X-Demo-Role: maintenance_engineer" -H "X-Demo-Session: $S" \
  -H 'Content-Type: application/json' -d '{"equipment_id":18,"title":"Inspect PRS-03 drive-end bearing","alert_id":83,"priority":"high","confirm":true}'
```
```
HTTP/1.1 201 Created
{"id":119,"code":"WO-202611-0119","title":"Inspect PRS-03 drive-end bearing","status":"open","priority":"high","source_type":"alert",
 "equipment":{"type":"equipment","id":18,"code":"PRS-03","label":"Twin-screw press 3"},"alert_id":83,"created_by_role":"maintenance_engineer",
 "demo_as_of":"2026-11-20T08:00:00Z","is_baseline":false,"allowed_transitions":["assigned","on_hold","cancelled"],"alert_code":"MLA-00162","alert_status":"in_progress", ...}
```
The linked alert is now `in_progress` and PRS-03 shows `maintenance_status: work_order_open` — for this session only. History:
`GET /work-orders/119/audit` (hash-chain verified).

**8. Clock outside the dataset -> 422**

```bash
curl -s -i "$B/production/summary?as_of=2027-01-01" -H "X-Demo-Role: executive"
```
```
HTTP/1.1 422 Unprocessable Entity
{"error":{"code":"as_of_out_of_window","message":"as_of is outside the synthetic dataset window","details":{"window_start":"2026-07-23T17:00:00+00:00","window_end":"2026-11-20T17:00:00+00:00"}}}
```

**9. Copilot question (deterministic mode, grounded in tool results)**

```bash
curl -s -X POST "$B/copilot/chat?as_of=2026-10-02T09:00:00Z" -H "X-Demo-Role: factory_manager" -H "X-Demo-Session: $S" \
  -H 'Content-Type: application/json' -d '{"message":"Why did OER drop today?","lang":"en"}'
```
```json
{"answer": "Interpreted as: why OER changed. OER so far today is 17.64%, 0.92 pp below the trailing 28-day OER of 18.56% (normal range 18.10-19.03% = 28-day OER +/- 2 s.d. of daily OER). Possible contributing factors (statistical association, not proven cause): Ripe share of FFB processed 81.09 % vs 86.16 %; Sterilizer cycle 66.29 min vs 79.48 min; ...",
 "tool_calls": [{"tool": "get_oer_trend", ...}, {"tool": "get_production_summary", ...}, {"tool": "get_active_alerts", ...}, {"tool": "search_demo_documents", ...}],
 "provenance": {"kind": "synthetic_actual", "source": "copilot:get_oer_trend,get_production_summary,get_active_alerts,search_demo_documents",
                "as_of": "2026-10-02T09:00:00Z", "model_version": "copilot-router@1"}, ...}
```

## 7. Endpoint groups (see API_CONTRACT.md for every operation)

`meta` · `demo` (roles, session, reset, tick) · `executive` · `alerts` · `process` (digital twin) · `production` · `maintenance` ·
`work-orders` · `logistics` · `energy` · `traceability` · `scenarios` · `roi` · `reports` · `ai` (forecasts, anomalies, model cards) ·
`copilot` · `kb` · `cv-prototype`.

Regenerate the contract after API changes with `make contracts` (maintainers; it rewrites `packages/contracts/openapi.json`,
`src/api-types.ts` and `docs/architecture/API_CONTRACT.md`).
