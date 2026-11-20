"""Offline provider for tests, local runs and load generation without spending quota."""

import asyncio
import random

from app.providers.base import ProviderError, ProviderResponse

CHARS_PER_TOKEN = 2  # rough estimate for mixed Chinese/English text


class MockProvider:
    def __init__(
        self,
        name: str = "mock",
        seed: int = 0,
        latency_s: float = 0.05,
        failure_rate: float = 0.0,
    ) -> None:
        if not 0.0 <= failure_rate <= 1.0:
            raise ValueError("failure_rate must be between 0 and 1")
        if latency_s < 0:
            raise ValueError("latency_s must be non-negative")
        self.name = name
        self._latency_s = latency_s
        self._failure_rate = failure_rate
        self._rng = random.Random(seed)  # noqa: S311 - simulation, not security

    async def complete(self, model: str, prompt: str, max_tokens: int) -> ProviderResponse:
        if self._latency_s > 0:
            await asyncio.sleep(self._latency_s * (0.5 + self._rng.random()))
        if self._rng.random() < self._failure_rate:
            raise ProviderError("server", "simulated failure")

        output_tokens = self._rng.randint(1, max(1, max_tokens))
        return ProviderResponse(
            text=f"[{model}] 模擬回應",
            input_tokens=max(1, len(prompt) // CHARS_PER_TOKEN),
            output_tokens=output_tokens,
        )
