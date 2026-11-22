"""Equipment electrical state + plant energy balance (REL-08/09/10), hourly.

Per motor-driven asset: running fraction, process load (0..1), electrical load L = 0.30 + 0.62*load (no-load
current ~30% FLA), kW = rated_kW * L * health current multiplier. Plant electricity = sum(assets) + unmetered base.
Supply: back-pressure turbine (36 kWh per t steam while the mill runs and steam >= 8 t/h) -> grid import up to
300 kW -> diesel genset. Biomass: fuel HHV needed = steam_t * 2.2 GJ/t / (0.85 * boiler efficiency); fibre first,
shell for the rest.
"""

from __future__ import annotations

import numpy as np

from app.seed.assumptions import A, P

STEAM_ENTHALPY_GJ_PER_T = 2.2  # REL-10
FIBRE_GJ_PER_T_WET = P("biomass_hhv_gj_per_t_dry") * (1 - P("pressed_fibre_moisture_pct") / 100)
SHELL_GJ_PER_T_WET = P("biomass_hhv_gj_per_t_dry") * (1 - P("shell_moisture_pct") / 100)
STAGE_STEAM_SHARE = {"STERILIZATION": 0.42, "DIGESTION": 0.25, "CLARIFICATION": 0.21, "KERNEL_RECOVERY": 0.12}


def friction_term(core, e) -> np.ndarray | float:
    """Bearing/gearbox wear adds friction torque: extra current as a fraction of FLA, independent of feed.
    Sized so the press current is ~+12% (P scn_press_degradation_current_rise_pct) at peak at nominal feed."""
    if e.load_kind != "press":
        return 0.0
    return P("scn_press_degradation_current_rise_pct") / 100 * 0.88 * core.mods.press_sev[e.index]


def equipment_state(core) -> dict[str, dict[str, np.ndarray]]:
    tb, mill, mods = core.tb, core.mill, core.mods
    H = tb.hours
    run = mill["running_min"] / 60.0
    tph = mill["tph"]
    stop = mill["downtime_min"] / 60.0
    idle_frac = np.clip(1 - run - stop, 0, 1)
    steam_load = np.clip(mill["boiler_steam_t"] / P("boiler_installed_t_steam_per_h"), 0, 1.2)
    # equipment breakdown windows -> not running for that fraction of the hour
    down: dict[str, np.ndarray] = {}
    for b in mods.breakdowns:
        arr = down.setdefault(b.equipment_code, np.zeros(H))
        mods.add_stop(arr, b.start, b.end)
    st: dict[str, dict[str, np.ndarray]] = {}
    for e in core.equip:
        r = np.zeros(H)
        load = np.zeros(H)
        noload = np.zeros(H)  # fraction of the hour running without feed (idle running)
        if e.load_kind == "process":
            r = run.copy()
            load = np.clip(tph / P("mill_capacity_t_ffb_per_h"), 0, 1.05)
            if e.code in ("LR-CNV-01", "CNV-02"):
                noload = np.where(mods.idle_running, idle_frac, 0.0)
        elif e.load_kind == "thresher":
            r = run.copy()
            load = np.clip(tph / 2 / e.rated_capacity, 0, 1.05)
            noload = np.where(mods.idle_running, idle_frac, 0.0)
        elif e.load_kind in ("press", "digester"):
            p = e.index
            r = mill["press_running"][p]
            fr = np.divide(mill["press_feed"][p], run, out=np.zeros(H), where=run > 0)
            load = np.clip(fr / P("press_unit_capacity_t_ffb_per_h"), 0, 1.05)
            if e.load_kind == "digester":
                noload = np.where(mods.idle_running, idle_frac, 0.0)
        elif e.load_kind == "utility_steam":
            r = np.ones(H)
            mult = mods.fan_mult if e.code == "BLR-FAN-01" else mods.fwp_mult
            load = np.clip((0.3 + 0.6 * steam_load) * mult, 0, 1.1)
        elif e.load_kind == "utility_const":
            r = np.ones(H)
            load = 0.35 + 0.35 * run  # water / effluent pumping follows the process load
        elif e.load_kind in ("vessel", "boiler", "clarifier"):
            r = run.copy() if e.load_kind == "vessel" else np.ones(H)
        if e.code in down:
            frac_down = np.clip(down[e.code] / 60.0, 0, 1)
            r = np.clip(r - frac_down, 0, 1) if e.load_kind not in ("press", "digester") else r * (1 - frac_down)
            noload = np.clip(noload - frac_down, 0, 1)
        ov = mods.overlays.get(e.code)
        cur_mult = ov["cur_mult"].copy() if ov is not None else np.ones(H)
        kw = np.zeros(H)
        kw_idle = np.zeros(H)
        if e.rated_kw:
            L = 0.30 + 0.62 * load + friction_term(core, e)
            kw = e.rated_kw * L * cur_mult * r + e.rated_kw * 0.30 * noload
            if e.load_kind in ("utility_steam", "utility_const"):
                kw_idle = kw * (1 - run)
            else:
                kw_idle = e.rated_kw * 0.30 * noload
        st[e.code] = {"run": r, "load": load, "noload": noload, "cur_mult": cur_mult, "kw": kw, "kw_idle": kw_idle}
    return st


