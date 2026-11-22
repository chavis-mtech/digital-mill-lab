"""Queue simulation AI-D03: FIFO vs constraint-aware slot scheduling over HISTORICAL arrivals (DML-063). Owner: backend-a.

Discrete-event simulation (heap of events, shared resources with FIFO/priority queues), seedable, what_if output.

Arrival set: the trucks that actually arrived on `business_date` (truck_trips, arrival <= as_of), with their measured
payload (ticket net) and harvest-to-mill time (ffb_deliveries). Same trucks for every policy.
Flow per truck: gate check -> weighbridge (weigh-in) -> grading -> unloading ramp -> weighbridge (weigh-out) -> exit.
Service times (minutes) - DOMAIN_PARAMETERS / data-engine assumptions:
  gate check   lognormal, mean gate_check_min_mean (5 min), sigma 0.5           (Engineering Assumption)
  weigh event  weighbridge_service_min_per_event (2 min) x m                     (bridges shared by weigh-in and weigh-out;
                                                                                  weigh-out has priority to clear the site)
  grading      4 min x m on grader_count (2) graders                           (Engineering Assumption)
  unloading    (unload_positioning_min 3 + payload_t / unloading_rate 1 t/min) x m on `unloading_ramps`
  exit         1 min
  m = lognormal multiplier, mean 1, CV 0.15. Random draws are made ONCE per truck from numpy default_rng(seed) and
  reused for every policy (common random numbers), so differences come from the policy, not from noise.
Outages: optionally (default on) unit outages are inferred from recorded queue events (see infer_outages) and replayed.
Policies:
  fifo        trucks enter the yard when they arrive; served first-come-first-served.
  slot_based  appointment slots of `slot_minutes`; capacity per slot = min(trucks_per_slot, floor(0.85 x binding
              capacity)), binding capacity = min(unloading_ramps x slot / mean unloading time, weighbridges x slot /
              (2 x weigh time)) - the 0.85 cap keeps utilisation below the point where queues grow non-linearly
              (KPI_DEFINITIONS 4.9). Trucks are allocated in arrival order to the earliest slot with free capacity
              that starts no earlier than their arrival slot; within the same arrival slot, loads with the longest
              harvest-to-mill time are allocated first (FFA risk). A truck with a later slot arrives at the slot start:
              that DEFERRAL is waiting moved off-site (at the estate / en route), reported separately - it does not vanish.
Outputs per policy: in-yard wait (weigh-in start - yard arrival, incl. gate), P90, max, max trucks waiting,
turnaround (exit - yard arrival), bridge and unloading utilisation, mean deferral and total delay (deferral + wait).
The observed (historical) wait/turnaround of the same trucks is returned so the FIFO model's fit can be judged.
"""

from __future__ import annotations

import heapq
import math
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models.logistics import FfbDelivery, QueueEvent, TruckTrip, WeighbridgeTicket
from app.models.production import ProcessHourly
from app.services.demo_context import DemoContext, provenance
from app.services.kpi_common import assumption_from_param, iso_utc, local_midnight, param, rnd

GRADING_MIN = 4.0
EXIT_MIN = 1.0
CV = 0.15
UTIL_CAP = 0.85
OUTAGE_GAP_MIN = 45.0
OUTAGE_MIN_WAITING = 2
UNLOAD_POS_MIN = 3.0  # ASSUMED.unload_positioning_min (data engine)
GRADERS = 2  # ASSUMED.grader_count


class _Res:
    def __init__(self, cap: int):
        self.cap, self.busy, self.q, self.busy_min = cap, 0, [], 0.0


def _lognormal(rng: np.random.Generator, mean: float, sigma: float, n: int) -> np.ndarray:
    mu = math.log(mean) - sigma**2 / 2
    return rng.lognormal(mu, sigma, n)


