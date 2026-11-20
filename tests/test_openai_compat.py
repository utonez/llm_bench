import json

import httpx
import pytest
import respx

from app.providers.base import ProviderError
from app.providers.openai_compat import OpenAICompatibleProvider

BASE_URL = "https://llm.example.com/v1"
API_KEY = "sk-test-secret-123"


def ok_body(content="信用卡", prompt_tokens=12, completion_tokens=3):
    return {
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    }


@pytest.fixture
async def provider():
    async with httpx.AsyncClient() as client:
        yield OpenAICompatibleProvider("groq", BASE_URL, API_KEY, client)


@respx.mock
async def test_complete_parses_text_and_usage(provider):
    route = respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, json=ok_body())
    )

    response = await provider.complete("model-a", "分類這題", max_tokens=16)

    assert response.text == "信用卡"
    assert response.input_tokens == 12
    assert response.output_tokens == 3
    sent = json.loads(route.calls.last.request.content)
    assert sent["model"] == "model-a"
    assert sent["max_tokens"] == 16
    assert sent["temperature"] == 0
    assert sent["messages"] == [{"role": "user", "content": "分類這題"}]
    assert route.calls.last.request.headers["Authorization"] == f"Bearer {API_KEY}"


@respx.mock
async def test_null_content_becomes_empty_text(provider):
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, json=ok_body(content=None))
    )

    response = await provider.complete("m", "p", max_tokens=8)

    assert response.text == ""


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (401, "auth"),
        (403, "auth"),
        (429, "rate_limit"),
        (500, "server"),
        (503, "server"),
        (400, "invalid_request"),
        (404, "invalid_request"),
    ],
)
@respx.mock
async def test_http_errors_are_classified(provider, status, kind):
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(status, json={"error": {"message": "nope"}})
    )

    with pytest.raises(ProviderError) as exc_info:
        await provider.complete("m", "p", max_tokens=8)

    assert exc_info.value.kind == kind


@respx.mock
async def test_network_timeout_is_classified_as_timeout(provider):
    respx.post(f"{BASE_URL}/chat/completions").mock(side_effect=httpx.ReadTimeout("slow"))

    with pytest.raises(ProviderError) as exc_info:
        await provider.complete("m", "p", max_tokens=8)

    assert exc_info.value.kind == "timeout"


@respx.mock
async def test_connection_failure_is_classified_as_server(provider):
    respx.post(f"{BASE_URL}/chat/completions").mock(side_effect=httpx.ConnectError("down"))

    with pytest.raises(ProviderError) as exc_info:
        await provider.complete("m", "p", max_tokens=8)

    assert exc_info.value.kind == "server"


@pytest.mark.parametrize(
    "body",
    [
        {"choices": []},
        {"choices": [{"message": {"content": "x"}}]},  # no usage
        {"unexpected": True},
    ],
)
@respx.mock
async def test_malformed_response_is_bad_response(provider, body):
    respx.post(f"{BASE_URL}/chat/completions").mock(return_value=httpx.Response(200, json=body))

    with pytest.raises(ProviderError) as exc_info:
        await provider.complete("m", "p", max_tokens=8)

    assert exc_info.value.kind == "bad_response"


@respx.mock
async def test_non_json_response_is_bad_response(provider):
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, text="<html>oops</html>")
    )

    with pytest.raises(ProviderError) as exc_info:
        await provider.complete("m", "p", max_tokens=8)

    assert exc_info.value.kind == "bad_response"


@respx.mock
async def test_api_key_never_appears_in_error_message(provider):
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(401, text=f"invalid key {API_KEY}")
    )

    with pytest.raises(ProviderError) as exc_info:
        await provider.complete("m", "p", max_tokens=8)

    assert API_KEY not in str(exc_info.value)


@respx.mock
async def test_list_models_returns_sorted_ids(provider):
    respx.get(f"{BASE_URL}/models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "b-model"}, {"id": "a-model"}]})
    )

    assert await provider.list_models() == ["a-model", "b-model"]
