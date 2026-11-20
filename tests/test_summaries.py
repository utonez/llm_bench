from datetime import date, timedelta

import pytest

from app.bench.summaries import aggregate_summaries, build_run_summaries
from app.pricing.fx import FxRate
from tests.conftest import FIXED_NOW
from tests.test_stats import make_result

FX = FxRate(on=date(2026, 11, 20), usd_twd=32.0)


def with_cost(result, cost):
    return result.model_copy(update={"cost_usd": cost})


def test_build_groups_one_summary_per_model_per_run():
    results = [make_result(model="a"), make_result(model="a"), make_result(model="b")]

    summaries = build_run_summaries(results, FX, price_refs={"a": "or/a"})

    by_model = {s.model: s for s in summaries}
    assert by_model["a"].calls == 2
    assert by_model["a"].price_ref == "or/a"
    assert by_model["b"].price_ref is None


def test_build_keeps_successful_latencies_and_counts():
    results = [
        make_result(latency=100.0, correct=True),
        make_result(latency=300.0, correct=False),
        make_result(latency=999.0, success=False),
    ]

    [summary] = build_run_summaries(results, FX, price_refs={})

    assert summary.latencies_ms == [100.0, 300.0]
    assert summary.successes == 2
    assert summary.graded == 2
    assert summary.correct == 1
    assert summary.error_counts == {"timeout": 1}
    assert summary.input_tokens == 20
    assert summary.output_tokens == 10
    assert summary.usd_twd == 32.0
    assert summary.fx_date == "2026-11-20"


def test_build_sums_known_costs_and_marks_unknown_as_none():
    priced = [with_cost(make_result(), 0.001), with_cost(make_result(), 0.002)]
    unpriced = [make_result(model="x")]

    by_model = {s.model: s for s in build_run_summaries(priced + unpriced, None, price_refs={})}

    assert by_model["m"].cost_usd == pytest.approx(0.003)
    assert by_model["m"].usd_twd is None
    assert by_model["x"].cost_usd is None


def test_aggregate_computes_p95_across_runs_and_twd_costs():
    run1 = build_run_summaries(
        [with_cost(make_result(latency=float(v), correct=True), 0.001) for v in range(1, 51)],
        FX,
        price_refs={},
    )
    run2 = build_run_summaries(
        [
            with_cost(
                make_result(latency=float(v), correct=False).model_copy(
                    update={"run_id": "r2", "timestamp": FIXED_NOW + timedelta(hours=6)}
                ),
                0.001,
            )
            for v in range(51, 101)
        ],
        FX,
        price_refs={},
    )

    [stats] = aggregate_summaries(run1 + run2)

    assert stats.runs == 2
    assert stats.calls == 100
    assert stats.p95_latency_ms == 95.0
    assert stats.accuracy == 0.5
    assert stats.cost_twd_per_call == pytest.approx(0.032)
    assert stats.cost_twd_per_1k_calls == pytest.approx(32.0)
    assert stats.cost_twd_per_correct == pytest.approx(0.064)
    assert stats.last_run_at == FIXED_NOW + timedelta(hours=6)


def test_aggregate_without_costs_leaves_cost_fields_empty():
    [stats] = aggregate_summaries(build_run_summaries([make_result()], None, price_refs={}))

    assert stats.cost_twd_per_call is None
    assert stats.cost_twd_per_correct is None


def test_aggregate_all_failed_has_no_latency():
    [stats] = aggregate_summaries(
        build_run_summaries([make_result(success=False)], FX, price_refs={})
    )

    assert stats.success_rate == 0.0
    assert stats.p95_latency_ms is None


def test_aggregate_empty():
    assert aggregate_summaries([]) == []
