import pytest

from app.config import PROJECT_ROOT, Settings
from app.storage.memory import InMemoryResultRepository
from jobs.run_bench import build_repository, run_once

MOCK_TARGETS = PROJECT_ROOT / "config" / "targets_mock.yaml"


async def test_run_once_measures_every_target_and_persists_results():
    repo = InMemoryResultRepository()

    summaries = await run_once(Settings(_env_file=None, targets_path=MOCK_TARGETS), repo)

    assert {s.provider for s in summaries} == {"mock-stable", "mock-flaky"}
    assert len(repo.list_results()) == sum(s.calls for s in summaries)


def test_memory_backend_builds_in_memory_repository():
    repo = build_repository(Settings(_env_file=None, storage_backend="memory"))

    assert isinstance(repo, InMemoryResultRepository)


def test_firestore_backend_requires_project_id():
    with pytest.raises(ValueError, match="GCP_PROJECT_ID"):
        build_repository(Settings(_env_file=None, storage_backend="firestore"))