def simulate(
    arrivals: np.ndarray, payload: np.ndarray, draws: dict[str, np.ndarray], weighbridges: int, ramps: int,
    outages: dict[str, list[tuple[float, float]]] | None = None, ramp_space: dict[str, Any] | None = None,
) -> dict[str, Any]:  # fmt: skip
    """Run one replication. arrivals = yard arrival minutes. outages = {"bridge"|"ramp": [(start_min, end_min), ...]},
    each interval removes one unit of that resource for new service starts (no pre-emption of running service)."""
    outages = outages or {}
    n = len(arrivals)
    weigh = param("weighbridge_service_min_per_event")
    rate = param("unloading_rate_t_per_min_per_bay")
    res = {"bridge": _Res(weighbridges), "grader": _Res(GRADERS), "ramp": _Res(ramps)}
    weigh_in_start = np.full(n, np.nan)
    exit_t = np.full(n, np.nan)
    ev: list[tuple[float, int, int, str]] = []
    seq = 0

    def push(t: float, i: int, step: str) -> None:
        nonlocal seq
        seq += 1
        heapq.heappush(ev, (t, seq, i, step))

    dur = {
        "weigh_in": lambda i: weigh * draws["m_w1"][i],
        "grade": lambda i: GRADING_MIN * draws["m_g"][i],
        "unload": lambda i: (UNLOAD_POS_MIN + payload[i] / rate) * draws["m_u"][i],
        "weigh_out": lambda i: weigh * draws["m_w2"][i],
    }
    resource = {"weigh_in": "bridge", "grade": "grader", "unload": "ramp", "weigh_out": "bridge"}
    prio = {"weigh_in": 1, "grade": 0, "unload": 0, "weigh_out": 0}
    nxt = {"weigh_in": "grade", "grade": "unload", "unload": "weigh_out", "weigh_out": None}

    def start(t: float, i: int, step: str) -> None:
        r = res[resource[step]]
        r.busy += 1
        d = dur[step](i)
        r.busy_min += d
        if step == "weigh_in":
            weigh_in_start[i] = t
        if step == "unload":
            unloaded[0] += payload[i]
        push(t + d, i, "done:" + step)

    def cap_at(name: str, t: float) -> int:
        down = sum(1 for a, b in outages.get(name, []) if a <= t < b)
        return max(0, res[name].cap - down)

    unloaded = [0.0]
    recheck_pending = [False]

    def space_ok(t: float, i: int) -> bool:
        if ramp_space is None:
            return True
        processed = float(np.interp(t, ramp_space["t"], ramp_space["cum"]))
        stock = max(0.0, ramp_space["stock0"] + unloaded[0] - processed)
        return stock + payload[i] <= ramp_space["cap"]

    def can_start(t: float, i: int, step: str) -> bool:
        if res[resource[step]].busy >= cap_at(resource[step], t):
            return False
        if step == "unload" and not space_ok(t, i):
            if not recheck_pending[0] and t + 5.0 <= float(ramp_space["t"][-1]):  # stop rechecking past the replay horizon
                recheck_pending[0] = True
                push(t + 5.0, -1, "cap:ramp")
            return False
        return True

    def request(t: float, i: int, step: str) -> None:
        r = res[resource[step]]
        if not r.q and can_start(t, i, step):
            start(t, i, step)
        else:
            heapq.heappush(r.q, (prio[step], t, i, step))

    for i in range(n):
        push(float(arrivals[i]) + float(draws["gate"][i]), i, "req:weigh_in")
    for name, ivs in outages.items():
        for _a, b in ivs:
            push(float(b), -1, "cap:" + name)
    while ev:
        t, _, i, kind = heapq.heappop(ev)
        if kind.startswith("cap:"):
            name = kind[4:]
            if name == "ramp":
                recheck_pending[0] = False
            r = res[name]
            while r.q and can_start(t, r.q[0][2], r.q[0][3]):
                _, _, j, s2 = heapq.heappop(r.q)
                start(t, j, s2)
            continue
        if kind.startswith("req:"):
            request(t, i, kind[4:])
            continue
        step = kind[5:]
        r = res[resource[step]]
        r.busy -= 1
        while r.q and can_start(t, r.q[0][2], r.q[0][3]):
            _, _, j, s2 = heapq.heappop(r.q)
            start(t, j, s2)
        nx = nxt[step]
        if nx:
            request(t, i, nx)
        else:
            exit_t[i] = t + EXIT_MIN
    return {"weigh_in_start": weigh_in_start, "exit": exit_t, "bridge_busy": res["bridge"].busy_min, "ramp_busy": res["ramp"].busy_min}


