"""Copilot orchestration: safety -> route -> allow-listed tools (audited) -> compose -> verify -> (LLM) -> persist.

Session scope (ADR-006): conversations are stored only when the caller sends X-Demo-Session; the stored rows carry that
session id and are only readable by it. Without a session the answer is returned but nothing is stored (no memory).
"""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.copilot import composer as C
from app.copilot.router import Route, route
from app.copilot.safety import check_user_input, normalise
from app.copilot.tools import TOOLS, ToolResult, ctx_end_of_day, resolve_day, run_tool
from app.copilot.verifier import Verification, numbers_from_text, verify
from app.errors import ApiError
from app.models.platform import CopilotMessage, CopilotSession
from app.services.audit import write_audit
from app.services.demo_context import DemoContext

MAX_MESSAGES_PER_CONVERSATION = 200
RATE_PER_MINUTE = 20
_rate: dict[str, deque] = {}
_rate_lock = threading.Lock()

TOOL_TO_INTENT = {
    "get_production_summary": "oer_value", "get_oer_trend": "oer_why", "get_equipment_health": "inspect_first",
    "get_active_alerts": "prioritize", "get_downtime_analysis": "downtime_when", "get_logistics_summary": "trucks_waiting",
    "get_energy_summary": "energy_why", "run_business_scenario": "oer_what_if", "search_demo_documents": "doc_search",
    "get_supplier_trace": "supplier_trace",
}  # fmt: skip
DOC_QUERY = {"oer_why": "OER oil extraction rate losses definition", "inspect_first": "screw press vibration bearing inspection escalate",
             "equipment_status": "vibration bearing temperature inspection limits", "energy_why": "energy per tonne electricity idle"}  # fmt: skip


@dataclass
class Plan:
    calls: list[tuple[str, dict[str, Any], bool]] = field(default_factory=list)  # (tool, args, required)


_MONTH_EN = r"(jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|june?|july?|aug(ust)?|sep(t(ember)?)?|oct(ober)?|nov(ember)?|dec(ember)?)"
_MONTH_TH = r"(ม\.ค\.|ก\.พ\.|มี\.ค\.|เม\.ย\.|พ\.ค\.|มิ\.ย\.|ก\.ค\.|ส\.ค\.|ก\.ย\.|ต\.ค\.|พ\.ย\.|ธ\.ค\.|มกราคม|กุมภาพันธ์|มีนาคม|เมษายน|พฤษภาคม|มิถุนายน|กรกฎาคม|สิงหาคม|กันยายน|ตุลาคม|พฤศจิกายน|ธันวาคม)"
_NAMED_DATE_RE = re.compile(
    rf"\b\d{{1,2}}(st|nd|rd|th)?\s+{_MONTH_EN}\b|\b{_MONTH_EN}\.?\s+\d{{1,2}}(st|nd|rd|th)?\b|\d{{1,2}}\s*{_MONTH_TH}", re.IGNORECASE
)


def _names_unresolved_date(text: str, slots: dict) -> bool:
    """True when the question names a calendar date (e.g. '2 October', 'ตุลาคม 2') that the router did not turn into a day slot."""
    day = slots.get("day")
    if isinstance(day, str) and day[:2] == "20":  # an ISO date was resolved
        return False
    return bool(_NAMED_DATE_RE.search(text))


def detect_lang(text: str, fallback: str) -> str:
    if re.search(r"[฀-๿]", text):
        return "th"
    if re.search(r"[A-Za-z]{2,}", text):
        return "en"
    return fallback