def energy_balance(core, eq_state, prices_by_day: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    tb, mill, mods = core.tb, core.mill, core.mods
    H = tb.hours
    run = mill["running_min"] / 60.0
    misc = A("misc_base_kw") + mods.misc_add_kw
    elec = misc + sum(s["kw"] for s in eq_state.values())
    idle = misc * (1 - run) + sum(s["kw_idle"] for s in eq_state.values())
    idle = np.minimum(idle, elec)
    steam = mill["boiler_steam_t"]
    # steam rate while running (t/h) drives the turbine
    steam_run = np.divide(np.maximum(steam - A("steam_banking_t_per_h") * (1 - run), 0), run, out=np.zeros(H), where=run > 0)
    elec_run_kw = np.divide(elec - idle, run, out=np.zeros(H), where=run > 0)
    tg_kw = np.where((run > 0) & (steam_run >= 8.0), np.minimum(np.minimum(elec_run_kw, steam_run * A("tg_kwh_per_t_steam")), P("turbine_generator_kw")), 0.0)
    self_gen = tg_kw * run
    deficit = np.maximum(elec - self_gen, 0)
    grid = np.minimum(deficit, A("grid_import_limit_kw"))
    dg = deficit - grid
    diesel = dg * P("diesel_l_per_kwh") + mill["processed_t"] * P("diesel_l_per_t_ffb_handling")
    water = mill["processed_t"] * (P("water_m3_per_t_ffb") - 0.1) + 6.0
    heavy_prev = np.repeat(np.concatenate([[False], core.cal.heavy_rain[:-1]]), 24)
    eff = P("boiler_efficiency") + mods.boiler_eff_delta - np.where(heavy_prev, 0.02, 0.0)
    need_gj = steam * STEAM_ENTHALPY_GJ_PER_T / (0.85 * eff)
    fibre_avail = mill["processed_t"] * P("fibre_pct_ffb") / 100
    fibre = np.minimum(fibre_avail, need_gj / FIBRE_GJ_PER_T_WET)
    shell = np.maximum(need_gj - fibre * FIBRE_GJ_PER_T_WET, 0) / SHELL_GJ_PER_T_WET
    day = np.arange(H) // 24
    cost = grid * prices_by_day["electricity"][day] + diesel * prices_by_day["diesel"][day]
    return {"elec": elec, "idle": idle, "self_gen": self_gen, "tg_kw": tg_kw, "grid": grid, "dg": dg, "diesel": diesel,
            "water": water, "fibre": fibre, "shell": shell, "cost": cost, "eff": eff, "steam_run": steam_run}