def infer_outages(db: Session, day_start, day_end) -> tuple[dict[str, list[tuple[float, float]]], list[dict[str, Any]]]:
    """Infer unit outages from the RECORDED queue events (not from ground-truth labels): a weighbridge / ramp unit with no
    event for > OUTAGE_GAP_MIN minutes while at least OUTAGE_MIN_WAITING trucks were waiting for that resource type
    (from truck timestamps) is treated as unavailable for that gap. Measured inference - may misread a quiet unit."""
    ev = pd.DataFrame(db.execute(
        select(QueueEvent.ts, QueueEvent.location, QueueEvent.event_type)
        .where(QueueEvent.ts >= day_start - timedelta(hours=2), QueueEvent.ts <= day_end, QueueEvent.location.like("bridge-%") | QueueEvent.location.like("ramp-%"))
    ).all(), columns=["ts", "loc", "type"])  # fmt: skip
    trips = pd.DataFrame(db.execute(
        select(TruckTrip.arrival_ts, TruckTrip.weigh_in_ts, TruckTrip.grading_ts, TruckTrip.unload_start_ts)
        .where(TruckTrip.arrival_ts >= day_start - timedelta(hours=6), TruckTrip.arrival_ts <= day_end)
    ).all(), columns=["arr", "win", "grd", "uls"])  # fmt: skip
    out: dict[str, list[tuple[float, float]]] = {"bridge": [], "ramp": []}
    info: list[dict[str, Any]] = []
    if ev.empty or trips.empty:
        return out, info
    ev["ts"] = pd.to_datetime(ev["ts"], utc=True)
    for c in trips.columns:
        trips[c] = pd.to_datetime(trips[c], utc=True)
    t0 = pd.Timestamp(day_start)
    sentinel_lo, sentinel_hi = pd.Timestamp(day_start), pd.Timestamp(day_end)
    for loc, g in ev.groupby("loc"):
        kind = "bridge" if loc.startswith("bridge") else "ramp"
        ts = sorted([sentinel_lo] + [x for x in g["ts"].tolist() if x >= sentinel_lo] + [sentinel_hi])
        for a, b in zip(ts, ts[1:], strict=False):
            if (b - a).total_seconds() / 60 <= OUTAGE_GAP_MIN:
                continue
            mids = list(pd.date_range(a, b, freq="10min")[1:-1])
            if kind == "bridge":
                waiting = [int(((trips["arr"] <= m) & (trips["win"] > m)).sum()) for m in mids]
            else:
                waiting = [int(((trips["grd"] <= m) & (trips["uls"] > m)).sum()) for m in mids]
            run: list[int] = []
            for k, wv in enumerate(waiting + [0]):
                if k < len(waiting) and wv >= OUTAGE_MIN_WAITING:
                    run.append(k)
                    continue
                if run and (mids[run[-1]] - mids[run[0]]).total_seconds() / 60 >= OUTAGE_GAP_MIN:
                    rs, re_ = mids[run[0]], mids[run[-1]]
                    out[kind].append(((rs - t0).total_seconds() / 60, (re_ - t0).total_seconds() / 60))
                    info.append({"unit": loc, "start": rs.to_pydatetime(), "end": re_.to_pydatetime(), "min_waiting": min(waiting[i] for i in run)})
                run = []
    return out, info
    ev["ts"] = pd.to_datetime(ev["ts"], utc=True)
    for c in trips.columns:
        trips[c] = pd.to_datetime(trips[c], utc=True)
    t0 = pd.Timestamp(day_start)
    for loc, g in ev.groupby("loc"):
        kind = "bridge" if loc.startswith("bridge") else "ramp"
        ts = sorted(g["ts"].tolist())
        for a, b in zip(ts, ts[1:], strict=False):
            if (b - a).total_seconds() / 60 <= OUTAGE_GAP_MIN:
                continue
            mids = pd.date_range(a, b, freq="10min")[1:-1]
            if len(mids) == 0:
                continue
            if kind == "bridge":
                waiting = [int(((trips["arr"] <= m) & (trips["win"] > m)).sum()) for m in mids]
            else:
                waiting = [int(((trips["grd"] <= m) & (trips["uls"] > m)).sum()) for m in mids]
            if min(waiting) >= OUTAGE_MIN_WAITING:
                s_min, e_min = (a - t0).total_seconds() / 60, (b - t0).total_seconds() / 60
                out[kind].append((s_min, e_min))
                info.append({"unit": loc, "start": a.to_pydatetime(), "end": b.to_pydatetime(), "min_waiting": min(waiting)})
    return out, info


