"""Generate docs/architecture/API_CONTRACT.md from packages/contracts/openapi.json (run by `make contracts`).

The table is derived from the OpenAPI x-* extensions, so it cannot drift from the code.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

HEADER = """# API Contract - Digital Mill Lab

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
"""

ABBR = {
    "executive": "EX",
    "factory_manager": "FM",
    "production_engineer": "PE",
    "maintenance_engineer": "ME",
    "logistics_officer": "LO",
    "ai_analyst": "AI",
    "system_admin": "SA",
    "public_viewer": "PV",
    "*": "*",
}


def _model(op: dict) -> str:
    for code, resp in op.get("responses", {}).items():
        if code.startswith("2"):
            ref = resp.get("content", {}).get("application/json", {}).get("schema", {}).get("$ref", "")
            return ref.rsplit("/", 1)[-1] or "-"
    return "-"


def _body(op: dict) -> str:
    content = op.get("requestBody", {}).get("content", {})
    for ctype, c in content.items():
        ref = c.get("schema", {}).get("$ref", "")
        name = ref.rsplit("/", 1)[-1] if ref else ctype
        return name
    return ""


def main() -> int:
    spec_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "packages/contracts/openapi.json"
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "docs/architecture/API_CONTRACT.md"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    rows_by_tag: dict[str, list[str]] = {}
    status_count: Counter[str] = Counter()
    owner_count: Counter[str] = Counter()
    for path, item in spec["paths"].items():
        for method, op in item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            tag = (op.get("tags") or ["root"])[0]
            roles = op.get("x-roles") or ["*"]
            role_txt = "all" if len(roles) == 8 else " ".join(ABBR.get(r, r) for r in roles)
            status = op.get("x-status", "implemented" if not path.startswith("/api/v1") else "?")
            owner = op.get("x-owner", "architect")
            status_count[status] += 1
            owner_count[owner] += 1
            body = _body(op)
            rows_by_tag.setdefault(tag, []).append(
                f"| {method.upper()} | `{path}` | {op.get('summary', '')} | {body and '`' + body + '`'} | `{_model(op)}` | "
                f"{op.get('x-permission') or '-'} | {role_txt} | {owner} | {op.get('x-task') or '-'} | {status} |"
            )
    lines = [HEADER, "## Summary", ""]
    total = sum(status_count.values())
    lines.append(f"{total} operations. Status: " + ", ".join(f"{k} {v}" for k, v in sorted(status_count.items())) + ".")
    lines.append("")
    lines.append("Owners: " + ", ".join(f"{k} {v}" for k, v in sorted(owner_count.items())) + ".")
    lines.append("")
    lines.append("## Endpoints")
    for tag in sorted(rows_by_tag):
        lines += [
            "",
            f"### {tag}",
            "",
            "| Method | Path | Summary | Request body | Response model | Permission | Roles | Owner | Task | Status |",
            "|---|---|---|---|---|---|---|---|---|---|",
            *rows_by_tag[tag],
        ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out_path} ({total} operations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
