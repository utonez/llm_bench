from datetime import timedelta

from app.bench.summaries import build_run_summaries
from app.storage.memory import InMemoryResultRepository
from tests.conftest import FIXED_NOW
from tests.test_stats import make_result


def make_summary(run_id, hours=0):
    result = make_result().model_copy(
        update={"run_id": run_id, "timestamp": FIXED_NOW + timedelta(hours=hours)}
    )
    [summary] = build_run_summaries([result], None, price_refs={})
    return summary


def test_summaries_round_trip_newest_first_with_since_filter():
    repo = InMemoryResultRepository()
    repo.save_summaries([make_summary("r0", 0), make_summary("r1", 6), make_summary("r2", 12)])

    recent = repo.list_summaries(since=FIXED_NOW + timedelta(hours=6))

    assert [s.run_id for s in recent] == ["r2", "r1"]


def test_saves_and_lists_newest_first():
    repo = InMemoryResultRepository()
    old = make_result(model="old").model_copy(update={"timestamp": FIXED_NOW - timedelta(hours=1)})
    new = make_result(model="new")

    repo.save_results([old, new])

    assert [r.model for r in repo.list_results()] == ["new", "old"]


def test_list_filters_by_since_and_limit():
    repo = InMemoryResultRepository()
    results = [
        make_result(model=str(i)).model_copy(update={"timestamp": FIXED_NOW + timedelta(minutes=i)})
        for i in range(5)
    ]
    repo.save_results(results)

    recent = repo.list_results(since=FIXED_NOW + timedelta(minutes=2), limit=2)

    assert [r.model for r in recent] == ["4", "3"]


def test_saved_results_are_not_affected_by_caller_mutation():
    repo = InMemoryResultRepository()
    batch = [make_result()]
    repo.save_results(batch)

    batch.clear()

    assert len(repo.list_results()) == 1
