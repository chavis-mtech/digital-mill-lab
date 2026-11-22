"""Hourly mill simulation: ramp FIFO -> sterilization -> threshing -> digestion -> pressing -> clarification.

One loop over the hours of the window. Each hour:
  1. FFB unloaded before the hour starts is available on the ramp (FIFO cohorts keep supplier, quality, arrival time).
  2. Capacity = min(operator rate, design x thresher availability, sterilizer cycle capacity, press capacity,
     steam-limited capacity); planned/unplanned stops remove minutes; the mill (re)starts at >= 100 t stock and stops
     when the ramp runs dry (starvation is not downtime).
  3. Oil-loss model (REL-03 extended) and effective OER (REL-04) from the FFB actually processed this hour:
       U      = max(0, 1 - p_ster_peak/2.8) + 0.8*max(0, 1 - cycle/80)              (under-cooking index)
       efb    = 0.07*(1 + 8U);  condensate = 0.10*(1 + 3.8U)
       fibre  = sum_p feed_p * 0.35*(1 + 0.04*max(0, 93 - T_dig))*(1 + 0.857*sev_p)*shift / feed
       sludge = 0.40*(1 + 0.10*max(0, 90 - T_clar));  nut = 0.08*(1 + 0.25*sum_p share_p*sev_p)
       OER    = 18.2 + season(d) + (1.00 - total_loss) - 0.08*max(0, unripe - 4) - 0.10*max(0, (delay_h - 24)/24)
                + daily AR noise + hourly noise
     with delay_h = harvest-to-mill + ramp wait (tonnage-weighted over the cohorts processed).
  4. Steam: demand = processed*0.48*(1+steam_extra) + banking; supply = 40 t/h x boiler availability; operators
     throttle feed so demand <= 1.18 x supply; pressure deficit = 1 - supply/demand scales drum and BPV header pressure,
     extends sterilizer cycles (+15 min at -15%) and cools the digesters (6.7 degC per bar).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

from app.seed.assumptions import A, P


@dataclass
class RampBatch:
    batch_id: int
    truck_idx: int
    supplier: int
    unload_end: float
    mass_kg: float
    remaining_kg: float
    unripe: float
    overripe: float
    ripe: float
    h2m_h: float
    first_processed: float | None = None


def press_vib(base: float, sev: np.ndarray | float) -> np.ndarray | float:
    return base + (P("scn_press_degradation_vib_peak_mm_s") - base) * sev


def press_derate(vib: np.ndarray | float, warn: float, crit: float) -> np.ndarray | float:
    peak = P("scn_press_degradation_vib_peak_mm_s")
    return P("scn_press_degradation_throughput_derate_pct") / 100 * np.clip((vib - warn) / (peak - warn), 0, 1)


def simulate_mill(tb, rngs, batches: list[RampBatch], cal, mods, press_base_vib: list[float], vib_warn: float, vib_crit: float) -> dict:
    rng = rngs.get("mill")
    H = tb.hours
    n_press = mods.press_sev.shape[0]
    cap_design = P("mill_capacity_t_ffb_per_h")
    press_cap_unit = P("press_unit_capacity_t_ffb_per_h")
    vessel_t = P("sterilizer_cage_capacity_t") * P("sterilizer_cages_per_vessel")
    n_vessels = P("sterilizer_vessel_count")
    load_min = A("sterilizer_load_unload_min")
    boiler_max = P("boiler_installed_t_steam_per_h")
    steam_pt = A("steam_process_t_per_t")
    banking = A("steam_banking_t_per_h")
    hdr_sp, drum_sp = P("bpv_header_pressure_barg"), P("boiler_pressure_barg")
    ster_p_sp = P("sterilizer_pressure_barg")
    cyc_ref = P("sterilizer_cycle_min")
    dig_sp, clar_sp = P("digester_temp_c"), P("clarifier_temp_c")
    oer_ref, ker_ref = P("oer_pct"), P("ker_pct")
    l_efb, l_cond, l_fib, l_sld, l_oth = (P("oil_loss_efb_pct_ffb"), P("oil_loss_sterilizer_condensate_pct_ffb"), P("oil_loss_fibre_pct_ffb"),
                                          P("oil_loss_sludge_pct_ffb"), P("oil_loss_other_pct_ffb"))
    loss_ref = P("oil_loss_total_pct_ffb")
    pen_unripe, unripe_ref = P("oer_penalty_pp_per_pp_unripe"), P("ffb_unripe_share_pct")
    pen_delay = P("oer_penalty_pp_per_24h_delay")
    ffa_rise, ffa_free = P("ffa_rise_pp_per_h_delay"), P("ffa_delay_free_hours")
    fresh_ffa = A("fresh_ffb_ffa_pct")
    peak_vib = P("scn_press_degradation_vib_peak_mm_s")
    fibre_gain_peak = 13.0 / P("fibre_oil_pct_dry_basis") - 1.0  # cake oil 7% -> 13% dry basis at the worst point

    keys = ["running_min", "downtime_min", "planned_min", "received_t", "processed_t", "tph", "waiting_t", "avg_wait_h", "cycles",
            "cycle_min", "hdr_p", "drum_p", "deficit", "boiler_steam_t", "steam_supply_cap", "dig_temp", "clar_temp", "press_cone",
            "loss_fibre", "loss_efb", "loss_sludge", "loss_nut", "loss_cond", "loss_total", "cpo_t", "kernel_t", "oer", "ker", "ripe",
            "unripe", "h2m", "delay_h", "ffa", "overripe", "undercook", "ster_p_peak"]
    out = {k: np.zeros(H) for k in keys}
    out["press_feed"] = np.zeros((n_press, H))
    out["press_vib"] = np.zeros((n_press, H))
    out["press_cone_p"] = np.zeros((n_press, H))
    out["press_loss"] = np.zeros((n_press, H))
    out["press_running"] = np.zeros((n_press, H))
    cons: list[tuple[int, int, float]] = []  # (hour, batch_id, kg)

    order = sorted(range(len(batches)), key=lambda i: batches[i].unload_end)
    ptr = 0
    ramp: deque[RampBatch] = deque()
    unarrived_t = 0.0
    running = False
    cum_t = 0.0
    prev_tph = 0.0
    heavy_prev = np.concatenate([[False], cal.heavy_rain[:-1]])
    for h in range(H):
        t0 = h * 60.0
        d = h // 24
        lh = h % 24
        # FFB unloaded before t0 becomes available; FFB unloaded during the hour is reported as received this hour
        recv = 0.0
        while ptr < len(order) and batches[order[ptr]].unload_end < t0 + 60:
            b = batches[order[ptr]]
            if b.unload_end >= t0:
                recv += b.mass_kg / 1000
            ramp.append(b)
            ptr += 1
        avail_kg = sum(b.remaining_kg for b in ramp if b.unload_end < t0)
        stock_t = avail_kg / 1000
        stop = min(60.0, mods.plant_stop_min[h] + mods.planned_stop_min[h])
        avail_min = 60.0 - stop
        # steam availability (wet fuel after heavy rain costs a little boiler output)
        supply = boiler_max * max(0.2, mods.boiler_cap[h] - (0.03 if heavy_prev[d] else 0.0))
        extra = mods.steam_extra[h]
        steam_cap_tph = supply * 1.18 / (steam_pt * (1 + extra))
        # operator rate setpoint
        night = lh >= 18 or lh < 6
        rate = A("operator_target_rate_tph") + mods.rate_adj[h] + (A("night_shift_rate_delta_tph") if night else 0.0)
        if stock_t > 400:
            rate += 3.5
        elif stock_t < 80:
            rate -= 4.0
        rate += float(rng.normal(0, 0.6))
        # press capacity (degraded presses are derated by the operators)
        sev = mods.press_sev[:, h]
        vib = np.array([press_vib(press_base_vib[p], sev[p]) for p in range(n_press)])
        derate = np.array([press_derate(v, vib_warn, vib_crit) for v in vib])
        cap_p = press_cap_unit * mods.press_avail[:, h] * (1 - derate)
        # sterilizer: deficit estimate -> cycle extension -> capacity
        dem_est = min(rate, steam_cap_tph) * steam_pt * (1 + extra)
        def_est = float(np.clip(1 - supply / dem_est, 0, 0.2)) if dem_est > 0 else 0.0
        cycle = mods.ster_cycle[h] + P("scn_steam_deviation_cycle_extension_min") * min(1.0, def_est / 0.15) + float(rng.normal(0, 1.2))
        ster_cap = n_vessels * vessel_t / ((cycle + load_min) / 60.0)
        cap = max(0.0, min(rate, cap_design * mods.cap_factor[h], ster_cap, cap_p.sum(), steam_cap_tph))
        # start / stop (campaign processing)
        if not running and stock_t >= A("mill_start_stock_t") and avail_min > 0:
            running = True
        processed = 0.0
        run_min = 0.0
        if running and avail_min > 0 and cap > 0:
            processed = min(cap * avail_min / 60.0, max(0.0, stock_t))
            run_min = processed / cap * 60.0
            if stock_t - processed < A("mill_stop_stock_t"):
                running = False
        tph = processed / (run_min / 60.0) if run_min > 0 else 0.0
        # consume FIFO cohorts
        need = processed * 1000
        w_unr = w_ovr = w_rip = w_h2m = w_wait = w_ffa = 0.0
        t_mid = t0 + max(run_min, 1) / 2
        while need > 1e-6 and ramp:
            b = ramp[0]
            if b.unload_end >= t0:
                break
            take = min(b.remaining_kg, need)
            b.remaining_kg -= take
            need -= take
            if b.first_processed is None:
                b.first_processed = t0
            cons.append((h, b.batch_id, take))
            wait_h = max(0.0, (t_mid - b.unload_end) / 60.0)
            delay = b.h2m_h + wait_h
            w_unr += take * b.unripe
            w_ovr += take * b.overripe
            w_rip += take * b.ripe
            w_h2m += take * b.h2m_h
            w_wait += take * wait_h
            w_ffa += take * (fresh_ffa + ffa_rise * max(0.0, delay - ffa_free) + 0.03 * max(0.0, b.overripe - 8.0))
            if b.remaining_kg <= 1e-6:
                ramp.popleft()
        kg = processed * 1000
        # steam & pressures
        demand = processed * steam_pt * (1 + extra) + banking * (60 - run_min) / 60.0
        run_dem_rate = tph * steam_pt * (1 + extra)
        deficit = float(np.clip(1 - supply / run_dem_rate, 0, 0.3)) if run_dem_rate > 0 else 0.0
        boiler_steam = min(demand, supply)
        hdr = hdr_sp * (1 - deficit) + float(rng.normal(0, 0.03))
        drum = drum_sp * (1 - deficit) + float(rng.normal(0, 0.12))
        dig = dig_sp - A("digester_temp_per_bar_header") * max(0.0, hdr_sp - hdr) + float(rng.normal(0, 0.5))
        clar = clar_sp + mods.clar_offset[h] + float(rng.normal(0, 0.5))
        p_peak = min(ster_p_sp, hdr - 0.15) + float(rng.normal(0, 0.02))
        U = max(0.0, 1 - p_peak / ster_p_sp) + 0.8 * max(0.0, 1 - cycle / cyc_ref)
        # per-press feed and loss
        feed = processed * cap_p / cap_p.sum() if cap_p.sum() > 0 else np.zeros(n_press)
        shift_f = A("night_shift_fibre_loss_factor") if night else 1.0
        p_loss = (l_fib * (1 + A("fibre_loss_per_degc_digester") * max(0.0, dig_sp - dig)) * (1 + fibre_gain_peak * sev) * (1 + mods.press_wear[h]) * shift_f
                  * rng.lognormal(0, 0.04, n_press))
        cone = 40.0 - 60.0 * derate + rng.normal(0, 0.8, n_press)  # operators back off the cone on a damaged press
        if processed > 0:
            share = feed / processed
            fib = float((share * p_loss).sum())
            nut = l_oth * (1 + 0.25 * float((share * sev).sum())) * float(rng.lognormal(0, 0.05))
        else:
            share = np.zeros(n_press)
            fib, nut = l_fib, l_oth
        efb = l_efb * (1 + A("undercook_efb_gain") * U) * float(rng.lognormal(0, 0.05))
        cond = l_cond * (1 + A("undercook_condensate_gain") * U) * float(rng.lognormal(0, 0.05))
        sld = l_sld * (1 + A("sludge_loss_per_degc_clarifier") * max(0.0, clar_sp - clar)) * float(rng.lognormal(0, 0.05))
        total = fib + efb + cond + sld + nut
        if kg > 0:
            unr, ovr, rip, h2m, wt, ffa = (w_unr / kg, w_ovr / kg, w_rip / kg, w_h2m / kg, w_wait / kg, w_ffa / kg)
        else:
            unr = ovr = rip = h2m = wt = ffa = 0.0
        delay = h2m + wt
        oer = (oer_ref + cal.oer_season_pp[d] + (loss_ref - total) - pen_unripe * max(0.0, unr - unripe_ref)
               - pen_delay * max(0.0, (delay - 24) / 24) + cal.oer_day_noise[d] + float(rng.normal(0, A("oer_hourly_noise_sd_pp"))))
        ker = ker_ref + cal.ker_day_noise[d] - 0.03 * max(0.0, unr - unripe_ref) + float(rng.normal(0, 0.1))
        cum_prev = cum_t
        cum_t += processed
        o = out
        o["running_min"][h] = run_min
        o["downtime_min"][h] = stop
        o["planned_min"][h] = min(60.0, mods.planned_stop_min[h])
        o["received_t"][h] = recv
        o["processed_t"][h] = processed
        o["tph"][h] = tph
        o["waiting_t"][h] = sum(b.remaining_kg for b in ramp) / 1000
        o["avg_wait_h"][h] = wt if kg > 0 else np.nan
        o["cycles"][h] = int(cum_t // vessel_t) - int(cum_prev // vessel_t)
        o["cycle_min"][h] = cycle
        o["hdr_p"][h] = hdr
        o["drum_p"][h] = drum
        o["deficit"][h] = deficit
        o["boiler_steam_t"][h] = boiler_steam
        o["steam_supply_cap"][h] = supply
        o["dig_temp"][h] = dig
        o["clar_temp"][h] = clar
        o["press_cone"][h] = float(cone.mean())
        o["loss_fibre"][h], o["loss_efb"][h], o["loss_sludge"][h], o["loss_nut"][h], o["loss_cond"][h] = fib, efb, sld, nut, cond
        o["loss_total"][h] = total
        o["oer"][h] = oer if kg > 0 else np.nan
        o["ker"][h] = ker if kg > 0 else np.nan
        o["cpo_t"][h] = processed * oer / 100 if kg > 0 else 0.0
        o["kernel_t"][h] = processed * ker / 100 if kg > 0 else 0.0
        o["ripe"][h] = rip if kg > 0 else np.nan
        o["unripe"][h] = unr if kg > 0 else np.nan
        o["overripe"][h] = ovr if kg > 0 else np.nan
        o["h2m"][h] = h2m if kg > 0 else np.nan
        o["delay_h"][h] = delay if kg > 0 else np.nan
        o["ffa"][h] = ffa if kg > 0 else np.nan
        o["undercook"][h] = U
        o["ster_p_peak"][h] = p_peak
        o["press_feed"][:, h] = feed
        o["press_vib"][:, h] = vib
        o["press_cone_p"][:, h] = cone
        o["press_loss"][:, h] = p_loss
        o["press_running"][:, h] = (run_min / 60.0) * (mods.press_avail[:, h] > 0.5)
        prev_tph = tph
    del prev_tph, unarrived_t, peak_vib
    out["cons"] = cons
    out["ramp_left"] = list(ramp)
    out["feed_rate_last"] = None
    return out
