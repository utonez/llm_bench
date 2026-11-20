"""Storage boundary: business logic depends on this, not on Firestore."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from app.bench.models import BenchResult
from app.bench.summaries import RunSummary

DEFAULT_LIST_LIMIT = 1000


class ResultRepository(Protocol):
    def save_results(self, results: Sequence[BenchResult]) -> None: ...

    def list_results(
        self, since: datetime | None = None, limit: int = DEFAULT_LIST_LIMIT
    ) -> list[BenchResult]:
        """Newest first."""
        ...

    def save_summaries(self, summaries: Sequence[RunSummary]) -> None: ...

    def list_summaries(
        self, since: datetime | None = None, limit: int = DEFAULT_LIST_LIMIT
    ) -> list[RunSummary]:
        """Newest first."""
        ...
