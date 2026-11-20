"""In-memory repository for tests and local runs."""

from collections.abc import Sequence
from datetime import datetime

from app.bench.models import BenchResult
from app.bench.summaries import RunSummary
from app.storage.base import DEFAULT_LIST_LIMIT


class InMemoryResultRepository:
    def __init__(self) -> None:
        self._results: tuple[BenchResult, ...] = ()
        self._summaries: tuple[RunSummary, ...] = ()

    def save_results(self, results: Sequence[BenchResult]) -> None:
        self._results = (*self._results, *results)

    def list_results(
        self, since: datetime | None = None, limit: int = DEFAULT_LIST_LIMIT
    ) -> list[BenchResult]:
        return _newest_first(self._results, since, limit)

    def save_summaries(self, summaries: Sequence[RunSummary]) -> None:
        self._summaries = (*self._summaries, *summaries)

    def list_summaries(
        self, since: datetime | None = None, limit: int = DEFAULT_LIST_LIMIT
    ) -> list[RunSummary]:
        return _newest_first(self._summaries, since, limit)


def _newest_first[T: (BenchResult, RunSummary)](
    items: Sequence[T], since: datetime | None, limit: int
) -> list[T]:
    selected = [item for item in items if since is None or item.timestamp >= since]
    selected.sort(key=lambda item: item.timestamp, reverse=True)
    return selected[:limit]
