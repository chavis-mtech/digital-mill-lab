"""Maintenance history: preventive rounds at the Sunday stop, breakdown/corrective work orders (linked to the rule
alert that preceded them when one exists), maintenance events, status history and the seeded audit-log baseline.

Consistency rules: a breakdown's maintenance_event.downtime_min equals the stop the mill simulation applied; a
repair that ends a degradation episode (PRS-01, DIG-02, CTF-01, boiler fouling, FWP-01 strainer, clarifier valve)
is the moment the sensor series recover; PRS-03 has NO work order (open or closed) after its degradation onset so
the guided tour can create one; a few unrelated work orders are still open at the anchor.
"""

from __future__ import annotations

import json

from app.models.platform import AuditLog
from app.seed.registry import TECHNICIANS
from app.services.audit import GENESIS, _fields, compute_hash

ROTATION = ["PRS-01", "DIG-01", "THR-01", "LR-CNV-01", "PRS-02", "DIG-02", "CTF-01", "BLR-FAN-01", "PRS-03", "DIG-03", "THR-02",
            "CNV-02", "PRS-04", "DIG-04", "CTF-02", "FWP-01", "KRN-01", "RPL-01", "PMP-CO-01", "TG-01", "WTP-PMP-01", "POME-PMP-01"]
SKILL = {"PRS": "mechanical", "DIG": "mechanical", "THR": "mechanical", "LR-": "mechanical", "CNV": "mechanical", "CTF": "mechanical",
         "BLR": "mechanical", "FWP": "mechanical", "KRN": "mechanical", "RPL": "mechanical", "PMP": "mechanical", "TG-": "electrical",
         "WTP": "mechanical", "POM": "mechanical", "WB-": "instrument", "STR": "mechanical", "CLR": "instrument", "DG-": "electrical"}


class MaintBuilder:
    def __init__(self, core, ids, alerts) -> None:
        self.core, self.ids, self.alerts = core, ids, alerts
        self.tb = core.tb
        self.rng = core.rngs.get("maintenance")
        self.techs = [{"id": i + 1, "code": c, "display_name": n, "skill": s, "shift_code": sh, "is_active": True, "data_kind": "synthetic"}
                      for i, (c, n, s, sh) in enumerate(TECHNICIANS)]
        self.wos: list[dict] = []
        self.hist: list[dict] = []
        self.events: list[dict] = []

    def tech_for(self, eq: str) -> int:
        skill = SKILL.get(eq[:3], "general")
        cands = [t["id"] for t in self.techs if t["skill"] == skill] or [t["id"] for t in self.techs]
        return int(self.rng.choice(cands))

    def wo(self, eq, title, desc, priority, source, created, transitions, est_dt, alert_id=None, due=None, notes=None, role="maintenance_engineer"):
        tb = self.tb
        created = max(created, 0.0)  # never before the window start
        transitions = [(s, max(t, created + 1 + k)) for k, (s, t) in enumerate(transitions)]
        wid = len(self.wos) + 1
        status = transitions[-1][0] if transitions else "open"
        resolved = next((t for s, t in transitions if s == "resolved"), None)
        tech = self.tech_for(eq) if any(s == "assigned" for s, _ in transitions) else None
        self.wos.append({
            "id": wid, "code": f"WO-{tb.date_of(created):%Y%m}-{wid:04d}", "session_id": None, "cloned_from_id": None,
            "equipment_id": self.ids["equip"][eq], "title": title, "description": desc, "priority": priority, "status": status,
            "source_type": source, "alert_id": alert_id, "recommendation_id": None, "anomaly_event_id": None,
            "assigned_technician_id": tech, "created_by_role": role, "created_at": tb.ts(created), "demo_as_of": tb.ts(created),
            "due_at": tb.ts(due) if due is not None else None, "resolved_at": tb.ts(resolved) if resolved is not None else None,
            "resolution_notes": notes if resolved is not None else None, "estimated_downtime_h": est_dt, "data_kind": "synthetic",
        })
        prev = None
        for s, t in [("open", created)] + list(transitions):
            self.hist.append({"id": len(self.hist) + 1, "work_order_id": wid, "session_id": None, "from_status": prev, "to_status": s,
                              "actor_role": "factory_manager" if s == "closed" else "maintenance_engineer", "changed_at": tb.ts(t),
                              "note": {"open": "Work order created", "assigned": "Technician assigned", "in_progress": "Work started",
                                       "resolved": "Maintenance record written", "closed": "Verified by engineer", "on_hold": "Waiting for spare parts"}.get(s)})
            prev = s
        return wid, tech

    def event(self, eq, wo_id, etype, s, e, planned, desc, tech, parts=None):
        self.events.append({
            "id": len(self.events) + 1, "equipment_id": self.ids["equip"][eq], "work_order_id": wo_id, "session_id": None, "event_type": etype,
            "start_ts": self.tb.ts(s), "end_ts": self.tb.ts(e), "downtime_min": round(e - s, 1), "planned": planned, "description": desc,
            "parts_cost_thb": round(parts if parts is not None else float(self.rng.lognormal(8.0, 0.8)), 0),
            "labour_cost_thb": round((e - s) / 60 * 350 * float(self.rng.uniform(1.5, 3)), 0), "technician_id": tech, "data_kind": "synthetic_actual",
        })


