"""Row builders for logistics, production, traceability, quality, energy tables (from the simulated state).

Mass-balance identities hold by construction and are re-checked by validate.py:
  ticket.net = gross - tare; delivery.net = ticket.net; ffb_batch.mass = delivery.net;
  sum(batch_inputs.mass) = production_batch.ffb_input; cpo = ffb x oer/100 (per hour, batch, shift, lot);
  lot.quantity = sum(lot_compositions.cpo); CPO stock: produced = dispatched + delta stock.
"""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

from app.seed.assumptions import A, P
from app.seed.energy import STAGE_STEAM_SHARE, friction_term
from app.seed.logistics import queue_lengths, truck_status

R2, R3, R4 = 2, 3, 4


def _r(x, n=3):
    if x is None:
        return None
    if isinstance(x, float) and math.isnan(x):
        return None
    return round(float(x), n)


def build_logistics(core, facility_id: int) -> dict:
    tb, trucks, sups = core.tb, core.trucks, core.suppliers
    trips, tickets, deliveries, batches, qevents = [], [], [], [], []
    truck_to_batch: dict[int, int] = {}
    # queue length at every event time, computed once (vectorised)
    ev_times = []
    for t in trucks:
        for v in (t.arrival, t.queue_start, t.weigh_in - 0.5 if t.weigh_in is not None else None, t.weigh_in, t.graded_end,
                  t.unload_start, t.unload_end, t.weigh_out, t.exit):
            if v is not None:
                ev_times.append(v)
    tarr = np.unique(np.array(ev_times))
    qlen_lookup = dict(zip(tarr.tolist(), queue_lengths(trucks, tarr).tolist(), strict=True))
    qid = 0
    for t in trucks:
        tid = t.idx + 1
        sp = sups[t.supplier]
        ts = tb.ts
        trips.append({
            "id": tid, "code": f"TRP-{tb.date_of(t.arrival):%Y%m%d}-{tid:05d}", "facility_id": facility_id, "supplier_id": sp.id,
            "plate_masked": t.plate, "truck_type": t.ttype.replace("_", "-"), "arrival_ts": ts(t.arrival),
            "queue_start_ts": ts(t.queue_start) if t.queue_start is not None else None,
            "weigh_in_ts": ts(t.weigh_in) if t.weigh_in is not None else None,
            "grading_ts": ts(t.grading) if t.grading is not None else None,
            "unload_start_ts": ts(t.unload_start) if t.unload_start is not None else None,
            "unload_end_ts": ts(t.unload_end) if t.unload_end is not None else None,
            "weigh_out_ts": ts(t.weigh_out) if t.weigh_out is not None else None,
            "exit_ts": ts(t.exit) if t.exit is not None else None,
            "status": truck_status(t), "data_kind": "synthetic_actual",
        })
        ev = [("arrived", t.arrival, "gate"), ("queued", t.queue_start, "gate"),
              ("called", (t.weigh_in - 0.5) if t.weigh_in is not None else None, "gate"),
              ("weigh_in", t.weigh_in, f"bridge-{t.bridge_in + 1}"), ("graded", t.graded_end, "grading"),
              ("unload_start", t.unload_start, f"ramp-{t.bay + 1}"), ("unload_end", t.unload_end, f"ramp-{t.bay + 1}"),
              ("weigh_out", t.weigh_out, f"bridge-{t.bridge_out + 1}"), ("exited", t.exit, "gate")]
        for etype, tv, loc in ev:
            if tv is None:
                continue
            qid += 1
            qlen = qlen_lookup[tv]
            qevents.append({"id": qid, "truck_trip_id": tid, "ts": ts(max(tv, t.arrival)), "event_type": etype,
                            "queue_length": int(max(qlen, 0)), "location": loc})
        if t.weigh_in is None:
            continue
        gross = t.tare_kg + t.payload_kg
        done = t.weigh_out is not None
        tickets.append({
            "id": tid, "ticket_no": f"WB-{tb.date_of(t.weigh_in):%Y%m%d}-{tid:05d}", "truck_trip_id": tid,
            "bridge_code": f"WB-0{t.bridge_in + 1}", "weigh_in_ts": ts(t.weigh_in), "weigh_out_ts": ts(t.weigh_out) if done else None,
            "gross_kg": int(gross), "tare_kg": int(t.tare_kg) if done else None, "net_kg": int(gross - t.tare_kg) if done else None,
            "operator_code": f"WB-OP-{(int(t.weigh_in // 720) % 4) + 1:02d}", "data_kind": "synthetic_actual",
        })
        if not done:
            continue
        net = gross - t.tare_kg
        rec = t.unload_end if t.unload_end is not None else t.graded_end
        ripe = max(0.0, 100 - t.unripe - t.overripe - t.empty_bunch)
        did = len(deliveries) + 1
        deliveries.append({
            "id": did, "code": f"DLV-{tb.date_of(rec):%Y%m%d}-{tid:05d}", "facility_id": facility_id, "supplier_id": sp.id,
            "plantation_id": t.plantation_id, "truck_trip_id": tid, "ticket_id": tid, "business_date": tb.date_of(rec),
            "received_ts": ts(rec), "net_kg": int(net), "grade": t.grade, "ripe_pct": _r(ripe, 1), "unripe_pct": _r(min(t.unripe, 100), 1),
            "overripe_pct": _r(t.overripe, 1), "empty_bunch_pct": _r(t.empty_bunch, 1), "long_stalk_pct": _r(t.long_stalk, 1),
            "deduction_pct": _r(t.deduction_pct, 2), "accepted_kg": 0 if t.reject else int(round(net * (1 - t.deduction_pct / 100))),
            "harvest_to_mill_h": _r(t.h2m_h, 1), "data_kind": "synthetic_actual",
        })
        truck_to_batch[t.idx] = did
        batches.append({
            "id": did, "code": f"FFB-{tb.date_of(rec):%Y%m%d}-{did:05d}", "delivery_id": did, "facility_id": facility_id,
            "received_ts": ts(rec), "mass_kg": int(net), "grade": t.grade, "ramp_code": f"RAMP-{t.bay + 1}" if not t.reject else None,
            "status": "rejected" if t.reject else "waiting", "processed_start_ts": None, "data_kind": "synthetic_actual",
        })
    # ffb batch processing status from the mill's FIFO
    rb_to_batch = {}
    for rb in core.batches:
        bid = truck_to_batch[rb.truck_idx]
        rb_to_batch[rb.batch_id] = bid
        row = batches[bid - 1]
        if rb.first_processed is not None:
            row["processed_start_ts"] = tb.ts(rb.first_processed)
            row["status"] = "processed" if rb.remaining_kg <= 1e-6 else "partially_processed"
    return {"truck_trips": trips, "weighbridge_tickets": tickets, "ffb_deliveries": deliveries, "ffb_batches": batches,
            "queue_events": qevents, "_rb_to_batch": rb_to_batch, "_truck_to_batch": truck_to_batch}


