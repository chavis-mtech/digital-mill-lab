"""Service metadata and health (owner: architect - implemented)."""

from __future__ import annotations

from datetime import date, datetime

from app.schemas.common import ApiModel, Disclaimer


class DataWindow(ApiModel):
    start_date: date
    end_date: date
    days: int
    start_utc: datetime
    end_utc_exclusive: datetime
    timezone: str


class MetaResponse(ApiModel):
    product: str
    tagline: str
    version: str
    environment: str
    demo_mode: bool
    data_window: DataWindow
    anchor_date: date
    default_as_of: datetime
    copilot_mode: str
    disclaimers: list[Disclaimer]
    api_prefix: str = "/api/v1"


class HealthResponse(ApiModel):
    status: str
    version: str


class ReadyCheck(ApiModel):
    name: str
    ok: bool
    detail: str | None = None


class ReadyResponse(ApiModel):
    status: str
    checks: list[ReadyCheck]