def _ramp_space(db: Session, ctx: DemoContext, day_start, cap: float) -> dict[str, Any] | None:
    """Loading-ramp space constraint replayed from the MEASURED mill: stock at day start (process_hourly.ffb_waiting_t
    of the hour ending at day start) and cumulative FFB processed per hour (complete hours <= as_of; after as_of the
    mean rate of the last 3 known hours is extrapolated - no data beyond as_of is read)."""
    rows = db.execute(
        select(ProcessHourly.ts, ProcessHourly.ffb_processed_t, ProcessHourly.ffb_waiting_t)
        .where(ProcessHourly.ts >= day_start - timedelta(hours=1), ProcessHourly.ts <= min(day_start + timedelta(hours=23), ctx.as_of - timedelta(hours=1)))
        .order_by(ProcessHourly.ts)
    ).all()  # fmt: skip
    if len(rows) < 2:
        return None
    t0 = pd.Timestamp(day_start)
    stock0 = float(rows[0][2] or 0.0)
    ts, cum, acc = [0.0], [0.0], 0.0
    for ts_h, proc, _ in rows[1:]:
        acc += float(proc or 0.0)
        ts.append((pd.Timestamp(iso_utc(ts_h)) - t0).total_seconds() / 60 + 60)  # end of the hour
        cum.append(acc)
    rate = float(np.mean([float(r[1] or 0.0) for r in rows[-3:]])) / 60.0
    ts.append(ts[-1] + 24 * 60)
    cum.append(acc + rate * 24 * 60)
    return {"t": np.array(ts), "cum": np.array(cum), "stock0": stock0, "cap": cap}


def _queue_series(yard: np.ndarray, win: np.ndarray, day_start, step: int = 15) -> list[dict[str, Any]]:
    if len(yard) == 0:
        return []
    t0, t1 = math.floor(yard.min() / step) * step, math.ceil(np.nanmax(win) / step) * step
    return [{"t": day_start + timedelta(minutes=float(t)), "v": float(((yard <= t) & (win > t)).sum())} for t in np.arange(t0, t1 + step, step)]


