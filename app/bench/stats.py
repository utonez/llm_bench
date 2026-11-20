"""Aggregate per-call results into per-model summaries."""

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from statistics import fmean

from app.bench.models import BenchResult


@dataclass(frozen=True)
class ModelSummary:
    provider: str
    model: str
    calls: int
    success_rate: float
    avg_latency_ms: float | None
    p95_latency_ms: float | None
    avg_input_tokens: float | None
    avg_output_tokens: float | None
    accuracy: float | None  # over graded, successful calls only
    error_counts: dict[str, int] = field(default_factory=dict)


def percentile(values: Sequence[float], pct: float) -> float:
    """Nearest-rank percentile: always returns an observed value."""
    if not values:
        raise ValueError("percentile of empty sequence")
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def summarize(results: Sequence[BenchResult]) -> list[ModelSummary]:
    groups: dict[tuple[str, str], list[BenchResult]] = {}
    for result in results:
        groups.setdefault((result.provider, result.model), []).append(result)
    return [_summarize_group(p, m, group) for (p, m), group in sorted(groups.items())]


def _summarize_group(provider: str, model: str, group: list[BenchResult]) -> ModelSummary:
    ok = [r for r in group if r.success]
    latencies = [r.latency_ms for r in ok]
    graded = [r.correct for r in ok if r.correct is not None]
    errors = Counter(r.error_kind or "unknown" for r in group if not r.success)

    return ModelSummary(
        provider=provider,
        model=model,
        calls=len(group),
        success_rate=len(ok) / len(group),
        avg_latency_ms=fmean(latencies) if latencies else None,
        p95_latency_ms=percentile(latencies, 95) if latencies else None,
        avg_input_tokens=fmean(r.input_tokens for r in ok) if ok else None,
        avg_output_tokens=fmean(r.output_tokens for r in ok) if ok else None,
        accuracy=sum(graded) / len(graded) if graded else None,
        error_counts=dict(errors),
    )