def plan_for(r: Route, message: str) -> Plan:
    s = r.slots
    period = s.get("period")
    i = r.intent
    p = Plan()
    if i == "oer_value":
        p.calls = [("get_production_summary", {"business_date": "today"}, True), ("get_oer_trend", {"period": period or "7d"}, False)]
    elif i == "oer_why":
        p.calls = [("get_oer_trend", {"period": period or "7d"}, True), ("get_production_summary", {}, False),
                   ("get_active_alerts", {"module": "production", "include_findings": False}, False)]  # fmt: skip
    elif i == "inspect_first":
        p.calls = [("get_equipment_health", {"limit": 5}, True)]
    elif i == "equipment_status":
        p.calls = [("get_equipment_health", {"equipment_code": s.get("equipment_code")}, True)]
    elif i == "downtime_when":
        p.calls = [("get_downtime_analysis", {"period": period if period in ("7d", "30d") else "30d"}, True)]
    elif i == "downtime_effect":
        args = {"kind": "downtime", "downtime_hours": s.get("hours"), "equipment_code": s.get("equipment_code"), "planned": bool(s.get("planned"))}
        if not s.get("hours") and s.get("pct"):
            # hours are derived in the engine from the measured 30-day downtime (see _derive_downtime_hours)
            p.calls = [("get_downtime_analysis", {"period": "30d"}, True), ("run_business_scenario", {**args, "cut_pct": s["pct"]}, True)]
        else:
            if not s.get("hours"):
                args.update(downtime_hours=1.0, default_amount=True)
            p.calls = [("run_business_scenario", args, True)]
    elif i == "forecast":
        if re.search(r"energy|electric|kwh|power|พลังงาน|ไฟฟ้า", message, re.IGNORECASE):
            p.calls = [("get_energy_summary", {"period": "today"}, True)]
        else:
            p.calls = [("get_oer_trend", {"period": "7d"}, True)]
    elif i == "oer_what_if":
        p.calls = [("run_business_scenario", {"kind": "production", "oer_delta_pp": s.get("pp") if s.get("pp") is not None else 0.5}, True)]
    elif i == "energy_why":
        p.calls = [("get_energy_summary", {"period": period or "today"}, True)]
    elif i == "trucks_waiting":
        p.calls = [("get_logistics_summary", {}, True)]
    elif i == "prioritize":
        p.calls = [("get_active_alerts", {}, True)]
    elif i in ("daily_summary", "exec_brief"):
        p.calls = [("get_production_summary", {}, True), ("get_oer_trend", {"period": "7d"}, False), ("get_active_alerts", {}, False),
                   ("get_energy_summary", {}, False), ("get_logistics_summary", {}, False)]  # fmt: skip
        if i == "exec_brief":
            p.calls.append(("get_equipment_health", {"limit": 3}, False))
    elif i == "doc_search":
        p.calls = [("search_demo_documents", {"query": message[:300]}, True)]
    elif i == "supplier_trace":
        p.calls = [("get_supplier_trace", {"lot_code": s.get("lot_code")}, True)]
    if i in DOC_QUERY:
        p.calls.append(("search_demo_documents", {"query": DOC_QUERY[i], "k": 2}, False))
    for c in p.calls:  # drop None-valued args (the tool defaults apply)
        for k in [k for k, v in c[1].items() if v is None]:
            c[1].pop(k)
    return p


def _rate_check(key: str) -> None:
    now = time.monotonic()
    with _rate_lock:
        q = _rate.setdefault(key, deque())
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= RATE_PER_MINUTE:
            raise ApiError(429, "rate_limited", "Too many copilot questions for this session; wait a minute.", {"limit_per_minute": RATE_PER_MINUTE})
        q.append(now)


def _audit_tool(pending: list, ctx: DemoContext, res: ToolResult, conv_id: str) -> None:
    """Queue one audit row per tool call (written after all tools ran, so a failing tool's rollback cannot drop it)."""
    action = "copilot.tool_denied" if res.status == "denied" else "copilot.tool_call"
    pending.append((action, "copilot_tool", res.tool,
                {"copilot_session_id": conv_id, "arguments": res.args, "status": res.status, "result_digest": res.digest() if res.status == "ok" else None,
                       "message": res.message}))  # fmt: skip


def _evidence(res: ToolResult) -> dict[str, Any]:
    prov = res.provenance or {}
    return {"tool": res.tool, "arguments": res.args, "status": res.status, "result_digest": res.digest(), "provenance": prov or None,
            "as_of": prov.get("as_of"), "facts": [f.out() for f in res.facts], "assumptions": res.assumptions, "limits": res.limits}  # fmt: skip


def _tool_call_out(res: ToolResult) -> dict[str, Any]:
    return {"tool": res.tool, "arguments": res.args, "allowed": res.status != "denied", "status": res.status, "duration_ms": res.duration_ms,
            "result_summary": res.summary()}  # fmt: skip


