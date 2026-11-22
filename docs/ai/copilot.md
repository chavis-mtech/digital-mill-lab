# Industrial Operations Copilot (SPEC 4.F)

Status: **implemented**: deterministic mode by default, optional LLM mode. Independent portfolio demo on synthetic data.
This is not an official system of any company. Owner: copilot. Code: `apps/ai-api/app/copilot/`.

## Pipeline

`POST /api/v1/copilot/chat` runs these steps in `engine.py`:

1. **Input safety** (`safety.py`): NFKC normalisation and removal of zero-width/bidi characters; the 2,000-character cap is
   enforced by the schema. The message is then checked against TH/EN patterns for injection, role escalation, SQL and
   control/write actions. A match means refusal, an audit row, and no tool call.
2. **Routing** (`router.py`): rules, then a TF-IDF nearest exemplar, then follow-up memory; slots are extracted. See
   `model-cards/copilot-router.md`.
3. **Tools** (`tools.py`): the server checks the role allow-list (`copilot:tool:<name>` in `services/rbac.py`) before any data
   access, then validates arguments with Pydantic. Tools are read-only and call the existing services in-process with the
   caller's `DemoContext`. A past day only ever moves the clock earlier, so no tool reads data after `as_of`. String fields in
   tool results are neutralised (tool output is data). Each call writes an audit row (`copilot.tool_call` /
   `copilot.tool_denied`, hash-chained by `services/audit.py`).
4. **Composer** (`composer.py`): fixed TH/EN templates that print only tool facts. Causes are worded as "possible contributing
   factors (statistical association, not proven cause)". When an ML model is mentioned, the answer says what it is and gives
   its measured limits, read from the model registry: the OER forecast loses to its naive baseline, so it is never used as a
   reason, and anomaly-detector precision/recall are quoted. Design-intent text in `scenario_runs` is never read.
5. **Grounding verifier** (`verifier.py`): every number in the answer must match a fact value, a number quoted in tool text or a
   cited snippet, or a number the user typed (rounding tolerance). Definitive causal language ("caused by", "the model shows ...
   caused", "สาเหตุคือ") is flagged. If deterministic text fails, the copilot shows an explicit uncertainty message instead.
6. **Optional LLM** (`llm.py`): the model may request allow-listed tools through `run_tool` and phrase the answer. The SAME
   verifier and an instruction-like-output check run on its text; if they fail, the deterministic answer is returned with
   `llm_answer_rejected: true`.
7. **Storage**: conversations are stored only with `X-Demo-Session` (ADR-006) and are readable only by that session. Rate limit:
   20 questions per minute per session or IP, on top of the global limiter.

## Tools

| Tool | Service reused | Roles without access |
|---|---|---|
| get_production_summary | `services.production.summary` | - |
| get_oer_trend | `services.production.oer_trend` + `services.kpi_insights` rule R1 (measured factor deviations) + ML registry metrics | - |
| get_equipment_health | `services.maintenance_health` (health criteria, relative risk index) + ML registry metrics | logistics_officer |
| get_active_alerts | `services.kpi_alerts.list_alerts` + `kpi_insights.insights` | - |
| get_downtime_analysis | `services.maintenance.downtime_analysis` | logistics_officer |
| get_logistics_summary | `services.logistics.queue_now` + `kpis` | - |
| get_energy_summary | `services.energy.summary` | - |
| run_business_scenario | `services.scenarios.production_what_if`, `services.maintenance.impact` (what-if only) | - |
| search_demo_documents | `copilot.kb` (TF-IDF over sample documents) | - |
| get_supplier_trace | `services.traceability.lot_report` | public_viewer, production_engineer, maintenance_engineer |

`draft_work_order` exists in the RBAC matrix but is **not implemented as a tool**. The copilot never creates records. It points
to the Work Orders screen (`/demo/maintenance/work-orders`), where an authorised person confirms the action.

## Endpoints

`POST /copilot/chat` (response fields: `answer`, `mode`, `intent`, `tool_calls`, `evidence[]` with facts, provenance and as_of,
`citations[]`, `assumptions`, `limits`, `uncertainty`, `refused`/`refusal_reason`, `verification`, `safety_flags`,
`suggested_followups`, `llm_answer_rejected`, `route`, `persisted`) · `GET /copilot/tools` · `GET /copilot/sessions[/{id}]` ·
`GET /copilot/sources/{ref}` (e.g. `kb:industrial-kpi-guide%236`, labelled sample document) · `GET /kb/documents[/{slug}]`.

## Knowledge base

Source files are `data/kb/*.md`: six sample documents written for this demo, not company documents. To index them, run
`python -m app.copilot.ingest`. Ingestion is idempotent (one row per file, versioned by content hash) and splits each document
into one chunk per `##`/`###` heading. The API also auto-ingests on first use. Retrieval uses word plus character TF-IDF and a
heading-term rerank. There is no external embedding service.

## LLM configuration (optional)

Set the following in `.env`, which is never committed:

- `LLM_PROVIDER=openai_compatible|anthropic`
- `LLM_MODEL=...`
- `LLM_API_KEY=...`
- `LLM_BASE_URL=...` (for Ollama, LM Studio or vLLM, e.g. `http://localhost:11434/v1`; no key needed)

With `LLM_PROVIDER=none` (the default) the copilot runs in deterministic mode. No real provider was exercised in this build;
the adapter loop is tested with a fake provider and a mocked `httpx`.

## Behaviours added after review

- Forecast questions are never answered with today's value. The copilot says it does not produce a reliable forecast, quotes the measured MAE against the baseline, and shows measured values.
- Accusation, fraud and blame questions are declined in EN and TH: flags mean "unusual, needs review", never wrongdoing.
- Low-confidence routing asks a clarification question with the top 2 interpretations.
- Every answer starts with "Interpreted as: ...".
- A percent cut in downtime is applied to the 30-day **plant downtime**, which uses the same `process_hourly` definition as the Executive KPI `plant_downtime_h`. The maintenance-event sum is not used here: it includes planned work, its events can overlap, and it would overstate lost production. Whenever that maintenance-event breakdown is shown, it is labelled as such.

## Limits

See `COPILOT_EVALUATION.md`. On new wording the router answers about 65% of held-out paraphrases (83% of those correctly) and asks for clarification on the rest. Thai retrieval mostly
hits the Thai summary sections. "Possible contributing factors" are statistical screens, not root-cause analysis.
