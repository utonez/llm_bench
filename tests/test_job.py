import pytest

from app.config import Settings
from app.storage.memory import InMemoryResultRepository
from jobs.run_bench import build_repository, run_once


async def test_run_once_measures_every_target_and_persists_results():
    repo = InMemoryResultRepository()

    summaries = await run_once(Settings(), repo)

    assert {s.provider for s in summaries} == {"mock-stable", "mock-flaky"}
    assert len(repo.list_results()) == sum(s.calls for s in summaries)


def test_unknown_storage_backend_is_rejected_until_implemented():
    with pytest.raises(NotImplementedError):
        build_repository(Settings(storage_backend="firestore"))
