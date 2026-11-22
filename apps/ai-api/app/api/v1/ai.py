"""AI endpoints: OER forecast, anomalies, failure risk, energy/logistics models, model cards. Owner: ml."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.api.v1._contract import STD_RESPONSES, contract
from app.db.session import get_db
from app.deps import require_permission
from app.ml import service as svc
from app.schemas.ai import (
    AnomalyListResponse,
    AnomalyOut,
    AnomalyStatusRequest,
    FailureRiskResponse,
    ForecastResponse,
    ModelCard,
    ModelCardListResponse,
    ModelInfo,
    ModelRunRequest,
    ModelRunResponse,
    OerExplanationResponse,
    OerForecastResponse,
    QueuePredictionResponse,
)
from app.schemas.common import AnomalyStatus, Period, Severity
from app.services.demo_context import DemoContext, require_session
from app.services.rbac import Permission as P

OWNER = "ml"
router = APIRouter(prefix="/ai", tags=["ai"], responses=STD_RESPONSES)
_read = require_permission(P.read_ai)
_DAYS = {Period.today: 1, Period.last_7d: 7, Period.last_30d: 30, Period.custom: 30}


def _impl(task: str, permission=P.read_ai) -> dict:
    return contract(permission, OWNER, task, status="implemented")


# ---- AI-B01 OER forecast -------------------------------------------------------------
@router.get("/oer/forecast", response_model=OerForecastResponse, summary="OER forecast with uncertainty band + naive baseline",
            openapi_extra=_impl("DML-047", P.read_ai))
def oer_forecast(horizon_h: int = Query(24, ge=1, le=168), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return svc.oer_forecast(db, ctx, horizon_h)


@router.get("/oer/explanation", response_model=OerExplanationResponse, summary="Feature contributions for an OER prediction",
            openapi_extra=_impl("DML-049", P.read_ai))
def oer_explanation(ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return svc.oer_explanation(db, ctx)


@router.get("/oer/model", response_model=ModelInfo, summary="Active OER model version + measured metrics",
            openapi_extra=_impl("DML-047", P.read_ai))
def oer_model(ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return svc.model_info(db, "oer_forecast")


# ---- anomalies (AI-B02, AI-C02, AI-E02, AI-D04) ----------------------------------------
@router.get("/anomalies/production", response_model=AnomalyListResponse, summary="Production anomalies (OER, steam, rate, energy, loss)",
            openapi_extra=_impl("DML-048", P.read_ai))
def production_anomalies(
    period: Period = Query(Period.last_7d),
    severity: Severity | None = Query(None),
    status: AnomalyStatus | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    ctx: DemoContext = Depends(_read),
    db: Session = Depends(get_db),
):
    return svc.list_anomalies(db, ctx, "production", _DAYS[period], severity=severity, status=status, limit=limit)


@router.get("/anomalies/equipment", response_model=AnomalyListResponse, summary="Equipment anomalies with contributing sensors",
            openapi_extra=_impl("DML-053", P.read_ai))
def equipment_anomalies(
    equipment_id: int | None = Query(None, ge=1),
    period: Period = Query(Period.last_7d),
    limit: int = Query(50, ge=1, le=200),
    ctx: DemoContext = Depends(_read),
    db: Session = Depends(get_db),
):
    return svc.list_anomalies(db, ctx, "equipment", _DAYS[period], equipment_id=equipment_id, limit=limit)


@router.get("/anomalies/{anomaly_id}", response_model=AnomalyOut, summary="Anomaly detail (evidence, normal range, possible factors)",
            openapi_extra=_impl("DML-049", P.read_ai))
def get_anomaly(anomaly_id: int = Path(ge=1), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return svc.get_anomaly(db, ctx, anomaly_id)


@router.post("/anomalies/{anomaly_id}/status", response_model=AnomalyOut, summary="Human verification: acknowledge / verify / dismiss",
             openapi_extra=_impl("DML-048", P.anomaly_verify))
def set_anomaly_status(
    body: AnomalyStatusRequest,
    anomaly_id: int = Path(ge=1),
    ctx: DemoContext = Depends(require_permission(P.anomaly_verify)),
    db: Session = Depends(get_db),
):
    require_session(ctx)
    return svc.set_status(db, ctx, anomaly_id, body.to_status.value, body.note)


# ---- AI-C03 failure risk -----------------------------------------------------------------
@router.get("/failure-risk", response_model=FailureRiskResponse, summary="Relative failure-risk ranking (not a probability)",
            openapi_extra=_impl("DML-054", P.read_ai))
def failure_risk(limit: int = Query(20, ge=1, le=100), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return svc.failure_risk(db, ctx, limit)


# ---- AI-E01/E02 energy ---------------------------------------------------------------------
@router.get("/energy/forecast", response_model=ForecastResponse, summary="Energy consumption forecast",
            openapi_extra=_impl("DML-067", P.read_ai))
def energy_forecast(horizon_h: int = Query(48, ge=1, le=336), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return svc.energy_forecast(db, ctx, horizon_h)


@router.get("/energy/anomalies", response_model=AnomalyListResponse, summary="Energy high vs production volume",
            openapi_extra=_impl("DML-068", P.read_ai))
def energy_anomalies(period: Period = Query(Period.last_30d), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return svc.list_anomalies(db, ctx, "energy", _DAYS[period], limit=200)


# ---- AI-D01/D02/D04 logistics ----------------------------------------------------------------
@router.get("/logistics/queue-prediction", response_model=QueuePredictionResponse, summary="Predicted waiting time for trucks in queue",
            openapi_extra=_impl("DML-062", P.read_ai))
def queue_prediction(ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return svc.queue_prediction(db, ctx)


@router.get("/logistics/arrival-forecast", response_model=ForecastResponse, summary="Truck arrival pattern forecast",
            openapi_extra=_impl("DML-062", P.read_ai))
def arrival_forecast(horizon_h: int = Query(24, ge=1, le=168), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return svc.arrival_forecast(db, ctx, horizon_h)


@router.get("/logistics/anomalies", response_model=AnomalyListResponse, summary="Implausible weights / excessive waits (review flags, not accusations)",
            openapi_extra=_impl("DML-062", P.read_ai))
def logistics_anomalies(period: Period = Query(Period.last_7d), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return svc.list_anomalies(db, ctx, "logistics", _DAYS[period], limit=200)


# ---- model cards & on-demand runs ----------------------------------------------------------------
@router.get("/models", response_model=ModelCardListResponse, summary="All model cards with measured metrics vs baselines",
            openapi_extra=_impl("DML-111", P.read_ai))
def list_models(ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    from app.ml.common import MODEL_NAMES  # noqa: PLC0415

    return {"items": [svc.model_card(db, n) for n in MODEL_NAMES]}


@router.get("/models/{name}", response_model=ModelCard, summary="One model card",
            openapi_extra=_impl("DML-111", P.read_ai))
def get_model(name: str = Path(max_length=64, pattern="^[a-z0-9_]+$"), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return svc.model_card(db, name)


@router.post("/models/{name}/run", response_model=ModelRunResponse, summary="Run inference at the demo clock (AI Analyst)",
             openapi_extra=_impl("DML-102", P.model_run))
def run_model(
    body: ModelRunRequest,
    name: str = Path(max_length=64, pattern="^[a-z0-9_]+$"),
    ctx: DemoContext = Depends(require_permission(P.model_run)),
    db: Session = Depends(get_db),
):
    return svc.run_model(db, ctx, name)
