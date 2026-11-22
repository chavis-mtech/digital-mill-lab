"""Time axis + deterministic RNG factory.

Internal time unit = minutes since the dataset window start (mill-local midnight of the first day, ADR-016).
Asia/Bangkok has no DST (UTC+7 all year), so local hour = (minute // 60) % 24 and day = minute // 1440.
All stored timestamps are UTC.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np

MILL_TZ = ZoneInfo("Asia/Bangkok")


class Rngs:
    """One root seed -> independent, named sub-generators (stable across runs and platforms)."""

    def __init__(self, root: int) -> None:
        self.root = int(root)

    def get(self, name: str) -> np.random.Generator:
        return np.random.default_rng([self.root, zlib.crc32(name.encode("utf-8"))])


@dataclass(frozen=True)
class TimeBase:
    anchor: date
    days: int
    start_date: date = field(init=False)
    start_utc: datetime = field(init=False)

    def __post_init__(self) -> None:
        start_date = self.anchor - timedelta(days=self.days - 1)
        object.__setattr__(self, "start_date", start_date)
        object.__setattr__(self, "start_utc", datetime.combine(start_date, time.min, tzinfo=MILL_TZ).astimezone(UTC))
        # sanity: the zone really is a fixed +7 offset over the window
        end_local = datetime.combine(self.anchor, time(23, 0), tzinfo=MILL_TZ)
        assert end_local.utcoffset() == timedelta(hours=7)

    @property
    def hours(self) -> int:
        return self.days * 24

    @property
    def minutes(self) -> int:
        return self.days * 1440

    @property
    def end_utc(self) -> datetime:
        return self.start_utc + timedelta(days=self.days)

    def ts(self, minute: float) -> datetime:
        """UTC timestamp (naive, UTC) for a minute offset - rounded to whole seconds."""
        return (self.start_utc + timedelta(seconds=round(float(minute) * 60))).replace(tzinfo=None)

    def day_date(self, d: int) -> date:
        return self.start_date + timedelta(days=int(d))

    def day_of(self, minute: float) -> int:
        return int(minute // 1440)

    def date_of(self, minute: float) -> date:
        return self.day_date(int(minute // 1440))

    def weekday(self, d: int) -> int:
        return self.day_date(d).weekday()

    def day_index(self, dd: date) -> int:
        return (dd - self.start_date).days

    def local_minute(self, d: int, hh: float, mm: float = 0) -> float:
        return d * 1440 + hh * 60 + mm

    def iso_local(self, minute: float) -> str:
        return (self.start_utc + timedelta(minutes=float(minute))).astimezone(MILL_TZ).isoformat()

    def ts_strings(self, minutes: np.ndarray) -> np.ndarray:
        """Vectorised SQLAlchemy-SQLite DATETIME text ('YYYY-MM-DD HH:MM:SS.ffffff', UTC)."""
        base = np.datetime64(self.start_utc.replace(tzinfo=None), "us")
        arr = base + (np.round(minutes * 60).astype(np.int64) * 1_000_000).astype("timedelta64[us]")
        return np.char.replace(np.datetime_as_string(arr, unit="us"), "T", " ")
