from collections.abc import Mapping, Sequence

from app.bench.models import BenchResult
from app.pricing.openrouter import Price


def call_cost_usd(price: Price, input_tokens: int, output_tokens: int) -> float:
    return input_tokens * price.prompt_usd + output_tokens * price.completion_usd


def apply_costs(
    results: Sequence[BenchResult], price_by_model: Mapping[str, Price]
) -> list[BenchResult]:
    """Return copies with cost_usd set where the model has a known reference price."""
    return [
        result.model_copy(
            update={"cost_usd": call_cost_usd(price, result.input_tokens, result.output_tokens)}
        )
        if (price := price_by_model.get(result.model)) is not None
        else result
        for result in results
    ]
