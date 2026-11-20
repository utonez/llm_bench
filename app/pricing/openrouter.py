"""Public per-token model prices from OpenRouter (no API key needed).

These are *market reference* prices: what the same model costs on a paid API.
Our free-tier calls cost $0, so this answers "what would this traffic cost in production?"
"""

from dataclasses import dataclass

import httpx

from app.pricing.errors import PricingError

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


@dataclass(frozen=True)
class Price:
    prompt_usd: float  # per input token
    completion_usd: float  # per output token


async def fetch_prices(client: httpx.AsyncClient) -> dict[str, Price]:
    try:
        response = await client.get(OPENROUTER_MODELS_URL)
        response.raise_for_status()
        models = response.json()["data"]
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise PricingError(f"OpenRouter prices unavailable: {type(exc).__name__}") from exc

    prices: dict[str, Price] = {}
    for model in models:
        price = _parse_price(model)
        if price is not None:
            prices[model["id"]] = price
    return prices


def _parse_price(model: dict) -> Price | None:
    pricing = model.get("pricing")
    if not isinstance(pricing, dict):
        return None
    try:
        prompt = float(pricing["prompt"])
        completion = float(pricing["completion"])
    except (KeyError, TypeError, ValueError):
        return None
    if prompt < 0 or completion < 0:
        return None
    return Price(prompt_usd=prompt, completion_usd=completion)