def _citations(results: list[ToolResult]) -> list[dict[str, Any]]:
    cits = []
    seen = set()
    for r in results:
        if r.status != "ok":
            continue
        if r.tool == "search_demo_documents":
            for h in r.data.get("hits", []):
                if h["ref"] in seen:
                    continue
                seen.add(h["ref"])
                cits.append({"kind": "document", "ref": h["ref"], "title": h["title"], "snippet": h["snippet"], "url": h["url"], "doc_id": h["doc_id"],
                             "heading": h["heading"]})  # fmt: skip
        else:
            cits.append({"kind": "data", "ref": f"tool:{r.tool}", "title": TOOLS[r.tool].description, "snippet": (r.provenance or {}).get("source"),
                         "url": None, "doc_id": None, "heading": None})  # fmt: skip
    return cits


def _previous(db: Session, conv: CopilotSession | None) -> dict[str, Any] | None:
    if conv is None:
        return None
    m = db.execute(
        select(CopilotMessage).where(CopilotMessage.copilot_session_id == conv.id, CopilotMessage.sender == "assistant").order_by(CopilotMessage.id.desc()).limit(1)
    ).scalar_one_or_none()
    if not m or not m.intent or m.refused:
        return None
    meta = json.loads(m.tool_calls_json) if m.tool_calls_json else {}
    return {"intent": m.intent, "slots": meta.get("slots", {}) if isinstance(meta, dict) else {}}


def _conversation(db: Session, ctx: DemoContext, conv_id: str | None, title: str, mode: str, create: bool = True) -> CopilotSession | None:
    if not ctx.session_id:
        return None
    if conv_id:
        conv = db.get(CopilotSession, conv_id)
        if conv is not None and conv.session_id == ctx.session_id:
            n = db.execute(select(func.count(CopilotMessage.id)).where(CopilotMessage.copilot_session_id == conv.id)).scalar_one()
            if n >= MAX_MESSAGES_PER_CONVERSATION:
                raise ApiError(409, "conversation_full", "This conversation reached its message limit; start a new one.")
            return conv
    if not create:
        return None
    conv = CopilotSession(id=str(uuid.uuid4()), session_id=ctx.session_id, role=ctx.role.value, title=title[:200], mode=mode, created_at=datetime.now(UTC))
    db.add(conv)
    db.flush()
    return conv


