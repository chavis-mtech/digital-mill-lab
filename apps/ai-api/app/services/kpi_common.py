"""Shared helpers for backend-a analytics (KPI, production, energy, logistics). Owner: backend-a.

Conventions used everywhere in backend-a services (docs/business/KPI_DEFINITIONS.md section 1):

* **Ratio of sums**: OER, KER, kWh/t, cost/t, availability over a window = sum(numerator) / sum(denominator).
* **as_of is a hard wall** (ADR-005): hourly fact rows (`process_hourly`, `energy_consumption`, ts = start of hour)
  are included only when the hour is *complete* at the demo clock (`ts + 1 h <= as_of`). Event rows (truck
  timestamps, deliveries, lab samples, alerts) are included only when their timestamp is `<= as_of`.
* **Business day** = 00:00-24:00 Asia/Bangkok (ADR-016). Shifts A 06:00-18:00, B 18:00-06:00 (data engine).
* **Previous period** = the immediately preceding window of the same length (for `today`: the same clock span on
  the previous day, so a partial day is compared with the same partial day).
* Missing denominators return ``None`` (never 0 or a fabricated value).
* Thresholds come from DOMAIN_PARAMETERS (snapshot `app.seed.params.PARAMS`, read-only) or KPI_DEFINITIONS section 5.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models.platform import Price
from app.schemas.common import Period, TrendDirection
from app.seed.params import PARAMS
from app.services.demo_context import DemoContext, provenance

HOUR = timedelta(hours=1)

# KPI_DEFINITIONS section 5 display thresholds (all Engineering Assumptions, configurable here, not in the UI).
THRESHOLDS: dict[str, dict[str, float]] = {
    "oer_gap_pp": {"amber": 0.3, "red": 0.8},  # below the trailing 28-day baseline
    "availability_pct": {"amber": 93.0, "red": 85.0},  # below
    "kwh_per_t": {"amber": 18.5, "red": 21.0},  # above
    "steam_t_per_t": {"amber": 0.55, "red": 0.62},  # above
    "cpo_ffa_pct": {"amber": 4.0, "red": 5.0},  # above
    "queue_min": {"amber": 15.0, "red": 60.0},  # above
    "turnaround_min": {"amber": 60.0, "red": 120.0},  # above
    "wait_to_process_h": {"amber": 12.0, "red": 24.0},  # above
    "critical_alerts": {"amber": 1.0, "red": 2.0},  # count at or above
}
BASELINE_DAYS = 28  # trailing baseline window (KPI_DEFINITIONS 4.4)


def param(key: str) -> float:
    """Nominal value of a DOMAIN_PARAMETERS key (frozen snapshot owned by the data engine)."""
    return float(PARAMS[key][0])


def param_meta(key: str) -> dict[str, Any]:
    nominal, lo, hi, unit, category, source, _conf = PARAMS[key]
    return {"value": nominal, "min": lo, "max": hi, "unit": unit, "category": category, "source": source}


def fact_tag(category: str) -> str:
    """Map a DOMAIN_PARAMETERS category to the SPEC fact taxonomy (FactTag)."""
    return {
        "Verified Public Fact": "verified_public_fact",
        "Historical Public Information": "historical_public_information",
        "Industry Practice": "industry_practice",
        "Engineering Assumption": "engineering_assumption",
        "Synthetic Demonstration Data": "synthetic_demonstration_data",
    }.get(category, "engineering_assumption")


def assumption_from_param(key: str, label: str, value: float | None = None, editable: bool = True) -> dict[str, Any]:
    m = param_meta(key)
    return {
        "key": key,
        "label": label,
        "value": m["value"] if value is None else value,
        "unit": m["unit"],
        "tag": fact_tag(m["category"]),
        "source": f"docs/business/DOMAIN_PARAMETERS.json#{key} ({m['source']})",
        "editable": editable,
    }


# ---------------------------------------------------------------------------- time windows
@dataclass(frozen=True)
class Window:
    start: datetime  # UTC inclusive
    end: datetime  # UTC; data must be <= end (end <= as_of)

    @property
    def hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600.0

    def shift(self, delta: timedelta) -> Window:
        return Window(self.start - delta, self.end - delta)


def tz(ctx: DemoContext) -> ZoneInfo:
    return ZoneInfo(ctx.timezone)


def local_midnight(ctx: DemoContext, d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=tz(ctx)).astimezone(UTC)


def period_windows(
    ctx: DemoContext, period: Period | str, start: date | None = None, end: date | None = None
) -> tuple[Window, Window | None]:
    """Current window ending at the demo clock and the previous window of the same length.

    today -> [as_of day 00:00, as_of]; previous = same span one day earlier.
    7d / 30d -> [00:00 of (as_of day - N + 1), as_of]; previous = shifted by N days.
    custom -> [start 00:00, min(end + 1 day 00:00, as_of)]; previous = shifted by the window length.
    Windows are clipped to the dataset start; previous is None when it would lie fully before the dataset.
    """
    period = Period(period)
    as_of = ctx.as_of
    if period == Period.custom:
        if start is None or end is None:
            raise ApiError(422, "invalid_period", "period=custom requires start and end dates")
        if end < start:
            raise ApiError(422, "invalid_period", "end must not be before start")
        s = local_midnight(ctx, start)
        e = min(local_midnight(ctx, end + timedelta(days=1)), as_of)
        if s >= as_of:
            raise ApiError(422, "invalid_period", "start must be before the demo clock (as_of)")
        if (end - start).days > 120:
            raise ApiError(422, "invalid_period", "custom window is limited to 120 days")
        span = e - s
        cur = Window(max(s, ctx.window_start), e)
        prev_span = timedelta(days=(end - start).days + 1)
    else:
        days = {Period.today: 1, Period.last_7d: 7, Period.last_30d: 30}[period]
        s = local_midnight(ctx, ctx.business_date - timedelta(days=days - 1))
        cur = Window(max(s, ctx.window_start), as_of)
        prev_span = timedelta(days=days)
        span = as_of - s
    prev = Window(cur.start - prev_span, cur.start - prev_span + span) if period != Period.custom else cur.shift(prev_span)
    if prev.end <= ctx.window_start:
        return cur, None
    return cur, Window(max(prev.start, ctx.window_start), prev.end)


def complete_hour_cutoff(end: datetime) -> datetime:
    """Latest hourly-row ts (start of hour) that is complete at `end`: ts <= end - 1 h."""
    return end - HOUR


# ---------------------------------------------------------------------------- numbers
def safe_div(num: float | None, den: float | None, scale: float = 1.0) -> float | None:
    if num is None or den is None or den == 0 or (isinstance(den, float) and math.isnan(den)):
        return None
    v = num / den * scale
    return None if math.isnan(v) else v


def rnd(v: float | None, nd: int = 3) -> float | None:
    if v is None:
        return None
    try:
        if math.isnan(v):
            return None
    except TypeError:
        return None
    return round(float(v), nd)


def kpi_value(
    ctx: DemoContext,
    key: str,
    label: str,
    value: float | None,
    unit: str,
    source: str,
    previous: float | None = None,
    good_direction: TrendDirection | str = TrendDirection.up,
    status: str | None = None,
    target: float | None = None,
    kind: str = "synthetic_actual",
    nd: int = 3,
) -> dict[str, Any]:
    """KpiValue dict. delta = value - previous (percentage points for % KPIs); delta_pct = relative change %."""
    delta = None if value is None or previous is None else value - previous
    delta_pct = safe_div(delta, abs(previous) if previous else None, 100.0)
    return {
        "key": key,
        "label": label,
        "value": rnd(value, nd),
        "unit": unit,
        "previous": rnd(previous, nd),
        "delta": rnd(delta, nd),
        "delta_pct": rnd(delta_pct, 2),
        "good_direction": TrendDirection(good_direction).value,
        "status": status,
        "target": rnd(target, nd),
        "provenance": provenance(kind, source, ctx),
    }


def status_above(value: float | None, key: str) -> str | None:
    """Severity for 'higher is worse' KPIs: amber -> medium, red -> high, green -> None."""
    if value is None:
        return None
    t = THRESHOLDS[key]
    if value > t["red"]:
        return "high"
    if value > t["amber"]:
        return "medium"
    return None


def status_below(value: float | None, key: str) -> str | None:
    if value is None:
        return None
    t = THRESHOLDS[key]
    if value < t["red"]:
        return "high"
    if value < t["amber"]:
        return "medium"
    return None


def oer_status(value: float | None, baseline: float | None) -> str | None:
    """KPI_DEFINITIONS 4.4: green within 0.3 pp of the 28-day baseline, amber 0.3-0.8 pp below, red > 0.8 pp below."""
    if value is None or baseline is None:
        return None
    gap = baseline - value
    if gap > THRESHOLDS["oer_gap_pp"]["red"]:
        return "high"
    if gap > THRESHOLDS["oer_gap_pp"]["amber"]:
        return "medium"
    return None


# ---------------------------------------------------------------------------- prices
def price_map(db: Session, commodity: str, until: date | None = None) -> dict[date, float]:
    """Daily illustrative price series (prices table; synthetic random walk around sourced nominal values)."""
    q = select(Price.price_date, Price.price).where(Price.commodity == commodity)
    if until is not None:
        q = q.where(Price.price_date <= until)
    return {d: float(p) for d, p in db.execute(q).all()}


def price_on(prices: dict[date, float], d: date, fallback: float | None = None) -> float | None:
    if d in prices:
        return prices[d]
    earlier = [k for k in prices if k <= d]
    if earlier:
        return prices[max(earlier)]
    return fallback


def to_local(ctx: DemoContext, ts: datetime) -> datetime:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts.astimezone(tz(ctx))


def iso_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)
