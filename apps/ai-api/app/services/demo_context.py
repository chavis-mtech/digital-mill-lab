"""DemoContext model and helpers. Every service takes a DemoContext - never global state (the build plan section 3).

Playback model (ADR-005/ADR-011): one deterministic 120-day timeline; `as_of` is the demo clock and services
must never read data with ts > as_of for "actual" views (forecasts may extend beyond it).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import ApiError
from app.models.enums import ProvenanceKind, Role, ScenarioCode


class DemoContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    as_of: datetime  # UTC, tz-aware, inside the dataset window
    as_of_explicit: bool  # False when defaulted (anchor) or resolved from scenario_id
    scenario_id: ScenarioCode | None = None
    session_id: str | None = None  # lower-case uuid; None = read-only shared baseline
    role: Role = Role.public_viewer
    request_id: str | None = None
    window_start: datetime
    window_end: datetime  # exclusive
    timezone: str = "Asia/Bangkok"

    # ---- convenience -----------------------------------------------------
    @property
    def local_as_of(self) -> datetime:
        from zoneinfo import ZoneInfo  # noqa: PLC0415

        return self.as_of.astimezone(ZoneInfo(self.timezone))

    @property
    def business_date(self) -> date:
        """Mill business day (Asia/Bangkok) containing as_of."""
        return self.local_as_of.date()

    def day_bounds(self, d: date | None = None) -> tuple[datetime, datetime]:
        """UTC [start, end) of a mill business day (default: the as_of day)."""
        from zoneinfo import ZoneInfo  # noqa: PLC0415

        tz = ZoneInfo(self.timezone)
        d = d or self.business_date
        start = datetime.combine(d, time.min, tzinfo=tz).astimezone(UTC)
        return start, start + timedelta(days=1)

    def period_bounds(self, days: int) -> tuple[datetime, datetime]:
        """UTC [start, as_of] for 'last N days' ending at the demo clock (clipped to the window)."""
        start, _ = self.day_bounds(self.business_date - timedelta(days=days - 1))
        return max(start, self.window_start), self.as_of


def session_filter(column: Any, ctx: DemoContext) -> ColumnElement[bool]:
    """Rows visible to this caller: the shared seeded baseline (NULL) plus the caller's own session rows."""
    if ctx.session_id is None:
        return column.is_(None)
    return or_(column.is_(None), column == ctx.session_id)


def require_session(ctx: DemoContext) -> str:
    """Writes need a sandbox session (ADR-006)."""
    if not ctx.session_id:
        raise ApiError(
            428,
            "session_required",
            "This action needs a demo session. Create one via POST /api/v1/demo/session and send it as X-Demo-Session.",
        )
    return ctx.session_id


def provenance(
    kind: ProvenanceKind | str, source: str, ctx: DemoContext, model_version: str | None = None
) -> dict[str, Any]:
    """Build the provenance object required on every numeric payload (see schemas.common.Provenance)."""
    return {"kind": ProvenanceKind(kind).value, "source": source, "as_of": ctx.as_of, "model_version": model_version}


def parse_as_of(raw: str, settings: Settings) -> datetime:
    """ISO datetime with offset -> as given; naive datetime -> mill-local; date-only -> 18:00 mill-local."""
    raw = raw.strip()
    try:
        if len(raw) == 10:
            d = date.fromisoformat(raw)
            dt = datetime.combine(d, time(18, 0), tzinfo=settings.tz)
        else:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=settings.tz)
    except ValueError as exc:
        raise ApiError(422, "invalid_as_of", "as_of must be an ISO-8601 date or datetime", {"value": raw[:64]}) from exc
    dt = dt.astimezone(UTC)
    if not (settings.window_start <= dt < settings.window_end):
        raise ApiError(
            422,
            "as_of_out_of_window",
            "as_of is outside the synthetic dataset window",
            {"window_start": settings.window_start.isoformat(), "window_end": settings.window_end.isoformat()},
        )
    return dt


def resolve_scenario_focus(db: Session | None, scenario: ScenarioCode) -> datetime | None:
    """Default as_of for a scenario = scenario_runs.focus_ts (None if not seeded yet)."""
    if db is None:
        return None
    from app.models.platform import ScenarioRun  # noqa: PLC0415

    try:
        return db.execute(select(ScenarioRun.focus_ts).where(ScenarioRun.code == scenario.value)).scalar_one_or_none()
    except SQLAlchemyError:
        db.rollback()
        return None
