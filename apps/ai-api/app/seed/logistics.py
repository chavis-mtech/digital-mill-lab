"""Logistics: daily intake -> supplier deliveries -> trucks -> gate/weighbridge/grading/unloading queue simulation.

Queue model (Engineering Assumption, REL-14): multi-server stations with interval booking
(gate check -> weigh-in [weighbridge pool, shared with weigh-out] -> grading [2 graders] -> unloading [bays]
-> weigh-out -> exit). Congestion emerges from arrivals vs service capacity; nothing sets a wait time directly.
"""

from __future__ import annotations

import math
from bisect import insort
from dataclasses import dataclass, field

import numpy as np

from app.seed.assumptions import A, P, profile
from app.seed.registry import TRUCK_TYPES, SupplierSpec


@dataclass
class Truck:
    idx: int
    supplier: int  # index into suppliers
    plantation_id: int
    plate: str
    ttype: str
    payload_kg: int
    tare_kg: int
    arrival: float
    unripe: float
    overripe: float
    empty_bunch: float
    long_stalk: float
    dirt: float
    h2m_h: float
    reject: bool = False
    outlier: bool = False
    queue_start: float | None = None
    weigh_in: float | None = None
    bridge_in: int = 0
    grading: float | None = None
    graded_end: float | None = None
    unload_start: float | None = None
    unload_end: float | None = None
    bay: int = 0
    weigh_out: float | None = None
    bridge_out: int = 0
    exit: float | None = None
    grade: str = "B"
    deduction_pct: float = 0.0
    extra: dict = field(default_factory=dict)


class Pool:
    """k identical servers with interval booking (earliest feasible gap on any server)."""

    def __init__(self, n: int) -> None:
        self.busy: list[list[tuple[float, float]]] = [[] for _ in range(n)]

    def block(self, i: int, s: float, e: float) -> None:
        insort(self.busy[i], (s, e))

    def prune(self, t: float) -> None:
        for iv in self.busy:
            k = 0
            while k < len(iv) and iv[k][1] < t:
                k += 1
            if k:
                del iv[:k]

    @staticmethod
    def _earliest(iv: list[tuple[float, float]], t: float, dur: float) -> float:
        start = t
        for s, e in iv:
            if e <= start:
                continue
            if s >= start + dur:
                break
            start = max(start, e)
        return start

    def book(self, t: float, dur: float) -> tuple[float, int]:
        best = None
        for i, iv in enumerate(self.busy):
            st = self._earliest(iv, t, dur)
            if best is None or st < best[0]:
                best = (st, i)
        st, i = best
        insort(self.busy[i], (st, st + dur))
        return st, i


def grade_of(unripe: float, overripe: float, long_stalk: float, empty: float) -> str:
    if unripe >= 22:
        return "reject"
    if unripe < 3 and overripe < 10 and long_stalk < 2.5 and empty < 2.5:
        return "A"
    if unripe < 7 and overripe < 15:
        return "B"
    return "C"