def press_current_a(core, eq_state) -> np.ndarray:
    press = [e for e in core.equip if e.load_kind == "press"]
    H = core.tb.hours
    num = np.zeros(H)
    den = np.zeros(H)
    for e in press:
        s = eq_state[e.code]
        cur = e.fla_a * (0.30 + 0.62 * s["load"] + friction_term(core, e)) * s["cur_mult"]
        on = s["run"] > 0.05
        num += np.where(on, cur, 0)
        den += on
    return np.divide(num, den, out=np.full(H, np.nan), where=den > 0)


def build_production(core, ids: dict, eq_state, log: dict) -> dict:
    tb, m = core.tb, core.mill
    H, D = tb.hours, tb.days
    fac, line = ids["facility"], ids["line"]
    rng = core.rngs.get("outputs.production")
    press_a = press_current_a(core, eq_state)
    # ---- process_hourly
    ph = []
    for h in range(H):
        proc = m["processed_t"][h]
        has = proc > 1e-9
        ph.append({
            "id": h + 1, "facility_id": fac, "line_id": line, "ts": tb.ts(h * 60), "running_minutes": _r(m["running_min"][h], 2),
            "downtime_min": _r(m["downtime_min"][h], 2), "ffb_received_t": _r(m["received_t"][h], 3), "ffb_processed_t": _r(proc, 3),
            "throughput_tph": _r(m["tph"][h], 3), "ffb_waiting_t": _r(m["waiting_t"][h], 3),
            "avg_wait_to_process_h": _r(m["avg_wait_h"][h], 2) if has else None,
            "sterilizer_cycles": int(m["cycles"][h]), "sterilizer_cycle_min": _r(m["cycle_min"][h], 1) if has else None,
            "steam_pressure_bar": _r(m["hdr_p"][h], 3), "boiler_steam_t": _r(m["boiler_steam_t"][h], 3),
            "digester_temp_c": _r(m["dig_temp"][h], 2), "press_load_a": _r(press_a[h], 1) if has else None,
            "press_cone_pressure_bar": _r(m["press_cone"][h], 2) if has else None, "clarifier_temp_c": _r(m["clar_temp"][h], 2),
            "oil_loss_press_fibre_pct": _r(m["loss_fibre"][h], 4) if has else None, "oil_loss_efb_pct": _r(m["loss_efb"][h], 4) if has else None,
            "oil_loss_sludge_pct": _r(m["loss_sludge"][h], 4) if has else None, "oil_loss_nut_pct": _r(m["loss_nut"][h], 4) if has else None,
            "oil_loss_total_pct": _r(m["loss_total"][h], 4) if has else None,
            "cpo_t": _r(m["cpo_t"][h], 4), "kernel_t": _r(m["kernel_t"][h], 4),
            "oer_pct": _r(m["oer"][h], 4) if has else None, "ker_pct": _r(m["ker"][h], 4) if has else None,
            "ffb_ripe_pct": _r(m["ripe"][h], 2) if has else None, "data_kind": "synthetic_actual",
        })
    # make process_hourly cpo/kernel exactly consistent with the rounded oer
    for r in ph:
        if r["oer_pct"] is not None:
            r["cpo_t"] = round(r["ffb_processed_t"] * r["oer_pct"] / 100, 4)
            r["kernel_t"] = round(r["ffb_processed_t"] * r["ker_pct"] / 100, 4)
    # ---- shifts (A 06-18, B 18-06 next day; mill-local)
    shifts = []
    shift_of_hour = np.zeros(H, dtype=int)
    sid = 0
    for d in range(D):
        for code, h0 in (("A", d * 24 + 6), ("B", d * 24 + 18)):
            h1 = min(h0 + 12, H)
            if h0 >= H:
                continue
            sid += 1
            sl = slice(h0, h1)
            ffb = sum(ph[h]["ffb_processed_t"] for h in range(h0, h1))
            cpo = sum(ph[h]["cpo_t"] for h in range(h0, h1))
            ker = sum(ph[h]["kernel_t"] for h in range(h0, h1))
            shifts.append({
                "id": sid, "facility_id": fac, "business_date": tb.day_date(d), "shift_code": code, "start_ts": tb.ts(h0 * 60),
                "end_ts": tb.ts(h1 * 60), "ffb_processed_t": round(ffb, 3), "cpo_t": round(cpo, 4), "kernel_t": round(ker, 4),
                "oer_pct": round(cpo / ffb * 100, 4) if ffb > 0 else None, "ker_pct": round(ker / ffb * 100, 4) if ffb > 0 else None,
                "operating_hours": round(float(m["running_min"][sl].sum()) / 60, 3), "downtime_min": round(float(m["downtime_min"][sl].sum()), 2),
                "supervisor_code": f"SUP-{code}{(d % 3) + 1}", "data_kind": "synthetic_actual",
            })
            shift_of_hour[h0:h1] = sid
    # ---- production batches (2-hour blocks)
    bh = int(A("production_batch_hours"))
    pbatches, byp = [], []
    block_of_hour = np.zeros(H, dtype=int)
    for b0 in range(0, H, bh):
        hs = range(b0, min(b0 + bh, H))
        ffb = sum(ph[h]["ffb_processed_t"] for h in hs)
        if ffb <= 0.05:
            continue
        cpo = sum(ph[h]["cpo_t"] for h in hs)
        ker = sum(ph[h]["kernel_t"] for h in hs)
        pid = len(pbatches) + 1
        oer = cpo / ffb * 100
        kr = ker / ffb * 100
        w = np.array([ph[h]["ffb_processed_t"] for h in hs])
        cyc = float(np.average([m["cycle_min"][h] for h in hs], weights=w)) if w.sum() > 0 else None
        pbatches.append({
            "id": pid, "code": f"PB-{tb.date_of(b0 * 60):%Y%m%d}-{(b0 % 24):02d}", "facility_id": fac, "line_id": line,
            "shift_id": int(shift_of_hour[b0]) or None, "start_ts": tb.ts(b0 * 60), "end_ts": tb.ts((b0 + len(hs)) * 60),
            "ffb_input_t": round(ffb, 3), "cpo_t": round(ffb * round(oer, 4) / 100, 4), "kernel_t": round(ffb * round(kr, 4) / 100, 4),
            "oer_pct": round(oer, 4), "ker_pct": round(kr, 4), "sterilizer_cycle_min": _r(cyc, 1), "trace_method": "mass_balance",
            "status": "completed", "data_kind": "synthetic_actual",
        })
        for h in hs:
            block_of_hour[h] = pid
        for prod, pct, dest in (("kernel", kr, "sale"), ("shell", P("shell_pct_ffb"), "boiler_fuel"), ("fibre", P("fibre_pct_ffb"), "boiler_fuel"),
                                ("efb", P("efb_pct_ffb"), "mulch"), ("pome", P("pome_t_per_t_ffb") * 100, "biogas_pond")):
            if prod != "kernel":
                pct = pct * float(rng.lognormal(0, 0.02))
            byp.append({"id": len(byp) + 1, "production_batch_id": pid, "product": prod, "quantity_t": round(ffb * pct / 100, 4),
                        "pct_of_ffb": round(pct, 3), "destination": dest, "data_kind": "synthetic_actual"})
    pb_by_id = {b["id"]: b for b in pbatches}
    # ---- batch inputs (FFB batch -> processing batch, mass balance)
    agg: dict[tuple[int, int], float] = defaultdict(float)
    rb2b = log["_rb_to_batch"]
    for h, rbid, kg in m["cons"]:
        agg[(int(block_of_hour[h]), rb2b[rbid])] += kg
    binputs = []
    tot_by_pb: dict[int, float] = defaultdict(float)
    for (pb, _fb), kg in agg.items():
        tot_by_pb[pb] += kg
    for (pb, fb), kg in sorted(agg.items()):
        if kg < 0.05:
            continue
        binputs.append({"id": len(binputs) + 1, "ffb_batch_id": fb, "production_batch_id": pb, "mass_kg": round(kg, 2),
                        "mass_share": round(min(1.0, kg / tot_by_pb[pb]), 6), "trace_method": "mass_balance"})
    # ---- CPO lots: one lot per business day into the receiving tank; dispatch oldest lots (>= 3 days) above min stock
    n_tank = int(P("cpo_storage_tank_count"))
    tank_cap = P("cpo_storage_tank_capacity_t")
    lots, comps = [], []
    tank_level = np.zeros((n_tank, H))
    levels = np.zeros(n_tank)
    in_storage: list[dict] = []
    recv_tank = 0
    lot_by_day: dict[int, dict] = {}
    lot_ffa: dict[int, float] = {}
    for d in range(D):
        hs = range(d * 24, d * 24 + 24)
        day_cpo = sum(ph[h]["cpo_t"] for h in hs)
        if day_cpo > 0:
            if levels[recv_tank] + 320 > tank_cap:
                recv_tank = int(np.argmin(levels))
            run_hours = [h for h in hs if ph[h]["ffb_processed_t"] > 0]
            lot = {"id": len(lots) + 1, "code": f"CPO-{tb.day_date(d):%Y%m%d}-T{recv_tank + 1}", "facility_id": fac,
                   "tank_code": f"TNK-0{recv_tank + 1}", "fill_start_ts": tb.ts(run_hours[0] * 60), "fill_end_ts": None,
                   "quantity_t": 0.0, "ffa_pct": None, "moisture_pct": None, "dirt_pct": None, "dobi": None, "status": "filling",
                   "dispatched_at": None, "data_kind": "synthetic_actual", "_tank": recv_tank, "_day": d}
            lots.append(lot)
            lot_by_day[d] = lot
        for h in hs:
            if day_cpo > 0:
                levels[recv_tank] += ph[h]["cpo_t"]
            # dispatch at 10:00 local
            if h % 24 == 10:
                k_disp = 0
                stock = levels.sum()
                for lt in sorted(in_storage, key=lambda x: x["_day"]):
                    if d - lt["_day"] < A("cpo_lot_min_age_days") or stock - lt["quantity_t"] < A("cpo_min_stock_t"):
                        break
                    lt["dispatched_at"] = tb.ts(h * 60 + 15 + 75 * k_disp)
                    k_disp += 1
                    lt["status"] = "dispatched"
                    levels[lt["_tank"]] -= lt["quantity_t"]
                    stock -= lt["quantity_t"]
                    in_storage.remove(lt)
            tank_level[:, h] = levels
        if day_cpo > 0:
            lot = lot_by_day[d]
            day_pbs = sorted({int(block_of_hour[h]) for h in hs if block_of_hour[h] > 0})
            qty = sum(pb_by_id[p]["cpo_t"] for p in day_pbs)
            lot["quantity_t"] = round(qty, 4)
            for p in day_pbs:
                c = pb_by_id[p]["cpo_t"]
                if c > 0:
                    comps.append({"id": len(comps) + 1, "cpo_lot_id": lot["id"], "production_batch_id": p, "cpo_t": round(c, 4),
                                  "share": round(min(1.0, c / qty), 6), "trace_method": "mass_balance"})
            w = np.array([ph[h]["cpo_t"] for h in hs])
            def wavg(key, default, hs=hs, w=w):
                vals = np.array([m[key][h] for h in hs])
                ok = (w > 0) & ~np.isnan(vals)
                return float(np.average(vals[ok], weights=w[ok])) if ok.any() else default
            ffa = float(np.clip(wavg("ffa", 3.0) + rng.normal(0, 0.06), 1.5, 8.0))
            delay = wavg("delay_h", 24.0)
            over = wavg("overripe", 8.0)
            uc = wavg("undercook", 0.0)
            clar = wavg("clar_temp", 90.0)
            lot["ffa_pct"] = round(ffa, 3)
            lot["moisture_pct"] = round(float(np.clip(P("cpo_moisture_pct") + 0.012 * max(0.0, 90 - clar) + rng.normal(0, 0.015), 0.06, 0.3)), 3)
            lot["dirt_pct"] = round(float(np.clip(P("cpo_dirt_pct") + 0.01 * uc + rng.normal(0, 0.006), 0.01, 0.1)), 3)
            lot["dobi"] = round(float(np.clip(A("dobi_fresh") - 0.015 * max(0.0, delay - 24) - 0.04 * max(0.0, over - 8) - 0.6 * uc + rng.normal(0, 0.05), 1.5, 4.0)), 2)
            lot_ffa[lot["id"]] = ffa
            last = max(h for h in hs if ph[h]["cpo_t"] > 0)
            if d < D - 1:
                lot["fill_end_ts"] = tb.ts((last + 1) * 60)
                lot["status"] = "in_storage"
                in_storage.append(lot)
    lot_rows = [{k: v for k, v in lt.items() if not k.startswith("_")} for lt in lots]
    # ---- quality measurements (lab, LIMS-like)
    qm = []
    def add(ts_min, point, param, value, unit, pb=None, lot=None, dlv=None, method=None, notes=None):
        qm.append({"id": len(qm) + 1, "facility_id": fac, "sample_ts": tb.ts(ts_min), "sample_point": point, "parameter": param,
                   "value": round(float(value), 4), "unit": unit, "production_batch_id": pb, "cpo_lot_id": lot, "ffb_delivery_id": dlv,
                   "method": method, "notes": notes, "data_kind": "synthetic_actual"})
    noise = A("lab_noise_rel")
    fod = P("fibre_oil_pct_dry_basis") / P("oil_loss_fibre_pct_ffb")
    for h in range(H):
        if m["processed_t"][h] <= 0:
            continue
        pb = int(block_of_hour[h]) or None
        t_s = h * 60 + 30
        if h % 4 == 1:
            for p in range(m["press_feed"].shape[0]):
                if m["press_feed"][p, h] > 0:
                    add(t_s, "press_fibre", "oil_in_fibre_dry", m["press_loss"][p, h] * fod * rng.lognormal(0, noise), "% dry", pb,
                        method="Soxhlet extraction (simulated)", notes=f"PRS-0{p + 1}")
            add(t_s, "efb", "oil_loss", m["loss_efb"][h] * rng.lognormal(0, noise), "% FFB", pb, method="Soxhlet extraction (simulated)")
            add(t_s, "sludge", "oil_loss", m["loss_sludge"][h] * rng.lognormal(0, noise), "% FFB", pb, method="Soxhlet extraction (simulated)")
        if h % 8 == 3:
            add(t_s, "nut", "oil_loss", m["loss_nut"][h] * rng.lognormal(0, noise), "% FFB", pb, method="Soxhlet extraction (simulated)")
            add(t_s, "condensate", "oil_loss", m["loss_cond"][h] * rng.lognormal(0, noise), "% FFB", pb, method="Soxhlet extraction (simulated)")
    for lt in lots:
        d = lt["_day"]
        hs = [h for h in range(d * 24, d * 24 + 24) if m["processed_t"][h] > 0]
        t_s = (hs[-1] + 1) * 60 - 5
        for param, val, unit in (("ffa", lt["ffa_pct"], "%"), ("moisture", lt["moisture_pct"], "%"), ("dirt", lt["dirt_pct"], "%"), ("dobi", lt["dobi"], "-")):
            add(min(t_s, tb.minutes - 1), "cpo_tank", param, val, unit, lot=lt["id"], method="AOCS/ISO lab method (simulated)", notes=lt["tank_code"])
        if lt["dispatched_at"] is not None:
            age_d = (lt["dispatched_at"] - lt["fill_start_ts"]).total_seconds() / 86400
            disp_min = (lt["dispatched_at"] - tb.start_utc.replace(tzinfo=None)).total_seconds() / 60 - 10
            add(disp_min, "cpo_tank", "ffa", lot_ffa[lt["id"]] + P("cpo_storage_ffa_drift_pp_per_day") * age_d, "%", lot=lt["id"],
                method="AOCS/ISO lab method (simulated)", notes="pre-dispatch sample")
    for d in range(D):
        if m["processed_t"][d * 24:(d + 1) * 24].sum() <= 0:
            continue
        add(d * 1440 + 9 * 60, "kernel", "moisture", P("kernel_moisture_pct") + rng.normal(0, 0.3), "%", method="Oven drying (simulated)")
        add(d * 1440 + 9 * 60 + 20, "effluent", "cod", P("pome_cod_mg_per_l") * rng.lognormal(0, 0.08), "mg/L", method="COD dichromate (simulated)")
    return {"process_hourly": ph, "production_shifts": shifts, "production_batches": pbatches, "byproduct_outputs": byp,
            "batch_inputs": binputs, "cpo_output_lots": lot_rows, "lot_compositions": comps, "quality_measurements": qm,
            "_tank_level_t": tank_level, "_block_of_hour": block_of_hour, "_lots": lots}


