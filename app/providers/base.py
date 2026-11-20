"""Common contract every LLM provider adapter implements."""

from dataclasses import dataclass
from typing import Literal, Protocol

ErrorKind = Literal[
    "timeout", "rate_limit", "auth", "invalid_request", "server", "bad_response", "unexpected"
]


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    input_tokens: int
    output_tokens: int


class ProviderError(Exception):
    """A classified provider failure. `kind` is what gets stored and charted."""

    def __init__(self, kind: ErrorKind, message: str = "") -> None:
        super().__init__(f"{kind}: {message}" if message else kind)
        self.kind: ErrorKind = kind


class Provider(Protocol):
    name: str

    async def complete(self, model: str, prompt: str, max_tokens: int) -> ProviderResponse: ...