def generate_trucks(tb, rngs, suppliers: list[SupplierSpec], cal, mods) -> tuple[list[Truck], np.ndarray, list[dict]]:
    """Returns (trucks sorted by arrival, daily intake target t, weight-outlier labels)."""
    rng = rngs.get("logistics.trucks")
    base = P("mill_capacity_t_ffb_per_h") * P("operating_hours_per_day") * P("capacity_utilisation_normal")
    hourly_w = np.array(profile("ffb_arrival_hourly_weights"), dtype=float)
    heavy = cal.heavy_rain
    rainy = cal.rainy
    # slow per-supplier quality random walk (supplier quality variation over time)
    S = len(suppliers)
    rw = np.zeros((S, tb.days))
    steps = rng.normal(0, 0.35, (S, tb.days))
    for d in range(1, tb.days):
        rw[:, d] = 0.85 * rw[:, d - 1] + steps[:, d]
    targets = np.zeros(tb.days)
    trucks: list[Truck] = []
    for d in range(tb.days):
        rain_f = 1.0
        if heavy[d]:
            rain_f *= 0.85
        elif rainy[d]:
            rain_f *= 0.95
        if d > 0 and heavy[d - 1]:
            rain_f *= 1.08
        total = base * cal.season[d] * cal.weekday[d] * cal.noise[d] * mods.intake_mult[d] * mods.quota[d] * rain_f
        targets[d] = total
        w = hourly_w ** mods.sharpen[d]
        if rainy[d]:
            w = w * np.where(np.arange(24) < 12, 0.6, 1.25)
        w = w / w.sum()
        for si, sp in enumerate(suppliers):
            if rng.random() > sp.reliability and sp.stype not in ("own_estate",):
                continue
            vol = total * sp.share / sp.reliability * float(rng.lognormal(-0.03, 0.25))
            q_unripe = sp.unripe_mean + rw[si, d] + mods.unripe_shift[si, d] + (0.8 if rainy[d] else 0.0) + float(rng.normal(0, 1.2))
            q_over = sp.overripe_mean + float(rng.normal(0, 1.5)) + (1.0 if (d > 0 and heavy[d - 1]) else 0.0)
            q_h2m = sp.h2m_mean * float(rng.lognormal(0, 0.2)) + mods.h2m_shift[si, d] + (8.0 if heavy[d] else 4.0 if rainy[d] else 0.0)
            types = list(sp.truck_mix.keys())
            probs = np.array([sp.truck_mix[t] for t in types])
            loads: list[tuple[str, int]] = []
            acc = 0.0
            while acc < vol:
                tt = str(rng.choice(types, p=probs / probs.sum()))
                key = TRUCK_TYPES[tt][0]
                nom = P(key)
                lo, hi = _range(key)
                pay = float(np.clip(rng.normal(nom, (hi - lo) / 5), lo, hi))
                if vol - acc < lo * 0.6 and loads:
                    break
                loads.append((tt, int(round(pay * 1000, -1))))
                acc += pay
            # convoys: trucks of one supplier-day arrive in clusters of up to 3 (dispersion index > 1)
            k = 0
            while k < len(loads):
                csize = int(min(len(loads) - k, rng.integers(1, 4)))
                hh = int(rng.choice(24, p=w))
                tc = d * 1440 + hh * 60 + float(rng.uniform(0, 60))
                for j in range(csize):
                    tt, pay = loads[k + j]
                    arr = tc + float(rng.uniform(0, 10))
                    unr = max(0.0, q_unripe + float(rng.normal(0, 1.0)))
                    ovr = float(np.clip(q_over + rng.normal(0, 1.2), 0.5, 30))
                    emp = float(np.clip(rng.normal(1.5, 0.6), 0, 6))
                    ls = float(np.clip(sp.long_stalk_mean + rng.normal(0, 0.8) + (1.0 if rainy[d] else 0), 0, 15))
                    dirt = float(np.clip(P("ffb_dirt_trash_share_pct") + rng.normal(0, 0.25) + (0.5 if rainy[d] else 0), 0.2, 4))
                    tare_nom = TRUCK_TYPES[tt][1]
                    trucks.append(Truck(
                        idx=0, supplier=si, plantation_id=int(rng.choice(sp.plantation_ids)), plate=str(rng.choice(sp.plates)),
                        ttype=tt, payload_kg=pay, tare_kg=int(round(tare_nom * float(rng.normal(1, 0.03)), -1)), arrival=arr,
                        unripe=unr, overripe=ovr, empty_bunch=emp, long_stalk=ls, dirt=dirt,
                        h2m_h=max(2.0, q_h2m + float(rng.normal(0, 1.5))),
                    ))
                k += csize
    trucks = [t for t in trucks if t.arrival < tb.minutes]
    trucks.sort(key=lambda t: (t.arrival, t.supplier))
    for i, t in enumerate(trucks):
        t.idx = i
    # injected weight outliers (logistics anomaly ground truth; plausible but beyond the class payload)
    labels = []
    rng_o = rngs.get("logistics.outliers")
    protected_minutes = [(d * 1440, (d + 1) * 1440) for d in mods.forced_dry]
    cands = [t for t in trucks if not any(a <= t.arrival < b for a, b in protected_minutes) and t.arrival < tb.minutes - 1440]
    for t in rng_o.choice(cands, size=min(3, len(cands)), replace=False) if cands else []:
        key = TRUCK_TYPES[t.ttype][0]
        hi = _range(key)[1]
        t.payload_kg = int(round(hi * 1000 * float(rng_o.uniform(1.08, 1.13)), -1))
        t.outlier = True
        labels.append({"truck_idx": t.idx, "payload_kg": t.payload_kg, "class_max_kg": int(hi * 1000)})
    return trucks, targets, labels


def _range(key: str) -> tuple[float, float]:
    from app.seed.assumptions import P_range

    return P_range(key)


