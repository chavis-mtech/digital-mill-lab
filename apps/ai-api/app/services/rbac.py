"""Simulated role -> permission matrix (SPEC section 10, ADR-007).

Roles are *simulated viewpoints* selected by the X-Demo-Role header, NOT production authentication.
Enforcement is server-side via deps.require_permission(); the matrix below is the single source of truth
(also published at GET /api/v1/demo/roles and in docs/architecture/API_CONTRACT.md).
"""

from __future__ import annotations

from enum import StrEnum

from app.models.enums import Role


class Permission(StrEnum):
    # ---- reads (dashboards / analytics) ----
    read_executive = "read:executive"
    read_production = "read:production"
    read_maintenance = "read:maintenance"
    read_logistics = "read:logistics"
    read_energy = "read:energy"
    read_traceability = "read:traceability"
    read_ai = "read:ai"
    read_kb = "read:kb"
    read_audit = "read:audit"  # global audit log (work-order trails are read:maintenance)
    # ---- calculations that never change business records ----
    scenario_calculate = "scenario:calculate"
    roi_calculate = "roi:calculate"
    report_export = "report:export"
    # ---- writes (session-scoped, human-confirmed) ----
    scenario_save = "scenario:save"
    workorder_create = "workorder:create"
    workorder_assign = "workorder:assign"
    workorder_transition = "workorder:transition"
    recommendation_decide = "recommendation:decide"
    alert_acknowledge = "alert:acknowledge"
    anomaly_verify = "anomaly:verify"
    model_run = "model:run"
    cv_upload = "cv:upload"
    # ---- demo control ----
    demo_session = "demo:session"  # create / reset the caller's OWN sandbox session
    demo_reset_all = "demo:reset_all"  # wipe all visitor sessions (admin)
    # ---- copilot ----
    copilot_chat = "copilot:chat"
    tool_production_summary = "copilot:tool:get_production_summary"
    tool_oer_trend = "copilot:tool:get_oer_trend"
    tool_equipment_health = "copilot:tool:get_equipment_health"
    tool_active_alerts = "copilot:tool:get_active_alerts"
    tool_downtime_analysis = "copilot:tool:get_downtime_analysis"
    tool_logistics_summary = "copilot:tool:get_logistics_summary"
    tool_energy_summary = "copilot:tool:get_energy_summary"
    tool_business_scenario = "copilot:tool:run_business_scenario"
    tool_search_documents = "copilot:tool:search_demo_documents"
    tool_supplier_trace = "copilot:tool:get_supplier_trace"
    tool_draft_work_order = "copilot:tool:draft_work_order"  # drafts only; human confirms via work-order API


P = Permission

_ALL_READS = {
    P.read_executive,
    P.read_production,
    P.read_maintenance,
    P.read_logistics,
    P.read_energy,
    P.read_traceability,
    P.read_ai,
    P.read_kb,
}
_CALC = {P.scenario_calculate, P.roi_calculate, P.report_export, P.demo_session, P.copilot_chat}
_READ_TOOLS = {
    P.tool_production_summary,
    P.tool_oer_trend,
    P.tool_equipment_health,
    P.tool_active_alerts,
    P.tool_downtime_analysis,
    P.tool_logistics_summary,
    P.tool_energy_summary,
    P.tool_business_scenario,
    P.tool_search_documents,
}

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.public_viewer: frozenset(_ALL_READS | _CALC | _READ_TOOLS),
    Role.executive: frozenset(_ALL_READS | _CALC | _READ_TOOLS | {P.read_audit, P.scenario_save, P.tool_supplier_trace}),
    Role.factory_manager: frozenset(
        _ALL_READS
        | _CALC
        | _READ_TOOLS
        | {
            P.read_audit,
            P.scenario_save,
            P.workorder_create,
            P.workorder_assign,
            P.workorder_transition,
            P.recommendation_decide,
            P.alert_acknowledge,
            P.anomaly_verify,
            P.tool_supplier_trace,
            P.tool_draft_work_order,
        }
    ),
    Role.production_engineer: frozenset(
        _ALL_READS
        | _CALC
        | _READ_TOOLS
        | {P.scenario_save, P.workorder_create, P.alert_acknowledge, P.anomaly_verify, P.cv_upload, P.tool_draft_work_order}
    ),
    Role.maintenance_engineer: frozenset(
        _ALL_READS
        | _CALC
        | _READ_TOOLS
        | {
            P.scenario_save,
            P.workorder_create,
            P.workorder_assign,
            P.workorder_transition,
            P.recommendation_decide,
            P.alert_acknowledge,
            P.anomaly_verify,
            P.tool_draft_work_order,
        }
    ),
    Role.logistics_officer: frozenset(
        (_ALL_READS - {P.read_ai})
        | _CALC
        | (_READ_TOOLS - {P.tool_equipment_health, P.tool_downtime_analysis})
        | {P.scenario_save, P.alert_acknowledge, P.tool_supplier_trace}
    ),
    Role.ai_analyst: frozenset(
        _ALL_READS | _CALC | _READ_TOOLS | {P.scenario_save, P.anomaly_verify, P.model_run, P.cv_upload, P.tool_supplier_trace}
    ),
    Role.system_admin: frozenset(set(Permission)),
}

ROLE_LABELS: dict[Role, dict[str, str]] = {
    Role.executive: {"en": "Executive", "th": "ผู้บริหาร"},
    Role.factory_manager: {"en": "Factory Manager", "th": "ผู้จัดการโรงงาน"},
    Role.production_engineer: {"en": "Production Engineer", "th": "วิศวกรฝ่ายผลิต"},
    Role.maintenance_engineer: {"en": "Maintenance Engineer", "th": "วิศวกรซ่อมบำรุง"},
    Role.logistics_officer: {"en": "Logistics Officer", "th": "เจ้าหน้าที่โลจิสติกส์"},
    Role.ai_analyst: {"en": "AI Analyst", "th": "นักวิเคราะห์ AI"},
    Role.system_admin: {"en": "System Administrator", "th": "ผู้ดูแลระบบ"},
    Role.public_viewer: {"en": "Public Demo Viewer", "th": "ผู้ชมเดโม (สาธารณะ)"},
}

DEFAULT_ROLE = Role.public_viewer


def has_permission(role: Role, permission: Permission | str) -> bool:
    return Permission(permission) in ROLE_PERMISSIONS[role]


def roles_with(permission: Permission | str) -> list[Role]:
    perm = Permission(permission)
    return [r for r in Role if perm in ROLE_PERMISSIONS[r]]


def copilot_tools_for(role: Role) -> list[str]:
    prefix = "copilot:tool:"
    return sorted(p.value[len(prefix) :] for p in ROLE_PERMISSIONS[role] if p.value.startswith(prefix))


def is_read_only(role: Role) -> bool:
    writes = {p for p in Permission if p.value.split(":")[0] in {"workorder", "recommendation", "alert", "anomaly", "model", "cv"}}
    writes |= {P.scenario_save, P.demo_reset_all}
    return not (ROLE_PERMISSIONS[role] & writes)
