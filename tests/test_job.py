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


def test_unknown_storage_backend_is_rejected_until_implemented():
    with pytest.raises(NotImplementedError):
        build_repository(Settings(_env_file=None, storage_backend="firestore"))
