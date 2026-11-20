"""Read-only routes. Handlers are plain `def`: the Firestore client is synchronous,
so FastAPI runs them in its thread pool instead of blocking the event loop."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import StatsServiceDep
from app.api.schemas import Envelope, HealthOut, ModelOut, ModelSeries, ModelStatsOut

MAX_DAYS = 30
DEFAULT_DAYS = 7
MODEL_ID_PATTERN = r"^[A-Za-z0-9._:/-]+$"

Days = Annotated[int, Query(ge=1, le=MAX_DAYS, description="Look-back window in days")]
ModelFilter = Annotated[
    str | None, Query(max_length=100, pattern=MODEL_ID_PATTERN, description="Exact model id")
]

health_router = APIRouter()
v1_router = APIRouter(prefix="/v1", tags=["benchmarks"])


@health_router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok")


@v1_router.get("/stats", response_model=Envelope[list[ModelStatsOut]])
def get_stats(service: StatsServiceDep, days: Days = DEFAULT_DAYS) -> Envelope[list[ModelStatsOut]]:
    """Per-model reliability, latency, accuracy and NT$ cost over the window."""
    return Envelope(success=True, data=service.stats(days), meta={"days": days})


@v1_router.get("/timeseries", response_model=Envelope[list[ModelSeries]])
def get_timeseries(
    service: StatsServiceDep, days: Days = DEFAULT_DAYS, model: ModelFilter = None
) -> Envelope[list[ModelSeries]]:
    """One point per benchmark run, oldest first, for trend charts."""
    return Envelope(
        success=True, data=service.timeseries(days, model), meta={"days": days, "model": model}
    )


@v1_router.get("/models", response_model=Envelope[list[ModelOut]])
def get_models(service: StatsServiceDep, days: Days = MAX_DAYS) -> Envelope[list[ModelOut]]:
    """Models measured in the window, with their reference-price id."""
    return Envelope(success=True, data=service.models(days), meta={"days": days})
