"""Generator constants: sourced parameters (via the params snapshot) + explicit engineering assumptions.

Every number the generator uses is either
  * P("<key>")  - the researcher's nominal value from docs/business/DOMAIN_PARAMETERS.json (snapshot in params.py), or
  * an entry in ASSUMED (fact category "Engineering Assumption" / "Synthetic Demonstration Data") with a reason, or
  * an entry in DEVIATIONS: a sourced key for which the generator deliberately uses a different value (with reason).
docs/DATA_GENERATION.md renders these tables. Nothing here is a real plant measurement.
"""

from __future__ import annotations

from app.seed.params import PARAMS, PROFILES

GENERATOR_VERSION = "1.0.0"
DEFAULT_SEED = 20261120


def P(key: str) -> float:
    """Nominal value of a sourced parameter (raises KeyError for unknown keys - no silent defaults)."""
    if key in DEVIATIONS:
        return DEVIATIONS[key][0]
    return PARAMS[key][0]


def P_range(key: str) -> tuple[float, float]:
    _, lo, hi, *_ = PARAMS[key]
    return float(lo), float(hi)


def profile(key: str) -> list:
    return PROFILES[key]


# key -> (value used, reason). Values stay inside the researcher's [min, max] unless stated.
DEVIATIONS: dict[str, tuple[float, str]] = {
    "capacity_utilisation_normal": (
        0.72,
        "Base daily intake = 60 t/h x 20 h x 0.72 at seasonal index 1.0. The 120-day window spans the Aug-Oct crop peak "
        "(damped index up to 1.33); at 0.78 the September intake would exceed the mill's daily capacity on most days and "
        "the ramp would overflow permanently. 0.72 is inside the sourced range [0.6, 0.92].",
    ),
    "press_count": (
        4,
        "4 screw presses x 15 t/h (= 60 t/h) instead of 6 x 10 t/h: both inside the sourced ranges ([4,8] and [8,15]); "
        "fewer presses keep the sensor table smaller and make one degraded press (PRS-03, 25% of feed) a visible share.",
    ),
    "press_unit_capacity_t_ffb_per_h": (15, "See press_count (4 x 15 t/h). Inside the sourced range [8, 15]."),
    "digester_count": (4, "One digester per press (4). Inside the sourced range [4, 8]."),
    "ramp_buffer_capacity_t": (
        600,
        "Loading-ramp + overflow floor capacity set to the sourced maximum (600 t) because peak-season afternoon "
        "arrivals (hourly weight up to 2.18x mean) build ~300-450 t of ramp stock before the night shift works it down.",
    ),
    "ffb_supply_daily_cv": (
        0.12,
        "Day-to-day intake noise uses CV 0.12 with AR(1) phi=0.5 (persistent weather/harvest rounds), inside [0.08, 0.3]; "
        "0.15 white noise on top of the crop peak produced repeated multi-day overflows.",
    ),
    "scn_press_degradation_extra_fibre_loss_pp": (
        0.10,
        "The researcher's 0.3 pp (plant-level) is a demo design value. Physically PRS-03 handles ~1/4 of the feed and "
        "its cake oil is bounded (~13% dry basis at the worst point vs 7% nominal, sourced range 5-11%), which gives "
        "~0.30 pp on the press's own share = ~0.08-0.10 pp plant-level. We keep the physically plausible value; the "
        "press-level loss (lab 'press_fibre' samples tagged PRS-03) shows the full effect.",
    ),
}


