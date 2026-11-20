from datetime import UTC, datetime

import pytest

from app.bench.models import Task, TaskCategory, TaskSource
from app.providers.base import ProviderError, ProviderResponse

FIXED_NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
TEST_SOURCE = TaskSource(
    name="test fixture",
    url="https://example.com/dataset",
    license="CC-BY-4.0",
    locator="row 1",
)


class ScriptedProvider:
    """Test double: returns canned text, or raises a scripted error."""

    def __init__(self, name: str, reply: str = "OK", error: ProviderError | None = None):
        self.name = name
        self._reply = reply
        self._error = error
        self.calls: list[tuple[str, str, int]] = []

    async def complete(self, model: str, prompt: str, max_tokens: int) -> ProviderResponse:
        self.calls.append((model, prompt, max_tokens))
        if self._error is not None:
            raise self._error
        return ProviderResponse(text=self._reply, input_tokens=10, output_tokens=5)


@pytest.fixture
def classification_task() -> Task:
    return Task(
        id="cls-01",
        category=TaskCategory.CLASSIFICATION,
        prompt="分類這則客訴",
        expected="信用卡",
        source=TEST_SOURCE,
    )


@pytest.fixture
def extraction_task() -> Task:
    return Task(
        id="ext-01",
        category=TaskCategory.EXTRACTION,
        prompt="抽取欄位",
        expected_fields={"amount": "15000", "currency": "TWD"},
        source=TEST_SOURCE,
    )


@pytest.fixture
def summary_task() -> Task:
    return Task(id="sum-01", category=TaskCategory.SUMMARY, prompt="摘要", source=TEST_SOURCE)