def answer(db: Session, ctx: DemoContext, message: str, *, lang: str = "th", copilot_session_id: str | None = None,
           settings: Settings | None = None, llm_provider: Any = None, client_key: str | None = None) -> dict[str, Any]:  # fmt: skip
    _rate_check(ctx.session_id or client_key or "anonymous")
    text = normalise(message)
    if not text:
        raise ApiError(422, "empty_message", "Message is empty after normalisation.")
    lang = detect_lang(text, lang)
    provider = llm_provider
    if provider is None and settings is not None:
        from app.copilot.llm import provider_from_settings  # noqa: PLC0415

        provider = provider_from_settings(settings)
    mode = "llm" if provider is not None else "deterministic"
    conv = _conversation(db, ctx, copilot_session_id, text, mode, create=False)
    conv_id = conv.id if conv else str(uuid.uuid4())
    pending_audit: list[tuple] = []
    results: list[ToolResult] = []
    flags: list[str] = []
    r: Route | None = None
    llm_rejected = False
    verification = Verification()

    verdict = check_user_input(text)
    if verdict.blocked:
        kind = next(k for k in ("escalation", "sql", "injection", "accusation", "control") if k in verdict.flags)
        flags = list(verdict.flags)
        comp = C.refusal(lang, kind)
        intent = f"refused_{kind}"
        pending_audit.append(("copilot.refusal", "copilot_session", conv_id, {"reason": kind, "matched": verdict.matched[:3]}))
    else:
        r = route(text, _previous(db, conv))
        intent = r.intent
        comp = None
        if r.intent == "explicit_tool":
            names = r.slots.get("tool_names", [])
            unknown = [n for n in names if n not in TOOLS]
            if unknown:
                for n in unknown:
                    res = run_tool(db, ctx, n, {})
                    results.append(res)
                    _audit_tool(pending_audit, ctx, res, conv_id)
                comp = C.refusal(lang, "tool_denied", f"Unknown tool: {', '.join(unknown)} (only the read-only tools listed at /api/v1/copilot/tools exist).")
            else:
                name = names[0]
                intent = TOOL_TO_INTENT.get(name, "unknown")
                r = Route(intent, 1.0, "explicit_tool", r.slots)
        if comp is None and intent == "no_data":
            comp = C.no_data(lang)
        elif comp is None and intent == "clarify":
            comp = C.clarify(r.slots.get("options", ["daily_summary", "prioritize"]), lang)
        elif comp is None and intent in ("help", "unknown"):
            comp = C.help_text(lang, unknown=intent == "unknown")
        elif comp is None:
            run_ctx = ctx
            day = r.slots.get("day")
            day_iso = None
            try:
                if day and day != "today":
                    d = resolve_day(ctx, day)
                    day_iso = d.isoformat()
                    run_ctx = ctx_end_of_day(ctx, d)
            except (ApiError, ValueError) as exc:
                comp = C.Composition(C._L(lang, f"No data for that date: {getattr(exc, 'message', str(exc))}", f"ไม่มีข้อมูลของวันที่ดังกล่าว: {getattr(exc, 'message', str(exc))}"),
                                     uncertainty="no_data", refused=True, refusal_reason="no_data")  # fmt: skip
            if comp is None:
                plan = plan_for(r, text)
                denied_required = []
                for name, args, required in plan.calls:
                    tool_ctx = run_ctx
                    if name == "run_business_scenario" and args.get("cut_pct") and not args.get("downtime_hours"):
                        dt = next((x for x in results if x.tool == "get_downtime_analysis" and x.status == "ok"), None)
                        total = dt.fact("plant_downtime_h") if dt else None  # plant downtime (KPI definition), not maintenance-event sums
                        if total:
                            args = {**args, "downtime_hours": round(total * args["cut_pct"] / 100.0, 2)}
                    if name == "get_production_summary" and day_iso:
                        # the production service windows a past business day itself (full day); other tools get an earlier clock
                        args = {**args, "business_date": day_iso}
                        tool_ctx = ctx
                    res = run_tool(db, tool_ctx, name, args)
                    results.append(res)
                    _audit_tool(pending_audit, ctx, res, conv_id)
                    if res.sanitised:
                        flags.append("untrusted_data_neutralised")
                    if res.status == "denied" and required:
                        denied_required.append(res)
                        break
                if denied_required:
                    comp = C.refusal(lang, "tool_denied", denied_required[0].message)
                else:
                    comp = C.COMPOSERS[intent]({x.tool: x for x in results if x.status != "denied"}, lang)

    if not comp.refused and intent in C.INTENT_LABELS:
        comp.text = C.interpreted_as(intent, lang) + " " + comp.text
        if _names_unresolved_date(text, r.slots):
            comp.text = C.interpreted_as(intent, lang) + " " + C._L(
                lang,
                "Note: you named a specific date that I cannot resolve from the wording, so this answer is NOT for that date; it describes the selected demo clock (shown at the top of the page). Change the demo clock or scenario to look at another day.",
                "หมายเหตุ: คุณระบุวันที่เฉพาะเจาะจงที่ระบบอ่านจากถ้อยคำไม่ได้ คำตอบนี้จึงไม่ใช่ของวันนั้น แต่เป็นของ \"เวลาสาธิต\" ที่เลือกไว้ (แสดงที่ด้านบนของหน้า) เปลี่ยนเวลาสาธิตหรือสถานการณ์เพื่อดูวันอื่น",
            ) + comp.text[len(C.interpreted_as(intent, lang)):]

    # ---------------- grounding
    values = [f.value for x in results for f in x.facts] + numbers_from_text(text)
    if comp.refused or intent in ("help", "unknown", "clarify"):
        values += numbers_from_text(" ".join(C.CAPABILITIES[lang]))  # numbers inside the static example questions
    if intent == "clarify":
        values += [1.0, 2.0]  # option numbering "(1) ... (2)"
    verification = verify(comp.text, values)
    answer_text = comp.text
    if not verification.ok:
        # deterministic text must never ship unsupported numbers: degrade to an explicit uncertainty statement
        answer_text = C._L(lang, "I could not verify every number in the drafted answer against the tool results, so I am not showing it. "
                                 "Please see the evidence list for the raw values.",
                           "ไม่สามารถยืนยันตัวเลขทุกตัวในคำตอบกับผลจากเครื่องมือ จึงไม่แสดงคำตอบ กรุณาดูค่าดิบในรายการหลักฐาน")  # fmt: skip
        comp.uncertainty = "grounding_failed"
    llm_reason = None
    llm_used = False
    if provider is not None and not comp.refused and results and verification.ok:
        from app.copilot.llm import llm_answer  # noqa: PLC0415

        llm_text, llm_ver, extra, llm_reason = llm_answer(provider, db, ctx, text, lang, results)
        for res in extra:  # tools the LLM requested went through run_tool (allow-list) - audit them like any other call
            _audit_tool(pending_audit, ctx, res, conv_id)
            if res.status == "denied":
                flags.append("llm_tool_denied")
        results += [x for x in extra if x.status != "denied"]
        results_denied = [x for x in extra if x.status == "denied"]
        if llm_text is not None:
            answer_text, verification = llm_text, llm_ver
            llm_used = True
        else:
            llm_rejected = True  # deterministic composition is returned instead
        extra_denied = results_denied
    else:
        extra_denied = []

    mode = "llm" if llm_used else "deterministic"
    if comp.refused:
        flags = flags or ([comp.refusal_reason] if comp.refusal_reason in ("tool_denied",) else [])
    assumptions = [a for x in results if x.status == "ok" for a in x.assumptions]
    limits = sorted({lim for x in results if x.status == "ok" for lim in x.limits})
    if not conv:
        assumptions.append("Conversation not stored: no X-Demo-Session header (ADR-006), so follow-up questions have no memory.")
    kinds = {(x.provenance or {}).get("kind") for x in results if x.status == "ok"}
    prov = {"kind": "what_if" if "what_if" in kinds else "synthetic_actual",
            "source": "copilot:" + (",".join(x.tool for x in results if x.status == "ok") or "none"), "as_of": ctx.as_of,
            "model_version": "copilot-router@1" + (f"+llm:{getattr(provider, 'name', 'llm')}" if llm_used else "")}  # fmt: skip
    tool_calls = [_tool_call_out(x) for x in results + extra_denied]
    citations = _citations(results)
    out = {
        "copilot_session_id": conv_id, "answer": answer_text, "lang": lang, "mode": mode, "intent": intent, "tool_calls": tool_calls,
        "citations": citations, "assumptions": assumptions[:12], "uncertainty": comp.uncertainty, "refused": comp.refused,
        "refusal_reason": comp.refusal_reason, "provenance": prov, "evidence": [_evidence(x) for x in results if x.status != "denied"],
        "suggested_followups": comp.followups, "llm_answer_rejected": llm_rejected, "llm_rejection_reason": llm_reason, "verification": verification.out(),
        "safety_flags": sorted(set(flags)), "limits": limits[:10], "persisted": conv is not None,
        "route": {"method": r.method, "confidence": r.confidence, "slots": {k: v for k, v in r.slots.items()}, "exemplar": r.exemplar} if r else None,
    }  # fmt: skip
    for action, etype, eid, after in pending_audit:
        write_audit(db, ctx, action, etype, eid, after=after)
    if ctx.session_id and conv is None:
        conv = CopilotSession(id=conv_id, session_id=ctx.session_id, role=ctx.role.value, title=text[:200], mode=mode, created_at=datetime.now(UTC))
        db.add(conv)
        db.flush()
        out["persisted"] = True
        out["assumptions"] = [a for a in out["assumptions"] if not a.startswith("Conversation not stored")]
    if conv is not None:
        db.add(CopilotMessage(copilot_session_id=conv.id, session_id=ctx.session_id, sender="user", content=text, created_at=datetime.now(UTC)))
        db.add(CopilotMessage(copilot_session_id=conv.id, session_id=ctx.session_id, sender="assistant", content=answer_text, intent=intent[:48],
                              tool_calls_json=json.dumps({"tool_calls": tool_calls, "slots": r.slots if r else {}}, default=str),
                              citations_json=json.dumps(citations, default=str), refused=comp.refused, created_at=datetime.now(UTC)))  # fmt: skip
    db.commit()
    return out
