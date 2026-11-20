"""In-memory repository for tests and local runs."""

from collections.abc import Sequence
from datetime import datetime

from app.bench.models import BenchResult
from app.storage.base import DEFAULT_LIST_LIMIT


class InMemoryResultRepository:
    def __init__(self) -> None:
        self._results: tuple[BenchResult, ...] = ()

    def save_results(self, results: Sequence[BenchResult]) -> None:
        self._results = (*self._results, *results)

    def list_results(
        self, since: datetime | None = None, limit: int = DEFAULT_LIST_LIMIT
    ) -> list[BenchResult]:
        selected = [r for r in self._results if since is None or r.timestamp >= since]
        selected.sort(key=lambda r: r.timestamp, reverse=True)
        return selected[:limit]
