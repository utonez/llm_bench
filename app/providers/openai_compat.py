"""Adapter for any provider exposing the OpenAI-compatible Chat Completions API.

Gemini, Groq and OpenRouter all offer this interface, so one class covers them.
No automatic retries: a benchmark should record failures, not hide them.
"""

import httpx

from app.providers.base import ErrorKind, ProviderError, ProviderResponse

TEMPERATURE = 0  # deterministic-as-possible answers for comparable runs


class OpenAICompatibleProvider:
    def __init__(self, name: str, base_url: str, api_key: str, client: httpx.AsyncClient) -> None:
        self.name = name
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._client = client

    async def complete(self, model: str, prompt: str, max_tokens: int) -> ProviderResponse:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": TEMPERATURE,
        }
        body = await self._request("POST", "/chat/completions", json=payload)
        return _parse_completion(body)

    async def list_models(self) -> list[str]:
        body = await self._request("GET", "/models")
        try:
            return sorted(item["id"] for item in body["data"])
        except (KeyError, TypeError) as exc:
            raise ProviderError("bad_response", "unexpected /models payload") from exc

    async def _request(self, method: str, path: str, **kwargs: object) -> dict:
        try:
            response = await self._client.request(
                method, f"{self._base_url}{path}", headers=self._headers, **kwargs
            )
        except httpx.TimeoutException as exc:
            raise ProviderError("timeout", f"{self.name} {path}") from exc
        except httpx.TransportError as exc:
            raise ProviderError("server", f"{self.name} {path}: {type(exc).__name__}") from exc

        if response.status_code >= 400:
            # Status only: response bodies can echo request data, never log them.
            raise ProviderError(_classify(response.status_code), f"HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise ProviderError("bad_response", "response is not JSON") from exc
        if not isinstance(body, dict):
            raise ProviderError("bad_response", "response is not a JSON object")
        return body


def _classify(status: int) -> ErrorKind:
    if status in (401, 403):
        return "auth"
    if status == 429:
        return "rate_limit"
    if status >= 500:
        return "server"
    return "invalid_request"


def _parse_completion(body: dict) -> ProviderResponse:
    try:
        message = body["choices"][0]["message"]
        usage = body["usage"]
        return ProviderResponse(
            text=message.get("content") or "",
            input_tokens=int(usage["prompt_tokens"]),
            output_tokens=int(usage["completion_tokens"]),
        )
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ProviderError("bad_response", "missing choices or usage") from exc
