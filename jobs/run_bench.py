"""Entry point for one benchmark round (Cloud Run Job in production).

Usage: python -m jobs.run_bench
"""

import asyncio
import logging
import sys

import httpx

from app.bench.runner import run_benchmark
from app.bench.stats import ModelSummary, summarize
from app.bench.task_loader import TaskFileError, load_tasks
from app.config import Settings
from app.providers.registry import TargetConfigError, build_targets
from app.storage.base import ResultRepository
from app.storage.memory import InMemoryResultRepository

logger = logging.getLogger("jobs.run_bench")


def build_repository(settings: Settings) -> ResultRepository:
    if settings.storage_backend == "memory":
        return InMemoryResultRepository()
    raise NotImplementedError(f"storage backend {settings.storage_backend!r} not available yet")


async def run_once(settings: Settings, repository: ResultRepository) -> list[ModelSummary]:
    tasks = load_tasks(settings.tasks_path)
    # The runner enforces the per-call timeout; the client's is a slightly looser safety net.
    async with httpx.AsyncClient(timeout=settings.bench_timeout_s + 5) as client:
        targets = build_targets(settings, client)
        results = await run_benchmark(tasks, targets, timeout_s=settings.bench_timeout_s)
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
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per request is noise
    settings = Settings()
    try:
        summaries = asyncio.run(run_once(settings, build_repository(settings)))
    except (TargetConfigError, TaskFileError) as exc:
        logger.error("configuration error: %s", exc)
        return 1
    logger.info("round complete: %d model(s) measured", len(summaries))
    return 0


if __name__ == "__main__":
    sys.exit(main())
