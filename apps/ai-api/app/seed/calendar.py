"""Daily drivers: crop seasonality, weekday pattern, rain, intake noise, illustrative price series."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from app.seed.assumptions import A, P, profile
from app.seed.timebase import TimeBase

# Daily rain Markov chain by month: (P(rain | dry yesterday), P(rain | rain yesterday)). Engineering Assumption informed
# by the Surat Thani rainfall series in DOMAIN_PARAMETERS (Oct-Dec wettest, Feb-Apr driest).
RAIN_MARKOV = {1: (0.25, 0.45), 2: (0.12, 0.3), 3: (0.15, 0.3), 4: (0.25, 0.45), 5: (0.35, 0.55), 6: (0.35, 0.55),
               7: (0.35, 0.55), 8: (0.35, 0.55), 9: (0.40, 0.60), 10: (0.50, 0.65), 11: (0.55, 0.70), 12: (0.50, 0.65)}


@dataclass
class Calendar:
    season: np.ndarray  # damped monthly supply index, interpolated daily
    weekday: np.ndarray
    rain_mm: np.ndarray
    noise: np.ndarray  # multiplicative intake noise (AR(1))
    oer_season_pp: np.ndarray
    oer_day_noise: np.ndarray
    ker_day_noise: np.ndarray

    @property
    def heavy_rain(self) -> np.ndarray:
        return self.rain_mm >= 25

    @property
    def rainy(self) -> np.ndarray:
        return self.rain_mm >= 2


def _season_index(tb: TimeBase) -> np.ndarray:
    vals = profile("ffb_supply_monthly_index_catchment_damped")
    out = np.empty(tb.days)
    for d in range(tb.days):
        dd = tb.day_date(d)
        # piecewise-linear between mid-months
        m = dd.month - 1
        frac = (dd.day - 15) / 30.0
        if frac >= 0:
            a, b = vals[m], vals[(m + 1) % 12]
            out[d] = a + (b - a) * frac
        else:
            a, b = vals[(m - 1) % 12], vals[m]
            out[d] = b + (b - a) * frac
    return out


def build_calendar(tb: TimeBase, rngs, forced_rain: dict[int, float], forced_dry: set[int], noise_free: set[int] | None = None) -> Calendar:
    noise_free = noise_free or set()
    kd_zero: list[int] = []
    rng = rngs.get("calendar")
    season = _season_index(tb)
    wk_prof = profile("weekday_intake_factor")
    weekday = np.array([wk_prof[tb.weekday(d)] for d in range(tb.days)])
    rain = np.zeros(tb.days)
    wet = False
    for d in range(tb.days):
        p_dry, p_wet = RAIN_MARKOV[tb.day_date(d).month]
        wet = rng.random() < (p_wet if wet else p_dry)
        mm = float(rng.exponential(14.0)) if wet else 0.0
        rain[d] = mm
    for d, mm in forced_rain.items():
        if 0 <= d < tb.days:
            rain[d] = mm
    for d in forced_dry:
        if 0 <= d < tb.days and d not in forced_rain:
            rain[d] = 0.0
    # AR(1) intake noise with stationary CV = P(ffb_supply_daily_cv)
    cv = P("ffb_supply_daily_cv")
    phi = 0.5
    e = rng.normal(0, cv * math.sqrt(1 - phi**2), tb.days)
    x = np.zeros(tb.days)
    for d in range(tb.days):
        x[d] = (phi * x[d - 1] if d else 0.0) + e[d]
    noise = np.exp(x - cv**2 / 2)
    amp = P("oer_seasonal_amplitude_pp")
    peak = A("oer_season_peak_doy")
    oer_season = np.array([amp * math.cos(2 * math.pi * (tb.day_date(d).timetuple().tm_yday - peak) / 365.0) for d in range(tb.days)])
    sd = P("oer_daily_noise_sd_pp")
    od = np.zeros(tb.days)
    eo = rng.normal(0, sd * math.sqrt(1 - 0.6**2), tb.days)
    for d in range(tb.days):
        od[d] = (0.6 * od[d - 1] if d else 0.0) + eo[d]
    kd = rng.normal(0, 0.08, tb.days)
    for d in forced_dry:  # protected comparison days: no intake-noise excursion
        if 0 <= d < tb.days:
            noise[d] = 1.0
    for d in noise_free:  # scenario focus/baseline days: no daily OER noise draw (contrast = drivers only; documented)
        if 0 <= d < tb.days:
            od[d] = 0.0
            kd_zero.append(d)
    kd[kd_zero] = 0.0
    return Calendar(season, weekday, rain, noise, oer_season, od, kd)


def build_prices(tb: TimeBase, rngs) -> list[dict]:
    """Illustrative daily price series (THB). Not market data; mutually consistent per REL-16."""
    rng = rngs.get("prices")
    rows = []
    cpo = P("cpo_price_thb_per_t") / 1000.0  # THB/kg
    kernel = P("palm_kernel_price_thb_per_t") / 1000.0
    diesel = P("diesel_price_thb_per_l")
    daily_sd = P("cpo_price_volatility_sd_pct_per_month") / 100 / math.sqrt(30)
    note = "Illustrative synthetic series (anchored on DOMAIN_PARAMETERS nominal values); not market data."
    pid = 0
    for d in range(tb.days):
        cpo *= math.exp(rng.normal(0, daily_sd) - 0.5 * daily_sd**2 + 0.15 * (P("cpo_price_thb_per_t") / 1000.0 - cpo) / cpo / 30)
        kernel *= math.exp(rng.normal(0, daily_sd * 1.3) + 0.15 * (P("palm_kernel_price_thb_per_t") / 1000.0 - kernel) / kernel / 30)
        diesel *= math.exp(rng.normal(0, 0.003))
        ffb = cpo * P("ffb_price_thb_per_kg") / (P("cpo_price_thb_per_t") / 1000.0) * (1 + rng.normal(0, 0.004))
        dd = tb.day_date(d)
        for commodity, price, unit in (
            ("cpo", cpo, "THB/kg"),
            ("kernel", kernel, "THB/kg"),
            ("ffb", ffb, "THB/kg"),
            ("electricity", P("grid_electricity_thb_per_kwh"), "THB/kWh"),
            ("diesel", diesel, "THB/L"),
            ("shell", P("pks_price_thb_per_t") / 1000.0, "THB/kg"),
            ("efb", P("efb_price_thb_per_t") / 1000.0, "THB/kg"),
        ):
            pid += 1
            rows.append({"id": pid, "commodity": commodity, "price_date": dd, "price": round(price, 4), "unit": unit,
                         "currency": "THB", "source_note": note, "data_kind": "synthetic"})
    return rows
