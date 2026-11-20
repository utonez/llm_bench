"""Read-side service: turns stored run summaries into API payloads.

Results are cached per (query, window) for a few minutes. The data only changes
every 6 hours, and the cache bounds Firestore reads no matter how much traffic arrives.
"""

import threading
import time
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from app.api.schemas import ModelOut, ModelSeries, ModelStatsOut, SeriesPoint
from app.bench.runner import utc_now
from app.bench.summaries import RunSummary, aggregate_summaries
from app.storage.base import ResultRepository

DEFAULT_CACHE_TTL_S = 300.0
MAX_SUMMARIES = 2000  # 30 days x 4 runs x ~16 models: a hard ceiling on one read


class StatsService:
    def __init__(
        self,
        repository: ResultRepository,
        clock: Callable[[], datetime] = utc_now,
        cache_ttl_s: float = DEFAULT_CACHE_TTL_S,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._ttl = cache_ttl_s
        self._cache: dict[tuple[Any, ...], tuple[float, Any]] = {}
        self._lock = threading.Lock()  # sync routes run in a thread pool

    def stats(self, days: int) -> list[ModelStatsOut]:
        return self._cached(("stats", days), lambda: self._stats(days))

    def timeseries(self, days: int, model: str | None) -> list[ModelSeries]:
        return self._cached(("series", days, model), lambda: self._series(days, model))

    def models(self, days: int) -> list[ModelOut]:
        return [
            ModelOut(
                provider=s.provider, model=s.model, price_ref=s.price_ref, last_run_at=s.last_run_at
            )
            for s in self.stats(days)
        ]

    def _stats(self, days: int) -> list[ModelStatsOut]:
        return [ModelStatsOut(**asdict(s)) for s in aggregate_summaries(self._summaries(days))]

    def _series(self, days: int, model: str | None) -> list[ModelSeries]:
        groups: dict[tuple[str, str], list[RunSummary]] = {}
        for summary in self._summaries(days):
            if model is None or summary.model == model:
                groups.setdefault((summary.provider, summary.model), []).append(summary)
        return [
            ModelSeries(provider=p, model=m, points=_points(group))
            for (p, m), group in sorted(groups.items())
        ]

    def _summaries(self, days: int) -> list[RunSummary]:
        since = self._clock() - timedelta(days=days)
        return self._repository.list_summaries(since=since, limit=MAX_SUMMARIES)

    def _cached(self, key: tuple[Any, ...], compute: Callable[[], Any]) -> Any:
        now = time.monotonic()
        with self._lock:
            hit = self._cache.get(key)
            if hit is not None and hit[0] > now:
                return hit[1]
        value = compute()
        with self._lock:
            self._cache[key] = (now + self._ttl, value)
        return value


def _points(group: list[RunSummary]) -> list[SeriesPoint]:
    points = []
    for summary in sorted(group, key=lambda s: s.timestamp):
        [stats] = aggregate_summaries([summary])
        points.append(
            SeriesPoint(
                timestamp=summary.timestamp,
                success_rate=stats.success_rate,
                avg_latency_ms=stats.avg_latency_ms,
                p95_latency_ms=stats.p95_latency_ms,
                accuracy=stats.accuracy,
                cost_twd_per_call=stats.cost_twd_per_call,
            )
        )
    return points
