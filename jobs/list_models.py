"""List the model IDs each configured provider actually offers to your key.

Usage: python -m jobs.list_models [substring]
Use this to pick real model IDs for config/targets*.yaml instead of guessing.
"""

import asyncio
import logging
import sys

import httpx

from app.config import Settings
from app.providers.base import ProviderError
from app.providers.registry import build_api_providers

logger = logging.getLogger("jobs.list_models")
REQUEST_TIMEOUT_S = 30.0


async def list_all(settings: Settings, needle: str = "") -> dict[str, list[str]]:
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S) as client:
        providers = build_api_providers(settings, client)
        if not providers:
            logger.error("no API keys configured - add them to .env (see .env.example)")
        found: dict[str, list[str]] = {}
        for provider in providers:
            try:
                models = await provider.list_models()
            except ProviderError as exc:
                logger.error("%s: could not list models (%s)", provider.name, exc.kind)
                continue
            found[provider.name] = [m for m in models if needle.lower() in m.lower()]
        return found


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    needle = sys.argv[1] if len(sys.argv) > 1 else ""
    for provider, models in asyncio.run(list_all(Settings(), needle)).items():
        logger.info("%s: %d model(s)", provider, len(models))
        for model in models:
            logger.info("  %s", model)
    return 0


if __name__ == "__main__":
    sys.exit(main())
