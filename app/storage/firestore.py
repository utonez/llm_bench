"""Firestore-backed result repository (one document per measured call)."""

import hashlib
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from google.cloud.firestore_v1.base_query import FieldFilter

from app.bench.models import BenchResult
from app.storage.base import DEFAULT_LIST_LIMIT

DEFAULT_COLLECTION = "bench_results"
MAX_BATCH_WRITES = 500  # Firestore limit per batched write
DESCENDING = "DESCENDING"  # == google.cloud.firestore.Query.DESCENDING


class FirestoreResultRepository:
    def __init__(self, client: Any, collection: str = DEFAULT_COLLECTION) -> None:
        self._client = client
        self._collection = collection

    def save_results(self, results: Sequence[BenchResult]) -> None:
        collection = self._client.collection(self._collection)
        for start in range(0, len(results), MAX_BATCH_WRITES):
            batch = self._client.batch()
            for result in results[start : start + MAX_BATCH_WRITES]:
                batch.set(collection.document(_document_id(result)), _to_document(result))
            batch.commit()

    def list_results(
        self, since: datetime | None = None, limit: int = DEFAULT_LIST_LIMIT
    ) -> list[BenchResult]:
        query = self._client.collection(self._collection)
        if since is not None:
            query = query.where(filter=FieldFilter("timestamp", ">=", since))
        query = query.order_by("timestamp", direction=DESCENDING).limit(limit)
        return [BenchResult.model_validate(doc.to_dict()) for doc in query.stream()]


def _document_id(result: BenchResult) -> str:
    """Deterministic and slash-free: re-saving a result overwrites instead of duplicating."""
    key = "|".join((result.run_id, result.provider, result.model, result.task_id))
    return hashlib.sha256(key.encode()).hexdigest()[:32]


def _to_document(result: BenchResult) -> dict[str, Any]:
    data = result.model_dump()
    data["category"] = result.category.value  # plain str, not an Enum subclass
    return data
