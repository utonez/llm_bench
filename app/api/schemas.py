"""Response schemas. Every endpoint returns the same envelope (see Envelope)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class Envelope[T](BaseModel):
    success: bool
    data: T | None = None
    error: str | None = None
    meta: dict[str, Any] | None = None


class ModelStatsOut(BaseModel):
    provider: str
    model: str
    price_ref: str | None
    runs: int
    calls: int
    success_rate: float
    avg_latency_ms: float | None
    p95_latency_ms: float | None
    accuracy: float | None
    error_counts: dict[str, int]
    cost_twd_per_call: float | None
    cost_twd_per_1k_calls: float | None
    cost_twd_per_correct: float | None
    last_run_at: datetime


class SeriesPoint(BaseModel):
    timestamp: datetime
    success_rate: float
    avg_latency_ms: float | None
    p95_latency_ms: float | None
    accuracy: float | None
    cost_twd_per_call: float | None


class ModelSeries(BaseModel):
    provider: str
    model: str
    points: list[SeriesPoint]


class ModelOut(BaseModel):
    provider: str
    model: str
    price_ref: str | None
    last_run_at: datetime


class HealthOut(BaseModel):
    status: str
