"""Per-run summaries (written by the job) and multi-run aggregation (read by the API).

One summary per (run, provider, model) keeps the API cheap: a week of data is ~84
small documents instead of ~2,300 per-call documents, which matters for Firestore's
free read quota. Successful latencies are kept as a list so P95 stays exact across runs.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from statistics import fmean

from pydantic import BaseModel, ConfigDict, Field

from app.bench.models import BenchResult
from app.bench.stats import percentile
from app.pricing.fx import FxRate

PER_1K = 1000


class RunSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    timestamp: datetime
    provider: str
    model: str
    price_ref: str | None
    calls: int = Field(ge=0)
    successes: int = Field(ge=0)
    latencies_ms: list[float]
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    graded: int = Field(ge=0)
    correct: int = Field(ge=0)
    error_counts: dict[str, int]
    cost_usd: float | None  # market-reference cost of this run's calls
    usd_twd: float | None
    fx_date: str | None


@dataclass(frozen=True)
class ModelStats:
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


def build_run_summaries(
    results: Sequence[BenchResult], fx: FxRate | None, price_refs: Mapping[str, str]
) -> list[RunSummary]:
    groups: dict[tuple[str, str, str], list[BenchResult]] = {}
    for result in results:
        groups.setdefault((result.run_id, result.provider, result.model), []).append(result)
    return [
        _summarize_run(run_id, provider, model, group, fx, price_refs.get(model))
        for (run_id, provider, model), group in groups.items()
    ]


def _summarize_run(
    run_id: str,
    provider: str,
    model: str,
    group: list[BenchResult],
    fx: FxRate | None,
    price_ref: str | None,
) -> RunSummary:
    ok = [r for r in group if r.success]
    graded = [r.correct for r in ok if r.correct is not None]
    costs = [r.cost_usd for r in group if r.cost_usd is not None]
    return RunSummary(
        run_id=run_id,
        timestamp=min(r.timestamp for r in group),
        provider=provider,
        model=model,
        price_ref=price_ref,
        calls=len(group),
        successes=len(ok),
        latencies_ms=[r.latency_ms for r in ok],
        input_tokens=sum(r.input_tokens for r in group),
        output_tokens=sum(r.output_tokens for r in group),
        graded=len(graded),
        correct=sum(graded),
        error_counts=dict(Counter(r.error_kind or "unknown" for r in group if not r.success)),
        cost_usd=sum(costs) if costs else None,
        usd_twd=fx.usd_twd if fx else None,
        fx_date=fx.on.isoformat() if fx else None,
    )


def aggregate_summaries(summaries: Sequence[RunSummary]) -> list[ModelStats]:
    groups: dict[tuple[str, str], list[RunSummary]] = {}
    for summary in summaries:
        groups.setdefault((summary.provider, summary.model), []).append(summary)
    return [_aggregate(p, m, group) for (p, m), group in sorted(groups.items())]


def _aggregate(provider: str, model: str, group: list[RunSummary]) -> ModelStats:
    calls = sum(s.calls for s in group)
    latencies = [v for s in group for v in s.latencies_ms]
    graded = sum(s.graded for s in group)
    correct = sum(s.correct for s in group)
    errors: Counter[str] = Counter()
    for s in group:
        errors.update(s.error_counts)

    priced = [s for s in group if s.cost_usd is not None and s.usd_twd is not None]
    priced_calls = sum(s.calls for s in priced)
    cost_twd = sum(s.cost_usd * s.usd_twd for s in priced)  # type: ignore[operator]
    priced_correct = sum(s.correct for s in priced)
    per_call = cost_twd / priced_calls if priced_calls else None

    return ModelStats(
        provider=provider,
        model=model,
        price_ref=next((s.price_ref for s in group if s.price_ref), None),
        runs=len(group),
        calls=calls,
        success_rate=sum(s.successes for s in group) / calls if calls else 0.0,
        avg_latency_ms=fmean(latencies) if latencies else None,
        p95_latency_ms=percentile(latencies, 95) if latencies else None,
        accuracy=correct / graded if graded else None,
        error_counts=dict(errors),
        cost_twd_per_call=per_call,
        cost_twd_per_1k_calls=per_call * PER_1K if per_call is not None else None,
        cost_twd_per_correct=cost_twd / priced_correct if priced_correct else None,
        last_run_at=max(s.timestamp for s in group),
    )
