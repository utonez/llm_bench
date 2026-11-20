from app.bench.models import BenchResult, TaskCategory
from app.bench.stats import percentile, summarize
from tests.conftest import FIXED_NOW


def make_result(provider="p", model="m", latency=100.0, success=True, correct=None):
    return BenchResult(
        run_id="r1",
        timestamp=FIXED_NOW,
        provider=provider,
        model=model,
        task_id="t",
        category=TaskCategory.CLASSIFICATION,
        latency_ms=latency,
        input_tokens=10 if success else 0,
        output_tokens=5 if success else 0,
        success=success,
        error_kind=None if success else "timeout",
        correct=correct,
    )


def test_percentile_nearest_rank():
    values = [float(v) for v in range(1, 101)]

    assert percentile(values, 95) == 95.0
    assert percentile(values, 50) == 50.0


def test_percentile_single_value():
    assert percentile([42.0], 95) == 42.0


def test_summarize_groups_by_provider_and_model():
    results = [make_result(model="a"), make_result(model="a"), make_result(model="b")]

    summaries = {s.model: s for s in summarize(results)}

    assert summaries["a"].calls == 2
    assert summaries["b"].calls == 1


def test_summarize_latency_ignores_failed_calls():
    results = [
        make_result(latency=100.0),
        make_result(latency=300.0),
        make_result(latency=9999.0, success=False),
    ]

    [summary] = summarize(results)

    assert summary.success_rate == 2 / 3
    assert summary.avg_latency_ms == 200.0
    assert summary.p95_latency_ms == 300.0
    assert summary.error_counts == {"timeout": 1}


def test_summarize_accuracy_counts_only_graded_results():
    results = [
        make_result(correct=True),
        make_result(correct=False),
        make_result(correct=None),
    ]

    [summary] = summarize(results)

    assert summary.accuracy == 0.5


def test_summarize_all_failed_has_no_latency_or_accuracy():
    [summary] = summarize([make_result(success=False)])

    assert summary.success_rate == 0.0
    assert summary.avg_latency_ms is None
    assert summary.p95_latency_ms is None
    assert summary.accuracy is None


def test_summarize_empty_input():
    assert summarize([]) == []
