"""FFB Supplier & Traceability (owner: backend-b). Mass-balance attribution by default; not a certification claim."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import ApiModel, Disclaimer


class TraceNode(ApiModel):
    id: str = Field(description="'<type>:<db id>' e.g. 'delivery:123'")
    type: str = Field(description="supplier | plantation | delivery | ticket | ffb_batch | production_batch | cpo_lot")
    label: str
    ts: datetime | None = None
    quantity: float | None = None
    unit: str | None = None
    attributes: dict = {}


class TraceEdge(ApiModel):
    source: str
    target: str
    mass: float | None = None
    unit: str | None = None
    share: float | None = Field(None, description="Fraction of the target attributable to the source")
    method: str = Field("mass_balance", description="lot_based | mass_balance")


class TraceGraphResponse(ApiModel):
    direction: str = Field(description="forward (supplier->lot) | backward (lot->suppliers)")
    root: str
    nodes: list[TraceNode]
    edges: list[TraceEdge]
    method: str
    method_explanation: str
    truncated: bool = False


class LotOut(ApiModel):
    id: int
    code: str
    tank_code: str
    fill_start_ts: datetime
    fill_end_ts: datetime | None
    quantity_t: float
    ffa_pct: float | None
    status: str
    supplier_count: int | None = None


class LotListResponse(ApiModel):
    items: list[LotOut]
    total: int


class DeliveryOut(ApiModel):
    id: int
    code: str
    supplier_code: str
    plantation_code: str | None
    received_ts: datetime
    net_kg: int
    accepted_kg: int
    grade: str
    ripe_pct: float | None
    ticket_no: str | None


class DeliveryListResponse(ApiModel):
    items: list[DeliveryOut]
    total: int


class SupplierShare(ApiModel):
    supplier_code: str
    supplier_name: str
    ffb_kg: float
    share_pct: float
    attributed_cpo_t: float


class TraceReportResponse(ApiModel):
    lot: LotOut
    method: str
    supplier_shares: list[SupplierShare]
    production_batches: list[str]
    quality_summary: dict
    sustainability_fields: dict = Field({}, description="RSPO-style data-model sketch fields; not a certification")
    disclaimers: list[Disclaimer]
