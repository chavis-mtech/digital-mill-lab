"""Core simulation pipeline: registry -> schedule -> calendar -> trucks/queue -> ramp -> mill, with the supplier
quota feedback loop (when the morning ramp stock is high, the mill limits next deliveries - standard practice in the
crop peak; without it the September intake would exceed daily capacity and the ramp would overflow).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.seed.assumptions import P
from app.seed.calendar import Calendar, build_calendar
from app.seed.episodes import build_schedule
from app.seed.logistics import Truck, generate_trucks, simulate_queue
from app.seed.mill import RampBatch, simulate_mill
from app.seed.registry import VIB_LIMITS, EquipSpec, SupplierSpec, build_suppliers, equipment_specs
from app.seed.timebase import Rngs, TimeBase


@dataclass
class Core:
    tb: TimeBase
    rngs: Rngs
    equip: list[EquipSpec]
    suppliers: list[SupplierSpec]
    plantations: list[dict]
    mods: object
    scenarios: list
    injected: list
    protected: set[int]
    cal: Calendar
    trucks: list[Truck]
    intake_targets: np.ndarray
    outlier_labels: list[dict]
    batches: list[RampBatch]
    mill: dict
    quota_iterations: int


def _ramp_batches(trucks: list[Truck]) -> list[RampBatch]:
    out = []
    for t in trucks:
        if t.weigh_out is None or t.reject or t.unload_end is None:
            continue
        ripe = max(0.0, 100.0 - t.unripe - t.overripe - t.empty_bunch)
        out.append(RampBatch(len(out) + 1, t.idx, t.supplier, t.unload_end, float(t.payload_kg), float(t.payload_kg),
                             t.unripe, t.overripe, ripe, t.h2m_h))
    return out


def run_core(tb: TimeBase, seed: int) -> Core:
    rngs = Rngs(seed)
    equip = equipment_specs()
    suppliers, plantations = build_suppliers(rngs.get("suppliers"))
    mods, scenarios, injected, protected = build_schedule(tb, rngs, suppliers, [e.code for e in equip])
    cal = build_calendar(tb, rngs, mods.forced_rain, mods.forced_dry, mods.noise_free_days)
    press = [e for e in equip if e.load_kind == "press"]
    warn, crit = (P(k) for k in VIB_LIMITS[press[0].vib_class])
    cap_ramp = P("ramp_buffer_capacity_t")
    it = 0
    while True:
        it += 1
        trucks, targets, labels = generate_trucks(tb, rngs, suppliers, cal, mods)
        simulate_queue(tb, rngs, trucks, mods)
        batches = _ramp_batches(trucks)
        mill = simulate_mill(tb, rngs, batches, cal, mods, [e.vib_healthy for e in press], warn, crit)
        if it >= 6:
            break
        changed = False
        w = mill["waiting_t"]
        for d in range(1, tb.days):
            if d in mods.quota_exempt:
                continue
            day_max = w[d * 24:(d + 1) * 24].max()
            if day_max > cap_ramp * 0.95:
                f = float(np.clip(1 - (day_max - cap_ramp * 0.85) / 1500.0, 0.75, 0.97))
                for dd in (d - 1, d):
                    if dd not in mods.quota_exempt:
                        mods.quota[dd] *= f
                changed = True
        if not changed:
            break
    return Core(tb, rngs, equip, suppliers, plantations, mods, scenarios, injected, protected, cal, trucks, targets, labels,
                batches, mill, it)