def simulate_queue(tb, rngs, trucks: list[Truck], mods) -> None:
    rng = rngs.get("logistics.queue")
    bridges = Pool(int(P("weighbridge_count")))
    for b, s, e in mods.wb_outages:
        bridges.block(b, s, e)
    graders = Pool(int(A("grader_count")))
    bays = Pool(int(P("unloading_bays")))
    for b, s, e in mods.bay_outages:
        bays.block(b, s, e)
    svc = P("weighbridge_service_min_per_event")
    grade_min = P("grading_inspection_min")
    rate = P("unloading_rate_t_per_min_per_bay")
    gate_mean = A("gate_check_min_mean")
    sig = 0.45
    for t in trucks:
        for pool in (bridges, graders, bays):
            pool.prune(t.arrival)
        d = int(t.arrival // 1440)
        t.queue_start = t.arrival + float(rng.lognormal(math.log(gate_mean) - sig**2 / 2, sig))
        hq = min(int(t.queue_start // 60), tb.hours - 1)
        st, b = bridges.book(t.queue_start, svc * mods.wb_svc_mult[hq] * float(rng.lognormal(0, 0.2)))
        t.weigh_in, t.bridge_in = st, b
        g_dur = grade_min * mods.grading_mult[min(d, tb.days - 1)] * float(rng.lognormal(0, 0.25))
        gs, _ = graders.book(t.weigh_in + svc + 0.5, g_dur)
        t.grading, t.graded_end = gs, gs + g_dur
        t.grade = grade_of(t.unripe, t.overripe, t.long_stalk, t.empty_bunch)
        if t.grade != "reject" and rng.random() < 0.002:
            t.grade = "reject"
        t.reject = t.grade == "reject"
        if t.reject:
            t.deduction_pct = 100.0
            wo, b2 = bridges.book(t.graded_end + 2, svc)
        else:
            t.deduction_pct = float(np.clip(0.4 + 0.18 * max(0, t.unripe - 3) + 0.25 * t.long_stalk + 0.3 * max(0, t.dirt - 1)
                                            + float(rng.normal(0, 0.15)), 0, 10))
            u_dur = A("unload_positioning_min") + t.payload_kg / 1000 / rate * float(rng.uniform(0.85, 1.15))
            us, bay = bays.book(t.graded_end + 1.0, u_dur)
            t.unload_start, t.unload_end, t.bay = us, us + u_dur, bay
            ho = min(int(t.unload_end // 60), tb.hours - 1)
            wo, b2 = bridges.book(t.unload_end + 1.0, svc * mods.wb_svc_mult[ho] * float(rng.lognormal(0, 0.2)))
        t.weigh_out, t.bridge_out = wo, b2
        t.exit = wo + svc + float(rng.uniform(1, 4))
        # censor at the window end (no future data)
        end = tb.minutes
        for attr in ("queue_start", "weigh_in", "grading", "graded_end", "unload_start", "unload_end", "weigh_out", "exit"):
            v = getattr(t, attr)
            if v is not None and v >= end:
                setattr(t, attr, None)
        for attr in ("arrival", "queue_start", "weigh_in", "grading", "graded_end", "unload_start", "unload_end", "weigh_out", "exit"):
            v = getattr(t, attr)
            if v is not None:
                setattr(t, attr, round(v * 60) / 60.0)  # whole seconds, same as the stored timestamps
        # keep the chain consistent: once a stage is censored, all later stages are too
        chain = ["queue_start", "weigh_in", "grading", "graded_end", "unload_start", "unload_end", "weigh_out", "exit"]
        cut = False
        for attr in chain:
            if attr in ("unload_start", "unload_end") and t.reject:
                continue
            if cut:
                setattr(t, attr, None)
            elif getattr(t, attr) is None:
                cut = True


def truck_status(t: Truck) -> str:
    if t.exit is not None:
        return "exited"
    if t.weigh_out is not None or t.unload_end is not None:
        return "weighing_out"
    if t.unload_start is not None:
        return "unloading"
    if t.grading is not None:
        return "grading"
    if t.weigh_in is not None:
        return "weighing_in"
    if t.queue_start is not None:
        return "queued"
    return "arriving"


def queue_lengths(trucks: list[Truck], times: np.ndarray) -> np.ndarray:
    """Trucks waiting for weigh-in (queue_start <= t < weigh_in) at each time."""
    qs = np.sort(np.array([t.queue_start for t in trucks if t.queue_start is not None]))
    wi = np.sort(np.array([t.weigh_in if t.weigh_in is not None else np.inf for t in trucks if t.queue_start is not None]))
    return np.searchsorted(qs, times, side="right") - np.searchsorted(wi, times, side="right")