def build_maintenance(core, ids, alerts: list[dict]) -> dict:
    tb, mods = core.tb, core.mods
    mb = MaintBuilder(core, ids, alerts)
    A_ = tb.days - 1
    end = tb.minutes
    press_onset = next((i.start for i in core.injected if i.code == "INJ-PRS-BRG"), None)

    def closed_after(t_res, extra_h=20):
        tc = t_res + extra_h * 60
        return [("closed", tc)] if tc < end else []

    # ---- breakdown / corrective work orders
    items = sorted(mods.breakdowns, key=lambda b: b.start)
    repairs = {}
    for b in items:
        eq = b.equipment_code
        al = [a for a in alerts if a["_equip"] == eq and b.start - 10 * 1440 <= a["_t"] <= b.start]
        alert_id = al[0]["id"] if al else None
        if alert_id is not None:
            created = min(al[0]["_t"] + 14 * 60, b.start - 30)
            created = max(created, al[0]["_t"] + 5)
            src = "alert"
        elif b.planned:
            created = b.start - 2 * 1440
            src = "manual"
        else:
            created = b.start + 10
            src = "manual"
        trans = [("assigned", max(created + 15, min(b.start + 20, created + 600)) if b.start > created else created + 15)]
        t_ip = max(trans[0][1] + 5, b.start + 30 if not b.planned else b.start)
        trans.append(("in_progress", t_ip))
        t_res = max(b.end, t_ip + 10)
        if t_res >= end:
            continue
        trans.append(("resolved", t_res))
        trans += closed_after(t_res)
        prio = "urgent" if b.impact == "plant" else "high" if (b.impact in ("press", "thresher") or alert_id) else "medium"
        title = {"breakdown": f"Breakdown repair - {eq}", "corrective": f"Corrective maintenance - {eq}"}[b.event_type]
        wid, tech = mb.wo(eq, title, b.description, prio, src, created, trans, round((b.end - b.start) / 60, 2), alert_id=alert_id,
                          due=b.end if b.planned else None, notes=b.description)
        etype = b.event_type
        mb.event(eq, wid, etype, b.start, b.end, b.planned, b.description, tech)
        repairs[b.code] = wid
    # ---- corrective actions that end background equipment episodes (done during the Sunday stop)
    for inj in core.injected:
        if inj.code not in ("INJ-BG-DIG02", "INJ-BG-CTF01") or inj.end >= end:
            continue
        eq = inj.equipment_code
        s = inj.end
        e = s + 150
        desc = {"INJ-BG-DIG02": "DIG-02 drive bearing re-greased and lubrication interval shortened (found running warm on the trend).",
                "INJ-BG-CTF01": "CTF-01 bowl cleaned of sludge build-up and rotor re-balanced (vibration trend rising, below alarm)."}[inj.code]
        trans = [("assigned", s - 1440), ("in_progress", s), ("resolved", e)] + closed_after(e)
        wid, tech = mb.wo(eq, f"Planned corrective - {eq}", desc, "medium", "manual", s - 2 * 1440, trans, 2.5, due=s, notes=desc)
        mb.event(eq, wid, "lubrication" if "DIG" in eq else "corrective", s, e, True, desc, tech)
    # ---- preventive rounds at each Sunday stop (+ monthly weighbridge calibration)
    ptr = 0
    for d in range(tb.days):
        if tb.weekday(d) != 6:
            continue
        s0 = d * 1440 + 5 * 60 + 15
        todo = []
        while len(todo) < 4:
            eq = ROTATION[ptr % len(ROTATION)]
            ptr += 1
            if eq == "PRS-03" and press_onset is not None and s0 >= press_onset - 1440:
                continue
            todo.append(eq)
        if tb.day_date(d).day <= 7:
            todo += ["WB-01", "WB-02"]
        for k, eq in enumerate(todo):
            s = s0 + 20 * k
            dur = float(mb.rng.uniform(60, 240))
            e = s + dur
            if e >= end:
                continue
            etype = "calibration" if eq.startswith("WB") else ("lubrication" if k % 2 == 0 else "inspection")
            desc = {"calibration": f"Monthly weighbridge calibration with certified test weights ({eq}).",
                    "lubrication": f"Weekly lubrication round: bearings greased, oil levels topped up ({eq}).",
                    "inspection": f"Weekly inspection: belts/chains, couplings, alignment and guards checked; no defect found ({eq})."}[etype]
            created = s - 3 * 1440
            trans = [("assigned", s - 2 * 1440 + 9 * 60), ("in_progress", s), ("resolved", e)] + closed_after(e)
            wid, tech = mb.wo(eq, f"Preventive maintenance - {eq} ({etype})", desc, "low", "preventive", created, trans, round(dur / 60, 2),
                              due=s, notes=desc)
            mb.event(eq, wid, etype, s, e, True, desc, tech, parts=float(mb.rng.lognormal(6.5, 0.6)))
    # ---- work orders still open at the anchor (unrelated to PRS-03)
    opens = [
        ("POME-PMP-01", "POME transfer pump mechanical seal leak", "Seal weeping at the gland; standby pump in service while waiting for the seal kit.",
         "medium", [("assigned", (A_ - 2) * 1440 + 10 * 60), ("in_progress", (A_ - 1) * 1440 + 9 * 60)], (A_ - 2) * 1440 + 9 * 60, None),
        ("CTF-02", "Planned bowl overhaul - CTF-02", "Scheduled 4,000 h bowl overhaul (disc stack, seals).", "low",
         [("assigned", (A_ - 1) * 1440 + 14 * 60)], (A_ - 4) * 1440 + 9 * 60, (A_ + 5) * 1440 + 6 * 60),
        ("DIG-04", "Mash temperature transmitter calibration - DIG-04", "Two-point calibration requested after a drift check; waiting for the reference RTD.",
         "low", [("assigned", (A_ - 6) * 1440 + 11 * 60), ("on_hold", (A_ - 5) * 1440 + 10 * 60)], (A_ - 6) * 1440 + 10 * 60, (A_ + 3) * 1440),
        ("KRN-01", "Nut cracker rotor wear inspection - KRN-01", "Kernel losses in shell trending at the upper end of normal; inspect cracker rotor.",
         "medium", [], A_ * 1440 + 9 * 60, (A_ + 2) * 1440),
    ]
    for eq, title, desc, prio, trans, created, due in opens:
        if created < 0 or any(t >= end for _, t in trans) or created >= end:
            continue
        mb.wo(eq, title, desc, prio, "manual", created, trans, None, due=due)
    # renumber WOs chronologically by creation for readable codes
    order = sorted(range(len(mb.wos)), key=lambda i: (mb.wos[i]["created_at"], mb.wos[i]["id"]))
    remap = {mb.wos[i]["id"]: k + 1 for k, i in enumerate(order)}
    wos = []
    for k, i in enumerate(order):
        w = dict(mb.wos[i])
        w["id"] = k + 1
        w["code"] = f"WO-{w['created_at']:%Y%m}-{k + 1:04d}"
        wos.append(w)
    for h in mb.hist:
        h["work_order_id"] = remap[h["work_order_id"]]
    hist = sorted(mb.hist, key=lambda h: (h["changed_at"], h["work_order_id"]))
    for k, h in enumerate(hist, start=1):
        h["id"] = k
    events = sorted(mb.events, key=lambda e: (e["start_ts"], e["equipment_id"]))
    for k, e in enumerate(events, start=1):
        e["id"] = k
        if e["work_order_id"]:
            e["work_order_id"] = remap[e["work_order_id"]]
    # alerts that led to a work order are 'in_progress' until resolved by their own data
    wo_alerts = {w["alert_id"] for w in wos if w["alert_id"]}
    for a in alerts:
        if a["id"] in wo_alerts and a["status"] == "new":
            a["status"] = "in_progress"
    audit = build_audit(tb, wos, hist)
    return {"technicians": mb.techs, "work_orders": wos, "work_order_status_history": hist, "maintenance_events": events, "audit_logs": audit}


