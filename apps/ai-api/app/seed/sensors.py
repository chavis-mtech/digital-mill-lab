"""Sensor time series derived from the hourly plant state (same state that drives process_hourly and energy).

Per sensor: sample times every `sampling_seconds`; hourly drivers are interpolated to the sample time; within an
hour the mill runs a contiguous block (at the start of the hour if it was already running, else at the end);
thermal signals pass a first-order lag; noise is AR(1). Data-quality abnormalities (dropouts at
P sensor_dropout_rate_pct, injected flatlines/spikes/dropout windows) are applied last.
Returns, per sensor: minutes, values, quality codes, and the 'equipment running' mask used by the alarm logic.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import lfilter

from app.seed.assumptions import AMBIENT_C, A, P

QUALITY = np.array(["good", "uncertain", "bad"])


def _lag(x: np.ndarray, dt_min: float, tau_min: float) -> np.ndarray:
    a = 1 - np.exp(-dt_min / tau_min)
    y, _ = lfilter([a], [1, -(1 - a)], x, zi=[x[0] * (1 - a)])
    return y


def _ar1(rng, n: int, sd: float, phi: float = 0.7) -> np.ndarray:
    e = rng.normal(0, sd * np.sqrt(1 - phi**2), n)
    return lfilter([1.0], [1, -phi], e)


def build_sensor_series(core, sensors, eq_state, eb, prod) -> dict[int, dict]:
    tb, m, mods = core.tb, core.mill, core.mods
    H = tb.hours
    t_mid = (np.arange(H) + 0.5) * 60
    run_frac = m["running_min"] / 60.0
    prev_run = np.concatenate([[0.0], run_frac[:-1]]) > 0.5
    out: dict[int, dict] = {}
    tank_level = prod["_tank_level_t"]
    dropout = P("sensor_dropout_rate_pct") / 100
    hdr_sp, drum_sp = P("bpv_header_pressure_barg"), P("boiler_pressure_barg")
    faults: dict[str, list] = {}
    for f in mods.sensor_faults:
        faults.setdefault(f.sensor_code, []).append(f)
    for sp in sensors:
        rng = core.rngs.get(f"sensor.{sp.code}")
        dt = sp.sampling_s / 60.0
        t = np.arange(0, tb.minutes, dt)
        n = len(t)
        hi = np.minimum((t // 60).astype(int), H - 1)
        within = t - hi * 60

        def interp(arr, t=t):
            return np.interp(t, t_mid, arr)

        def running_mask(rf, hi=hi, within=within):
            rf_h = rf[hi]
            start = np.where(prev_run[hi], within < rf_h * 60, within >= (1 - rf_h) * 60)
            return (rf_h >= 0.999) | ((rf_h > 0.001) & start)

        e = sp.equip
        es = eq_state[e.code]
        mill_run = running_mask(run_frac)
        # start-up alarm inhibit: process alarms only after the mill has run continuously for >= 60 min
        win = max(1, int(round(60 / dt)))
        settled = np.convolve(mill_run.astype(float), np.ones(win), mode="full")[:n] >= win - 1e-9
        eq_run = running_mask(np.clip(es["run"], 0, 1)) if e.rated_kw or e.load_kind == "press" else mill_run
        noload_run = running_mask(np.clip(es["run"] + es["noload"], 0, 1)) & ~eq_run if e.rated_kw else np.zeros(n, bool)
        if e.load_kind in ("utility_steam", "utility_const"):
            eq_run = np.ones(n, bool)
        ov = mods.overlays.get(e.code)
        load = interp(es["load"])
        alarm_mask = eq_run.copy()
        k = sp.kind
        if k == "vib":
            if e.load_kind == "press":
                base = interp(m["press_vib"][e.index])
            else:
                base = np.full(n, e.vib_healthy) + (interp(ov["vib_add"]) if ov is not None else 0)
            v = base * (0.88 + 0.12 * load) * (1 + _ar1(rng, n, 0.05)) + rng.normal(0, 0.04, n)
            v = np.where(eq_run, v, np.where(noload_run, base * 0.75 + rng.normal(0, 0.04, n), 0.12 + np.abs(rng.normal(0, 0.03, n))))
            v = np.maximum(v, 0.05)
        elif k == "brg_temp":
            rise = P("bearing_temp_normal_c") - AMBIENT_C
            amb = AMBIENT_C + 3 * np.sin(2 * np.pi * ((t / 60) % 24 - 9) / 24)
            add = interp(ov["temp_add"]) if ov is not None else 0.0
            if e.load_kind == "press":
                add = add + 24.0 * interp(mods.press_sev[e.index]) ** 1.2
            act = np.where(eq_run, 0.75 + 0.25 * load, np.where(noload_run, 0.55, 0.0))
            target = amb + rise * act + add * np.where(eq_run | noload_run, 1.0, 0.3)
            v = _lag(target, dt, 40.0) + _ar1(rng, n, 0.5)
        elif k == "current":
            fla = e.fla_a
            cm = interp(es["cur_mult"])
            fr = interp(core.mods.press_sev[e.index]) * (P("scn_press_degradation_current_rise_pct") / 100 * 0.88) if e.load_kind == "press" else 0.0
            v = np.where(eq_run, fla * (0.30 + 0.62 * load + fr) * cm * (1 + _ar1(rng, n, 0.015)), np.where(noload_run, fla * 0.30 * (1 + rng.normal(0, 0.02, n)), 0.0))
            v = np.maximum(v, 0)
        elif k == "rpm":
            v = np.where(eq_run, 11.0 * (0.9 + 0.1 * load) + rng.normal(0, 0.12, n), 0.0)
        elif k == "cone":
            v = np.where(eq_run, interp(m["press_cone_p"][e.index]) + rng.normal(0, 0.5, n), 0.0)
        elif k == "state":
            v = eq_run.astype(float)
        elif k == "run_hours":
            init = 9000 + (e.id * 7919) % 30000
            cum = init + np.cumsum(np.clip(es["run"], 0, 1)) if e.load_kind != "dg" else init / 20 + np.cumsum(eb["dg"] > 0)
            v = cum[hi].astype(float)
        elif k == "dig_temp":
            target = np.where(mill_run | noload_run, interp(m["dig_temp"]), 86.0)
            v = _lag(target, dt, 45.0) + rng.normal(0, 0.35, n)
            alarm_mask = settled
        elif k == "drum_p":
            v = np.where(mill_run, interp(m["drum_p"]), drum_sp - 0.8) + _ar1(rng, n, 0.12)
            alarm_mask = settled
        elif k == "steam_flow":
            rate = np.where(mill_run, interp(eb["steam_run"]), A("steam_banking_t_per_h"))
            v = np.maximum(rate * (1 + _ar1(rng, n, 0.03)), 0)
        elif k == "flue_temp":
            target = 165 + 30 * np.clip(interp(m["boiler_steam_t"]) / P("boiler_installed_t_steam_per_h"), 0, 1.2) + interp(mods.flue_add)
            v = _lag(target, dt, 60.0) + _ar1(rng, n, 1.5)
        elif k == "hdr_p":
            v = np.where(mill_run, interp(m["hdr_p"]), hdr_sp) + _ar1(rng, n, 0.025)
            alarm_mask = settled
        elif k == "tg_load":
            v = np.where(mill_run, interp(eb["tg_kw"]), 0.0) * (1 + rng.normal(0, 0.015, n))
            v = np.maximum(v, 0)
        elif k == "dg_load":
            v = eb["dg"][hi] * (1 + rng.normal(0, 0.01, n))
        elif k == "ves_p":
            cyc = interp(m["cycle_min"]) + A("sterilizer_load_unload_min")
            phase = ((t + e.index * cyc / 5.0) % cyc) / cyc
            peak = interp(m["ster_p_peak"])
            prof = np.select([phase < 0.08, phase < 0.18, phase < 0.24, phase < 0.34, phase < 0.86, phase < 0.95],
                             [0.0, 0.55, 0.25, 0.8, 1.0, 0.3], 0.0)
            v = np.where(mill_run, prof * peak + rng.normal(0, 0.03, n), 0.0)
            v = np.maximum(v, 0)
        elif k == "ves_temp":
            # paired with vessel pressure sensor: saturated steam temperature ~ 100 * p_abs^0.25 (Engineering Assumption)
            cyc = interp(m["cycle_min"]) + A("sterilizer_load_unload_min")
            phase = ((t + e.index * cyc / 5.0) % cyc) / cyc
            peak = interp(m["ster_p_peak"])
            prof = np.select([phase < 0.08, phase < 0.18, phase < 0.24, phase < 0.34, phase < 0.86, phase < 0.95], [0.0, 0.55, 0.25, 0.8, 1.0, 0.3], 0.0)
            p = np.where(mill_run, prof * peak, 0.0)
            target = np.where(mill_run, 100 * (p + 1.013) ** 0.25, 55.0)
            v = _lag(target, dt, 12.0) + rng.normal(0, 0.4, n)
        elif k == "clr_temp":
            target = np.where(mill_run, interp(m["clar_temp"]), 87.0)
            v = _lag(target, dt, 60.0) + rng.normal(0, 0.3, n)
            alarm_mask = settled
        elif k == "clr_level":
            v = np.where(mill_run, 71.0, 62.0) + _ar1(rng, n, 1.5)
        elif k == "tank_level":
            v = tank_level[e.index][hi] / P("cpo_storage_tank_capacity_t") * 100 + rng.normal(0, 0.15, n)
            v = np.clip(v, 0, 100)
        elif k == "tank_temp":
            v = P("cpo_storage_temp_c") + 1.5 * np.sin(2 * np.pi * ((t / 60) % 24 - 14) / 24) + _ar1(rng, n, 0.4)
        else:
            raise ValueError(k)
        q = np.zeros(n, dtype=np.int8)
        keep = rng.random(n) >= dropout
        for f in faults.get(sp.code, []):
            sel = (t >= f.start) & (t < f.end)
            if f.kind == "flatline" and sel.any():
                v = v.copy()
                v[sel] = v[np.argmax(sel)]
            elif f.kind == "spike" and sel.any():
                idx = np.where((t >= f.start) & (t < f.start + 600))[0][: int(f.params.get("n_spikes", 3)) * 6: 6]
                v = v.copy()
                v[idx] = v[idx] * 4 + 3
                q[idx] = 1
            elif f.kind == "dropout":
                keep &= ~sel
        dec = 0 if sp.kind in ("state", "run_hours") else 3
        out[sp.id] = {"t": t[keep], "v": np.round(v[keep], dec), "q": q[keep], "alarm_mask": alarm_mask[keep], "code": sp.code}
    return out
