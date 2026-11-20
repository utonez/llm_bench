"""Domain models: benchmark tasks and per-call results."""

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_MAX_TOKENS = 256


class TaskCategory(StrEnum):
    CLASSIFICATION = "classification"  # graded: exact label
    EXTRACTION = "extraction"  # graded: JSON fields
    SUMMARY = "summary"  # measured only
    EXPLANATION = "explanation"  # measured only


class TaskSource(BaseModel):
    """Where a task's text and answer come from. Required: no invented tasks."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    url: str = Field(pattern=r"^https://")
    license: str = Field(min_length=1)
    locator: str = Field(min_length=1)  # row / line / section inside the source
    retrieved: str | None = None  # YYYY-MM-DD


class Task(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    category: TaskCategory
    prompt: str = Field(min_length=1)
    source: TaskSource
    expected: str | None = None
    expected_fields: dict[str, str] | None = None
    max_tokens: int = Field(default=DEFAULT_MAX_TOKENS, gt=0, le=4096)

    @model_validator(mode="after")
    def _graded_tasks_need_answers(self) -> Self:
        if self.category is TaskCategory.CLASSIFICATION and not self.expected:
            raise ValueError(f"classification task {self.id!r} needs 'expected'")
        if self.category is TaskCategory.EXTRACTION and not self.expected_fields:
            raise ValueError(f"extraction task {self.id!r} needs 'expected_fields'")
        return self


class BenchResult(BaseModel):
    """One measured call: (provider, model, task) at a point in time."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    timestamp: datetime
    provider: str
    model: str
    task_id: str
    category: TaskCategory
    latency_ms: float = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    success: bool
    error_kind: str | None = None
    correct: bool | None = None  # None = failed call or ungraded category
    cost_usd: float | None = Field(default=None, ge=0)  # None = no reference price known
