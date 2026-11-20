"""Firestore-backed repository.

Collections:
  bench_results  one document per measured call (raw data, kept for audit/drill-down)
  run_summaries  one document per (run, provider, model) — what the API reads
"""

import hashlib
from collections.abc import Sequence
from datetime import datetime
from typing import Any, TypeVar

from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import BaseModel

from app.bench.models import BenchResult
from app.bench.summaries import RunSummary
from app.storage.base import DEFAULT_LIST_LIMIT

DEFAULT_COLLECTION = "bench_results"
SUMMARY_COLLECTION = "run_summaries"
MAX_BATCH_WRITES = 500  # Firestore limit per batched write
DESCENDING = "DESCENDING"  # == google.cloud.firestore.Query.DESCENDING

M = TypeVar("M", bound=BaseModel)


class FirestoreResultRepository:
    def __init__(
        self,
        client: Any,
        collection: str = DEFAULT_COLLECTION,
        summary_collection: str = SUMMARY_COLLECTION,
    ) -> None:
        self._client = client
        self._collection = collection
        self._summary_collection = summary_collection

    def save_results(self, results: Sequence[BenchResult]) -> None:
        self._save(self._collection, results, lambda r: (r.run_id, r.provider, r.model, r.task_id))

    def list_results(
        self, since: datetime | None = None, limit: int = DEFAULT_LIST_LIMIT
    ) -> list[BenchResult]:
        return self._list(self._collection, BenchResult, since, limit)

    def save_summaries(self, summaries: Sequence[RunSummary]) -> None:
        self._save(self._summary_collection, summaries, lambda s: (s.run_id, s.provider, s.model))

    def list_summaries(
        self, since: datetime | None = None, limit: int = DEFAULT_LIST_LIMIT
    ) -> list[RunSummary]:
        return self._list(self._summary_collection, RunSummary, since, limit)

    def _save(self, name: str, items: Sequence[BaseModel], key: Any) -> None:
        collection = self._client.collection(name)
        for start in range(0, len(items), MAX_BATCH_WRITES):
            batch = self._client.batch()
            for item in items[start : start + MAX_BATCH_WRITES]:
                batch.set(collection.document(_document_id(key(item))), _to_document(item))
            batch.commit()

    def _list(self, name: str, model: type[M], since: datetime | None, limit: int) -> list[M]:
        query = self._client.collection(name)
        if since is not None:
            query = query.where(filter=FieldFilter("timestamp", ">=", since))
        query = query.order_by("timestamp", direction=DESCENDING).limit(limit)
        return [model.model_validate(doc.to_dict()) for doc in query.stream()]


def _document_id(parts: tuple[str, ...]) -> str:
    """Deterministic and slash-free: re-saving overwrites instead of duplicating."""
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]


def _to_document(item: BaseModel) -> dict[str, Any]:
    # mode="python" keeps datetimes as datetimes (indexable timestamps); enums become values.
    data = item.model_dump()
    return {k: (v.value if hasattr(v, "value") else v) for k, v in data.items()}