def build_energy_rows(core, ids, stage_ids, eq_state, eb) -> list[dict]:
    tb, m = core.tb, core.mill
    rows = []
    stage_kw: dict[str, np.ndarray] = defaultdict(lambda: np.zeros(tb.hours))
    for e in core.equip:
        stage_kw[e.stage] += eq_state[e.code]["kw"]
    for h in range(tb.hours):
        rows.append({
            "id": len(rows) + 1, "facility_id": ids["facility"], "process_stage_id": None, "ts": tb.ts(h * 60),
            "electricity_kwh": round(float(eb["elec"][h]), 2), "grid_import_kwh": round(float(eb["grid"][h]), 2),
            "self_generated_kwh": round(float(eb["self_gen"][h] + eb["dg"][h]), 2), "steam_t": round(float(m["boiler_steam_t"][h]), 3),
            "boiler_fibre_t": round(float(eb["fibre"][h]), 3), "boiler_shell_t": round(float(eb["shell"][h]), 3),
            "diesel_l": round(float(eb["diesel"][h]), 2), "water_m3": round(float(eb["water"][h]), 2),
            "ffb_processed_t": round(float(m["processed_t"][h]), 3), "idle_kwh": round(float(eb["idle"][h]), 2),
            "cost_thb": round(float(eb["cost"][h]), 2), "data_kind": "synthetic_actual",
        })
        proc_steam = max(float(m["boiler_steam_t"][h]) - A("steam_banking_t_per_h") * (1 - m["running_min"][h] / 60), 0.0)
        extra = core.mods.steam_extra[h]
        base_proc = proc_steam / (1 + extra)
        for st_code, sid in stage_ids.items():
            kwh = float(stage_kw[st_code][h]) if st_code in stage_kw else 0.0
            share = STAGE_STEAM_SHARE.get(st_code)
            steam = None
            if share is not None:
                steam = base_proc * share + (proc_steam - base_proc if st_code == "STERILIZATION" else 0.0)
            if kwh <= 0 and steam is None:
                continue
            rows.append({
                "id": len(rows) + 1, "facility_id": ids["facility"], "process_stage_id": sid, "ts": tb.ts(h * 60),
                "electricity_kwh": round(kwh, 2), "grid_import_kwh": None, "self_generated_kwh": None,
                "steam_t": round(steam, 3) if steam is not None else None, "boiler_fibre_t": None, "boiler_shell_t": None,
                "diesel_l": None, "water_m3": None, "ffb_processed_t": round(float(m["processed_t"][h]), 3),
                "idle_kwh": round(min(kwh, float(eq_state_idle(core, eq_state, st_code, h))), 2), "cost_thb": None, "data_kind": "synthetic_actual",
            })
    return rows


def eq_state_idle(core, eq_state, stage: str, h: int) -> float:
    return sum(float(eq_state[e.code]["kw_idle"][h]) for e in core.equip if e.stage == stage)
