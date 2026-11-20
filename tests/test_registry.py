import httpx
import pytest

from app.config import Settings
from app.providers.mock import MockProvider
from app.providers.openai_compat import OpenAICompatibleProvider
from app.providers.registry import TargetConfigError, build_targets


def write_targets(tmp_path, body):
    path = tmp_path / "targets.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def settings_with(tmp_path, body, **keys):
    return Settings(_env_file=None, targets_path=write_targets(tmp_path, body), **keys)


async def test_builds_targets_for_providers_with_keys(tmp_path):
    settings = settings_with(
        tmp_path,
        "targets:\n  - {provider: groq, model: g1}\n  - {provider: gemini, model: m1}\n",
        groq_api_key="k1",
        gemini_api_key="k2",
    )

    async with httpx.AsyncClient() as client:
        targets = build_targets(settings, client)

    assert [(t.provider.name, t.model) for t in targets] == [("groq", "g1"), ("gemini", "m1")]
    assert all(isinstance(t.provider, OpenAICompatibleProvider) for t in targets)


async def test_targets_sharing_a_provider_share_one_instance(tmp_path):
    settings = settings_with(
        tmp_path,
        "targets:\n  - {provider: groq, model: a}\n  - {provider: groq, model: b}\n",
        groq_api_key="k",
    )

    async with httpx.AsyncClient() as client:
        first, second = build_targets(settings, client)

    assert first.provider is second.provider


async def test_skips_providers_without_keys(tmp_path):
    settings = settings_with(
        tmp_path,
        "targets:\n  - {provider: groq, model: g1}\n  - {provider: openrouter, model: o1}\n",
        groq_api_key="k1",
    )

    async with httpx.AsyncClient() as client:
        targets = build_targets(settings, client)

    assert [t.provider.name for t in targets] == ["groq"]


async def test_mock_targets_need_no_key(tmp_path):
    settings = settings_with(tmp_path, "targets:\n  - {provider: mock, model: fast}\n")

    async with httpx.AsyncClient() as client:
        [target] = build_targets(settings, client)

    assert isinstance(target.provider, MockProvider)


async def test_unknown_provider_is_rejected(tmp_path):
    settings = settings_with(tmp_path, "targets:\n  - {provider: acme, model: x}\n")

    async with httpx.AsyncClient() as client:
        with pytest.raises(TargetConfigError, match="acme"):
            build_targets(settings, client)


async def test_no_usable_targets_is_an_error(tmp_path):
    settings = settings_with(tmp_path, "targets:\n  - {provider: groq, model: g1}\n")

    async with httpx.AsyncClient() as client:
        with pytest.raises(TargetConfigError, match="no usable targets"):
            build_targets(settings, client)


async def test_missing_targets_file_is_an_error(tmp_path):
    settings = Settings(_env_file=None, targets_path=tmp_path / "missing.yaml")

    async with httpx.AsyncClient() as client:
        with pytest.raises(TargetConfigError, match="not found"):
            build_targets(settings, client)
