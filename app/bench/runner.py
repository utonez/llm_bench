"""Run every task against every (provider, model) target and measure each call."""

import asyncio
import logging
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from app.bench.models import BenchResult, Task
from app.bench.scoring import score_response
from app.providers.base import Provider, ProviderError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 30.0
Clock = Callable[[], datetime]


@dataclass(frozen=True)
class Target:
    provider: Provider
    model: str


def utc_now() -> datetime:
    return datetime.now(UTC)


async def run_benchmark(
    tasks: Sequence[Task],
    targets: Sequence[Target],
    *,
    clock: Clock = utc_now,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    run_id: str | None = None,
) -> list[BenchResult]:
    """Providers run in parallel; calls to the same provider run one at a time
    so a single round stays inside free-tier rate limits."""
    run_id = run_id or uuid.uuid4().hex
    by_provider: dict[str, list[Target]] = {}
    for target in targets:
        by_provider.setdefault(target.provider.name, []).append(target)

    batches = await asyncio.gather(
        *(_run_provider(group, tasks, run_id, clock, timeout_s) for group in by_provider.values())
    )
    return [result for batch in batches for result in batch]


async def _run_provider(
    targets: list[Target], tasks: Sequence[Task], run_id: str, clock: Clock, timeout_s: float
) -> list[BenchResult]:
    return [
        await _run_one(target, task, run_id, clock, timeout_s)
        for target in targets
        for task in tasks
    ]


async def _run_one(
    target: Target, task: Task, run_id: str, clock: Clock, timeout_s: float
) -> BenchResult:
    base = {
        "run_id": run_id,
        "timestamp": clock(),
        "provider": target.provider.name,
        "model": target.model,
        "task_id": task.id,
        "category": task.category,
    }
    started = time.perf_counter()
    try:
        response = await asyncio.wait_for(
            target.provider.complete(target.model, task.prompt, task.max_tokens), timeout_s
        )
    except TimeoutError:
        return _failure(base, started, "timeout")
    except ProviderError as exc:
        logger.warning("%s/%s failed on %s: %s", base["provider"], target.model, task.id, exc)
        return _failure(base, started, exc.kind)
    except Exception:
        logger.exception(
            "unexpected error from %s/%s on %s", base["provider"], target.model, task.id
        )
        return _failure(base, started, "unexpected")

    return BenchResult(
        **base,
        latency_ms=_elapsed_ms(started),
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        success=True,
        correct=score_response(task, response.text),
    )


def _failure(base: dict, started: float, kind: str) -> BenchResult:
    return BenchResult(
        **base,
        latency_ms=_elapsed_ms(started),
        input_tokens=0,
        output_tokens=0,
        success=False,
        error_kind=kind,
    )


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000
