"""Entry point for one benchmark round (Cloud Run Job in production).

Usage: python -m jobs.run_bench
"""

import asyncio
import logging
import sys

from app.bench.runner import Target, run_benchmark
from app.bench.stats import ModelSummary, summarize
from app.bench.task_loader import load_tasks
from app.config import Settings
from app.providers.mock import MockProvider
from app.storage.base import ResultRepository
from app.storage.memory import InMemoryResultRepository

logger = logging.getLogger("jobs.run_bench")


def build_targets() -> list[Target]:
    # Real providers are added in the providers milestone; mocks keep this runnable offline.
    return [
        Target(MockProvider(name="mock-stable", seed=1, latency_s=0.02), "mock-fast"),
        Target(
            MockProvider(name="mock-flaky", seed=2, latency_s=0.05, failure_rate=0.2), "mock-slow"
        ),
    ]


def build_repository(settings: Settings) -> ResultRepository:
    if settings.storage_backend == "memory":
        return InMemoryResultRepository()
    raise NotImplementedError(f"storage backend {settings.storage_backend!r} not available yet")


async def run_once(settings: Settings, repository: ResultRepository) -> list[ModelSummary]:
    tasks = load_tasks(settings.tasks_path)
    results = await run_benchmark(tasks, build_targets(), timeout_s=settings.bench_timeout_s)
    repository.save_results(results)
    summaries = summarize(results)
    for s in summaries:
        logger.info(
            "%s/%s calls=%d success=%.0f%% p95=%s ms accuracy=%s errors=%s",
            s.provider,
            s.model,
            s.calls,
            s.success_rate * 100,
            f"{s.p95_latency_ms:.0f}" if s.p95_latency_ms is not None else "-",
            f"{s.accuracy:.0%}" if s.accuracy is not None else "-",
            s.error_counts,
        )
    return summaries


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings()
    summaries = asyncio.run(run_once(settings, build_repository(settings)))
    logger.info("round complete: %d model(s) measured", len(summaries))
    return 0


if __name__ == "__main__":
    sys.exit(main())