# Engineering assumptions not covered by a sourced parameter (category, value, reason).
ASSUMED: dict[str, tuple[str, float, str]] = {
    "operator_target_rate_tph": ("Engineering Assumption", 56.0, "Operators run ~93% of rated 60 t/h when FFB is available."),
    "mill_start_stock_t": ("Engineering Assumption", 100.0, "Mill (re)starts once ~1.8 h of FFB is on the ramp (campaign processing)."),
    "mill_stop_stock_t": ("Engineering Assumption", 5.0, "Mill stops when the ramp is practically empty (starvation, not downtime)."),
    "sterilizer_load_unload_min": ("Engineering Assumption", 10.0, "Door/cage handling time added to each sterilizer cycle."),
    "press_ref_cone_pressure_bar": ("Engineering Assumption", 40.0, "Reference cone pressure (= P press_cone_pressure_bar)."),
    "steam_banking_t_per_h": ("Engineering Assumption", 2.0, "Boiler steam while the mill is stopped (banked boiler, heating)."),
    "steam_process_t_per_t": ("Engineering Assumption", 0.48, "Running steam/t; with banking steam the daily ratio ~0.50 t/t (P steam_t_per_t_ffb)."),
    "tg_kwh_per_t_steam": ("Engineering Assumption", 36.0, "Back-pressure turbine specific output (~28 kg steam/kWh)."),
    "grid_import_limit_kw": ("Engineering Assumption", 300.0, "Grid connection limit; deficits above it are covered by the diesel genset."),
    "misc_base_kw": ("Engineering Assumption", 70.0, "Unmetered base load: lighting, compressors, workshop, offices, elevators."),
    "fresh_ffb_ffa_pct": ("Engineering Assumption", 2.4, "FFA of oil from FFB processed within the delay-free window (REL-07 baseline)."),
    "dobi_fresh": ("Industry Practice", 3.1, "DOBI of fresh, well-sterilised CPO; falls with delay/overripeness (no sourced number)."),
    "oer_hourly_noise_sd_pp": ("Synthetic Demonstration Data", 0.25, "Hourly measurement/process noise on OER (daily noise uses P oer_daily_noise_sd_pp)."),
    "oer_season_peak_doy": ("Engineering Assumption", 258.0, "OER seasonal term peaks mid-September with the crop peak (amplitude P oer_seasonal_amplitude_pp)."),
    "undercook_efb_gain": ("Engineering Assumption", 8.0, "EFB oil loss multiplier per unit of under-cooking index U (REL-03 extension)."),
    "undercook_condensate_gain": ("Engineering Assumption", 3.8, "Condensate oil loss multiplier per unit of U; with efb gain gives +0.15 pp at U=0.16 (P scn_steam_deviation_extra_loss_pp)."),
    "digester_temp_per_bar_header": ("Engineering Assumption", 6.7, "Digester temperature lost per bar of BPV header pressure deficit."),
    "fibre_loss_per_degc_digester": ("Engineering Assumption", 0.04, "Relative press fibre oil loss increase per degC below 93 degC."),
    "sludge_loss_per_degc_clarifier": ("Engineering Assumption", 0.10, "Relative sludge oil loss increase per degC below 90 degC (5 degC -> x1.5 = P scn_clarifier_sludge_loss_multiplier)."),
    "night_shift_rate_delta_tph": ("Synthetic Demonstration Data", -1.0, "Shift effect: night shift (B) runs ~1 t/h slower."),
    "night_shift_fibre_loss_factor": ("Synthetic Demonstration Data", 1.03, "Shift effect: +3% press fibre loss on the night shift."),
    "gate_check_min_mean": ("Engineering Assumption", 5.0, "Gate documentation/security check before the weighbridge queue."),
    "grader_count": ("Engineering Assumption", 2.0, "Grading stations working in parallel."),
    "unload_positioning_min": ("Engineering Assumption", 3.0, "Truck positioning/tipping time per unloading."),
    "weighbridge_resolution_kg": ("Engineering Assumption", 10.0, "Weighbridge display resolution."),
    "production_batch_hours": ("Engineering Assumption", 2.0, "A processing batch = 2-hour block of sterilizer cycles (~110 t FFB)."),
    "cpo_min_stock_t": ("Engineering Assumption", 700.0, "Dispatch keeps at least this CPO stock (sales cadence)."),
    "cpo_lot_min_age_days": ("Engineering Assumption", 3.0, "A daily lot is dispatched no earlier than 3 days after filling (settling + QC)."),
    "lab_noise_rel": ("Synthetic Demonstration Data", 0.06, "Relative lab measurement noise on oil-loss samples."),
}


def A(key: str) -> float:
    return ASSUMED[key][1]


# Fixed physical/electrical constants (Engineering Assumption).
VOLTAGE_V = 400.0
SQRT3 = 3**0.5
MOTOR_EFF = 0.92
AMBIENT_C = 31.0