def run(db: Session, ctx: DemoContext, body: Any) -> dict[str, Any]:
    d: date = body.business_date or ctx.business_date
    if d > ctx.business_date:
        raise ApiError(422, "future_date", "business_date is after the demo clock (as_of)")
    day_start = local_midnight(ctx, d)
    if day_start + timedelta(days=1) <= ctx.window_start:
        raise ApiError(422, "out_of_window", "business_date is before the dataset window")
    rows = db.execute(
        select(TruckTrip.arrival_ts, TruckTrip.weigh_in_ts, TruckTrip.exit_ts, WeighbridgeTicket.net_kg, FfbDelivery.harvest_to_mill_h)
        .outerjoin(WeighbridgeTicket, WeighbridgeTicket.truck_trip_id == TruckTrip.id)
        .outerjoin(FfbDelivery, FfbDelivery.truck_trip_id == TruckTrip.id)
        .where(TruckTrip.arrival_ts >= day_start, TruckTrip.arrival_ts < day_start + timedelta(days=1), TruckTrip.arrival_ts <= ctx.as_of)
        .order_by(TruckTrip.arrival_ts)
    ).all()  # fmt: skip
    if len(rows) < 2:
        raise ApiError(422, "no_arrivals", "Fewer than 2 truck arrivals on that day up to as_of", {"business_date": d.isoformat()})
    df = pd.DataFrame(rows, columns=["arr", "win", "exit", "net", "h2m"])
    for c in ("arr", "win", "exit"):
        df[c] = pd.to_datetime(df[c], utc=True)
    arr = ((df["arr"] - pd.Timestamp(day_start)).dt.total_seconds() / 60).to_numpy()
    payload = (df["net"].fillna(df["net"].median()).to_numpy(dtype=float)) / 1000.0
    h2m = df["h2m"].fillna(0).to_numpy(dtype=float)
    n = len(arr)
    rng = np.random.default_rng(body.seed)
    draws = {"gate": _lognormal(rng, 5.0, 0.5, n), **{k: _lognormal(rng, 1.0, CV, n) for k in ("m_w1", "m_g", "m_u", "m_w2")}}

    asof_t = pd.Timestamp(ctx.as_of)
    done = df[(df["win"] <= asof_t)]
    observed = {
        "avg_wait_min": rnd(float(((done["win"] - done["arr"]).dt.total_seconds() / 60).mean()), 1) if len(done) else None,
        "avg_turnaround_min": rnd(float(((df.loc[df["exit"] <= asof_t, "exit"] - df.loc[df["exit"] <= asof_t, "arr"]).dt.total_seconds() / 60).mean()), 1)
        if (df["exit"] <= asof_t).any() else None,
        "trucks": n,
    }  # fmt: skip

    weigh = param("weighbridge_service_min_per_event")
    mean_unload = UNLOAD_POS_MIN + float(payload.mean()) / param("unloading_rate_t_per_min_per_bay")
    binding = min(body.unloading_ramps * body.slot_minutes / mean_unload, body.weighbridges * body.slot_minutes / (2 * weigh))
    slot_cap = max(1, min(body.trucks_per_slot, int(math.floor(UTIL_CAP * binding))))

    outages, outage_info = ({}, [])
    if getattr(body, "replay_observed_outages", True):
        outages, outage_info = infer_outages(db, day_start, min(day_start + timedelta(days=1), ctx.as_of))

    ramp_space = None
    if getattr(body, "ramp_capacity_t", None):
        ramp_space = _ramp_space(db, ctx, day_start, body.ramp_capacity_t)

    results = []
    for pol in body.policies:
        pol = getattr(pol, "value", pol)
        if pol == "fifo":
            yard = arr.copy()
        else:
            yard = np.empty(n)
            used: dict[int, int] = {}
            order = sorted(range(n), key=lambda i: (math.floor(arr[i] / body.slot_minutes), -h2m[i], arr[i]))
            for i in order:
                k = math.floor(arr[i] / body.slot_minutes)
                while used.get(k, 0) >= slot_cap:
                    k += 1
                used[k] = used.get(k, 0) + 1
                yard[i] = max(arr[i], k * body.slot_minutes)
        sim = simulate(yard, payload, draws, body.weighbridges, body.unloading_ramps, outages, ramp_space)
        wait = sim["weigh_in_start"] - yard
        tat = sim["exit"] - yard
        defer = yard - arr
        horizon = max(float(np.nanmax(sim["exit"]) - yard.min()), 1.0)
        series = _queue_series(yard, sim["weigh_in_start"], day_start)
        results.append({
            "policy": pol,
            "avg_wait_min": round(float(np.nanmean(wait)), 2), "p90_wait_min": round(float(np.nanpercentile(wait, 90)), 2),
            "max_wait_min": round(float(np.nanmax(wait)), 2),
            "max_queue_length": int(max((p["v"] for p in series), default=0)),
            "avg_turnaround_min": round(float(np.nanmean(tat)), 2),
            "bridge_utilisation_pct": round(100 * sim["bridge_busy"] / (body.weighbridges * horizon), 2),
            "unloading_utilisation_pct": round(100 * sim["ramp_busy"] / (body.unloading_ramps * horizon), 2),
            "avg_deferral_min": round(float(defer.mean()), 2), "max_deferral_min": round(float(defer.max()), 2),
            "avg_total_delay_min": round(float(np.nanmean(wait + defer)), 2),
            "queue_length_series": {"key": f"queue_{pol}", "label": f"Trucks waiting in the yard ({pol}, simulated)", "unit": "trucks",
                                    "points": series, "provenance": provenance("what_if", "queue simulation", ctx)},
        })  # fmt: skip
    return {
        "trucks_simulated": n,
        "business_date": d,
        "slot_capacity_used": slot_cap if any(getattr(p, "value", p) == "slot_based" for p in body.policies) else None,
        "observed": observed,
        "inferred_outages": outage_info,
        "results": results,
        "assumptions": [
            assumption_from_param("weighbridge_service_min_per_event", "Weighbridge time per weigh event"),
            assumption_from_param("unloading_rate_t_per_min_per_bay", "Unloading rate per ramp"),
            {"key": "gate_check_min_mean", "label": "Gate check (lognormal mean, sigma 0.5)", "value": 5.0, "unit": "min", "tag": "engineering_assumption",
             "source": "app/seed/assumptions.py ASSUMED.gate_check_min_mean", "editable": False},
            {"key": "grading_min", "label": "Grading time on 2 graders", "value": GRADING_MIN, "unit": "min", "tag": "engineering_assumption",
             "source": "docs/DATA_GENERATION.md section 4 (queue)", "editable": False},
            {"key": "unload_positioning_min", "label": "Positioning per unloading", "value": 3.0, "unit": "min", "tag": "engineering_assumption",
             "source": "app/seed/assumptions.py ASSUMED.unload_positioning_min", "editable": False},
            {"key": "service_cv", "label": "Service-time variability (lognormal CV)", "value": CV, "unit": None, "tag": "engineering_assumption",
             "source": "backend-a simulation choice", "editable": False},
            {"key": "slot_utilisation_cap", "label": "Slot capacity cap as share of binding capacity", "value": UTIL_CAP, "unit": None,
             "tag": "industry_practice", "source": "docs/business/KPI_DEFINITIONS.md 4.9 (queues grow non-linearly above ~0.85)", "editable": False},
            {"key": "seed", "label": "Random seed (common random numbers across policies)", "value": body.seed, "unit": None,
             "tag": "synthetic_demonstration_data", "source": "request", "editable": True},
        ],  # fmt: skip
        "limitations": [
            "Single replication per seed; change the seed to see the spread - differences of a few minutes are within noise.",
            "Slot scheduling moves waiting off-site (deferral) - it does not remove it. Total delay = deferral + yard wait; long deferral can raise FFB age and FFA.",
            "Assumes every truck can and will arrive at its assigned slot (no no-shows, no driver behaviour, no road time model).",
            "Equipment outages are INFERRED from the recorded queue events (a unit idle > 45 min while >= 2 trucks waited for it) and replayed for both "
            "policies; manual-ticketing slowdowns and other effects are not modelled, so the FIFO replay may still differ from what was observed.",
            "Arrivals after as_of on the same day are unknown and not simulated.",
            "Synthetic data and engineering assumptions; not validated on a real mill. Long waits are a flow problem, never an accusation.",
        ],
        "provenance": provenance("what_if", "queue simulation over truck_trips arrivals (discrete-event)", ctx),
    }
