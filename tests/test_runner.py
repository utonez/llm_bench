import asyncio

from app.bench.runner import Target, run_benchmark
from app.providers.base import ProviderError
from tests.conftest import FIXED_NOW, ScriptedProvider


def clock():
    return FIXED_NOW


async def test_runs_every_task_against_every_target(classification_task, summary_task):
    provider = ScriptedProvider("p", reply="信用卡")
    targets = [Target(provider, "m1"), Target(provider, "m2")]

    results = await run_benchmark([classification_task, summary_task], targets, clock=clock)

    assert len(results) == 4
    assert {(r.model, r.task_id) for r in results} == {
        ("m1", "cls-01"),
        ("m1", "sum-01"),
        ("m2", "cls-01"),
        ("m2", "sum-01"),
    }


async def test_records_tokens_score_and_timestamp(classification_task):
    provider = ScriptedProvider("p", reply="信用卡")

    [result] = await run_benchmark([classification_task], [Target(provider, "m")], clock=clock)

    assert result.success is True
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert result.correct is True
    assert result.timestamp == FIXED_NOW
    assert result.latency_ms >= 0


async def test_provider_error_is_recorded_not_raised(classification_task):
    failing = ScriptedProvider("bad", error=ProviderError("rate_limit", "429"))
    healthy = ScriptedProvider("good", reply="信用卡")

    results = await run_benchmark(
        [classification_task], [Target(failing, "m"), Target(healthy, "m")], clock=clock
    )

    by_provider = {r.provider: r for r in results}
    assert by_provider["bad"].success is False
    assert by_provider["bad"].error_kind == "rate_limit"
    assert by_provider["bad"].correct is None
    assert by_provider["good"].success is True


async def test_unexpected_exception_is_recorded_as_unexpected(classification_task):
    class Exploding(ScriptedProvider):
        async def complete(self, model, prompt, max_tokens):
            raise ValueError("boom")

    [result] = await run_benchmark(
        [classification_task], [Target(Exploding("x"), "m")], clock=clock
    )

    assert result.success is False
    assert result.error_kind == "unexpected"


async def test_slow_call_times_out(classification_task):
    class Slow(ScriptedProvider):
        async def complete(self, model, prompt, max_tokens):
            await asyncio.sleep(1)

    [result] = await run_benchmark(
        [classification_task], [Target(Slow("s"), "m")], clock=clock, timeout_s=0.01
    )

    assert result.success is False
    assert result.error_kind == "timeout"


async def test_min_output_tokens_raises_budget_for_reasoning_models(classification_task):
    provider = ScriptedProvider("p")

    await run_benchmark(
        [classification_task], [Target(provider, "reasoner", min_output_tokens=256)], clock=clock
    )

    assert provider.calls[0][2] == 256


async def test_task_budget_is_kept_when_above_target_minimum(classification_task):
    provider = ScriptedProvider("p")

    await run_benchmark([classification_task], [Target(provider, "m", min_output_tokens=8)])

    assert provider.calls[0][2] == classification_task.max_tokens


async def test_calls_to_one_provider_are_spaced_by_min_interval(classification_task, summary_task):
    provider = ScriptedProvider("p")
    targets = [Target(provider, "m1", min_interval_s=0.05), Target(provider, "m2")]

    await run_benchmark([classification_task, summary_task], targets)

    gaps = [b - a for a, b in zip(provider.call_times, provider.call_times[1:], strict=False)]
    assert len(gaps) == 3
    assert all(gap >= 0.045 for gap in gaps)  # small tolerance for timer resolution


async def test_different_providers_are_not_slowed_by_each_other(classification_task):
    slow = ScriptedProvider("slow")
    fast = ScriptedProvider("fast")

    started = asyncio.get_running_loop().time()
    await run_benchmark(
        [classification_task] * 3,
        [Target(slow, "m", min_interval_s=0.1), Target(fast, "m")],
    )

    fast_span = fast.call_times[-1] - fast.call_times[0]
    assert fast_span < 0.05
    assert asyncio.get_running_loop().time() - started >= 0.19


async def test_all_results_share_one_run_id(classification_task, summary_task):
    provider = ScriptedProvider("p")

    results = await run_benchmark([classification_task, summary_task], [Target(provider, "m")])

    assert len({r.run_id for r in results}) == 1