def build_audit(tb, wos, hist) -> list[dict]:
    code_by_id = {w["id"]: w["code"] for w in wos}
    rows = []
    prev = GENESIS
    entries = [(tb.ts(0), "system_admin", "seed.baseline", "dataset", "synthetic-baseline", None,
                json.dumps({"note": "Seeded synthetic baseline (shared, read-only). Not real plant data."}, sort_keys=True), None)]
    for h in hist:
        action = "work_order.create" if h["from_status"] is None else "work_order.transition"
        before = None if h["from_status"] is None else json.dumps({"status": h["from_status"]}, sort_keys=True)
        entries.append((h["changed_at"], h["actor_role"], action, "work_order", code_by_id[h["work_order_id"]], before,
                        json.dumps({"status": h["to_status"]}, sort_keys=True), h["changed_at"]))
    for k, (ts, role, action, etype, eid, before, after, as_of) in enumerate(entries, start=1):
        row = AuditLog(ts=ts, session_id=None, role=role, actor=f"demo:{role}", action=action, entity_type=etype, entity_id=eid,
                       before_json=before, after_json=after, request_id=None, demo_as_of=as_of)
        row.prev_hash = prev
        row.hash = compute_hash(prev, _fields(row))
        prev = row.hash
        rows.append({"id": k, "ts": ts, "session_id": None, "role": role, "actor": f"demo:{role}", "action": action, "entity_type": etype,
                     "entity_id": eid, "before_json": before, "after_json": after, "request_id": None, "demo_as_of": as_of,
                     "prev_hash": row.prev_hash, "hash": row.hash})
    return rows
