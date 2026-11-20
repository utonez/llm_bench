import pytest

from app.providers.base import ProviderError
from app.providers.mock import MockProvider


async def test_mock_returns_text_and_estimated_tokens():
    provider = MockProvider(seed=1, latency_s=0)

    response = await provider.complete("mock-fast", "請摘要這段文字" * 4, max_tokens=50)

    assert response.text
    assert response.input_tokens > 0
    assert 0 < response.output_tokens <= 50


async def test_mock_failure_rate_one_always_fails():
    provider = MockProvider(seed=1, latency_s=0, failure_rate=1.0)

    with pytest.raises(ProviderError) as exc_info:
        await provider.complete("mock-fast", "x", max_tokens=10)

    assert exc_info.value.kind == "server"


async def test_mock_is_deterministic_for_same_seed():
    first = await MockProvider(seed=7, latency_s=0).complete("m", "p", 20)
    second = await MockProvider(seed=7, latency_s=0).complete("m", "p", 20)

    assert first == second


def test_mock_rejects_invalid_failure_rate():
    with pytest.raises(ValueError):
        MockProvider(failure_rate=1.5)
