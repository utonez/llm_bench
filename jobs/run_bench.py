"""Entry point for one benchmark round (Cloud Run Job in production).

Usage: python -m jobs.run_bench
"""

import asyncio
import logging
import sys

import httpx

from app.bench.runner import Target, run_benchmark
from app.bench.stats import ModelSummary, summarize
from app.bench.summaries import build_run_summaries
from app.bench.task_loader import TaskFileError, load_tasks
from app.config import Settings
from app.pricing.cost import apply_costs
from app.pricing.errors import PricingError
from app.pricing.fx import FxRate, fetch_usd_twd
from app.pricing.openrouter import Price, fetch_prices
from app.providers.registry import TargetConfigError, build_targets
from app.storage.base import ResultRepository
from app.storage.factory import build_repository

logger = logging.getLogger("jobs.run_bench")


async def load_pricing(
    client: httpx.AsyncClient, targets: list[Target]
) -> tuple[dict[str, Price], FxRate | None]:
    """Reference prices by model and today's FX. Failures only cost us the cost columns."""
    prices: dict[str, Price] = {}
    fx: FxRate | None = None
    try:
        catalog = await fetch_prices(client)
        prices = {t.model: catalog[t.price_ref] for t in targets if t.price_ref in catalog}
        missing = sorted({t.price_ref for t in targets if t.price_ref} - catalog.keys())
        if missing:
            logger.warning("no OpenRouter price for %s", missing)
    except PricingError as exc:
        logger.warning("pricing skipped: %s", exc)
    try:
        fx = await fetch_usd_twd(client)
    except PricingError as exc:
        logger.warning("FX skipped: %s", exc)
    return prices, fx


async def run_once(settings: Settings, repository: ResultRepository) -> list[ModelSummary]:
    tasks = load_tasks(settings.tasks_path)
    # The runner enforces the per-call timeout; the client's is a slightly looser safety net.
    async with httpx.AsyncClient(timeout=settings.bench_timeout_s + 5) as client:
        targets = build_targets(settings, client)
        prices, fx = await load_pricing(client, targets) if settings.pricing_enabled else ({}, None)
        results = await run_benchmark(tasks, targets, timeout_s=settings.bench_timeout_s)
    results = apply_costs(results, prices)
    repository.save_results(results)
    price_refs = {t.model: t.price_ref for t in targets if t.price_ref}
    repository.save_summaries(build_run_summaries(results, fx, price_refs))
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
