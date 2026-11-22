"""Palm Mill Production Intelligence (owner: backend-a)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import Field

from app.schemas.common import ApiModel, BandSeries, Formula, KpiValue, NormalRange, Provenance, Quantity, Series


class MassBalance(ApiModel):
    """FFB in -> products/by-products out, as % of FFB processed (checks the data obeys mass balance)."""

    ffb_processed_t: float
    cpo_t: float
    kernel_t: float
    shell_t: float | None = None
    fibre_t: float | None = None
    efb_t: float | None = None
    pome_m3: float | None = None
    oil_losses_t: float | None = None
    closure_pct: float | None = Field(None, description="Sum of outputs / FFB x 100 (water/evaporation excluded)")
    formulas: list[Formula] = []
    provenance: Provenance


class ProductionSummaryResponse(ApiModel):
    business_date: date
    kpis: list[KpiValue] = Field(description="ffb_received_t, ffb_processed_t, cpo_t, kernel_t, oer_pct, ker_pct, throughput_tph, operating_h, downtime_h, ffb_waiting_t")
    mass_balance: MassBalance
    oer_formula: Formula
    window_start: datetime | None = None
    window_end: datetime | None = Field(None, description="Window end (<= as_of); a day in progress is cut at as_of")


class OerTrendResponse(ApiModel):
    granularity: str
    oer: Series
    ker: Series | None = None
    expected_oer: Series | None = Field(None, description="Expected OER given FFB quality (model or rule) for comparison")
    ffb_ripe_pct: Series | None = None
    expected_band: BandSeries | None = Field(None, description="Expected OER range from history (trailing 28 days +/- 2 s.d.)")
    note: str | None = None


class ProcessVariable(ApiModel):
    key: str = Field(examples=["steam_pressure_bar"])
    label: str
    value: Quantity
    normal_range: NormalRange | None = None
    status: str = Field("normal", description="normal | warning | critical (computed against normal_range)")
    trend_24h: list[float | None] = []


class ProcessStateResponse(ApiModel):
    ts: datetime
    running: bool
    variables: list[ProcessVariable]
    note: str | None = None


class ShiftOut(ApiModel):
    id: int
    business_date: date
    shift_code: str
    start_ts: datetime
    end_ts: datetime
    ffb_processed_t: float
    cpo_t: float
    kernel_t: float
    oer_pct: float | None
    ker_pct: float | None
    operating_hours: float
    downtime_min: float
    provenance: Provenance


class ShiftListResponse(ApiModel):
    items: list[ShiftOut]
    total: int
    note: str | None = None


class LossComponent(ApiModel):
    key: str = Field(examples=["press_fibre"])
    label: str
    pct_of_ffb: float | None
    benchmark_pct: float | None = Field(None, description="Industry-practice reference (docs/business)")
    lost_cpo_t: float | None = None


class OilLossResponse(ApiModel):
    total_loss_pct: float | None
    components: list[LossComponent]
    series: list[Series]
    provenance: Provenance
    benchmark_total_pct: float | None = None
    note: str | None = None


class BatchOut(ApiModel):
    id: int
    code: str
    start_ts: datetime
    end_ts: datetime
    ffb_input_t: float
    cpo_t: float
    kernel_t: float
    oer_pct: float
    ker_pct: float
    trace_method: str
    supplier_count: int | None = None


class BatchListResponse(ApiModel):
    items: list[BatchOut]
    total: int


class QualityParameter(ApiModel):
    sample_point: str
    parameter: str
    latest: Quantity
    limit: NormalRange | None = None
    series: Series


class QualityResponse(ApiModel):
    parameters: list[QualityParameter]
