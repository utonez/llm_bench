"""Build the repository selected by settings (shared by the job and the API)."""

from app.config import Settings
from app.storage.base import ResultRepository
from app.storage.firestore import FirestoreResultRepository
from app.storage.memory import InMemoryResultRepository


def build_repository(settings: Settings) -> ResultRepository:
    if settings.storage_backend == "memory":
        return InMemoryResultRepository()
    if not settings.gcp_project_id:
        raise ValueError("STORAGE_BACKEND=firestore needs GCP_PROJECT_ID")
    from google.cloud import firestore  # imported lazily: only needed in the cloud

    return FirestoreResultRepository(firestore.Client(project=settings.gcp_project_id))
