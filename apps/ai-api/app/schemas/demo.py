"""Demo control: sandbox sessions, roles, simulated-live tick (owner: backend-b)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import ApiModel, DemoContextOut, KpiValue, Role


class SessionCreateResponse(ApiModel):
    session_id: str = Field(description="Send as X-Demo-Session on later requests")
    created_at: datetime
    note: str = "Sandbox session: your changes are visible only to you and can be reset at any time."


class SessionResetResponse(ApiModel):
    session_id: str
    deleted: dict[str, int] = Field(description="Rows removed per table (business rows only; audit log is kept)")
    reset_at: datetime


class ResetAllResponse(ApiModel):
    sessions_cleared: int
    deleted: dict[str, int]
    reset_at: datetime


class RoleOut(ApiModel):
    role: Role
    label_en: str
    label_th: str
    read_only: bool
    permissions: list[str]
    copilot_tools: list[str]


class RoleListResponse(ApiModel):
    items: list[RoleOut]
    notice: str = "Roles are simulated viewpoints for the demo, not production authentication."
    label: str = "Simulated viewpoint, not authentication"


class DemoContextResponse(ApiModel):
    context: DemoContextOut
    default_as_of: datetime
    latest_data_ts: datetime | None = Field(None, description="Newest synthetic fact in the DB (None if not seeded)")


class TickRequest(ApiModel):
    step_minutes: int = Field(10, ge=1, le=240)


class TickResponse(ApiModel):
    """Simulated Live Mode: the client advances its own clock; server returns the next as_of + headline deltas."""

    previous_as_of: datetime
    next_as_of: datetime
    wrapped: bool = Field(description="True if the clock looped back to the window start")
    headline: list[KpiValue]
    new_alert_ids: list[int] = []
    label: str = "SIMULATION - Simulated live mode: replaying synthetic data, not a live plant feed."
    # ---- additive (backend-b) ----
    mode: str = "simulation"
    step_minutes: int | None = None
    scenario_id: str | None = None
    window_start: datetime | None = None
    window_end: datetime | None = Field(None, description="Exclusive end of the window the clock loops in (scenario window or dataset window)")
