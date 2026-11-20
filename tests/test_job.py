import httpx
import pytest
import respx

from app.config import PROJECT_ROOT, Settings
from app.pricing.fx import CBC_FX_URL
from app.pricing.openrouter import OPENROUTER_MODELS_URL
from app.storage.factory import build_repository
from app.storage.memory import InMemoryResultRepository
from jobs.run_bench import run_once

MOCK_TARGETS = PROJECT_ROOT / "config" / "targets_mock.yaml"


def offline_settings(**overrides):
    return Settings(_env_file=None, targets_path=MOCK_TARGETS, pricing_enabled=False, **overrides)


async def test_run_once_measures_every_target_and_persists_results():
    repo = InMemoryResultRepository()

    summaries = await run_once(offline_settings(), repo)

    assert {s.provider for s in summaries} == {"mock-stable", "mock-flaky"}
    assert len(repo.list_results()) == sum(s.calls for s in summaries)


async def test_run_once_saves_one_summary_per_model():
    repo = InMemoryResultRepository()

    await run_once(offline_settings(), repo)

    summaries = repo.list_summaries()
    assert {s.provider for s in summaries} == {"mock-stable", "mock-flaky"}
    assert all(s.cost_usd is None for s in summaries)  # pricing disabled


@respx.mock
async def test_run_once_prices_calls_in_twd_when_pricing_is_available(tmp_path):
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n  - {provider: mock, model: fast, name: m, latency_s: 0, price_ref: v/fast}\n",
        encoding="utf-8",
    )
    respx.get(OPENROUTER_MODELS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [{"id": "v/fast", "pricing": {"prompt": "0.001", "completion": "0.002"}}]
            },
        )
    )
    respx.get(CBC_FX_URL).mock(
        return_value=httpx.Response(200, json=[{"日期": "20261120", "NTD_USD": "32.936"}])
    )
    repo = InMemoryResultRepository()

    await run_once(Settings(_env_file=None, targets_path=targets), repo)

    [summary] = repo.list_summaries()
    assert summary.price_ref == "v/fast"
    assert summary.cost_usd and summary.cost_usd > 0
    assert summary.usd_twd == 32.936
    assert summary.fx_date == "2026-11-20"


@respx.mock
async def test_run_once_still_completes_when_pricing_sources_are_down(tmp_path):
    respx.get(OPENROUTER_MODELS_URL).mock(return_value=httpx.Response(503))
    respx.get(CBC_FX_URL).mock(side_effect=httpx.ConnectError("down"))
    repo = InMemoryResultRepository()

    await run_once(Settings(_env_file=None, targets_path=MOCK_TARGETS), repo)

    assert repo.list_results()
    assert all(s.cost_usd is None and s.usd_twd is None for s in repo.list_summaries())


def test_memory_backend_builds_in_memory_repository():
    repo = build_repository(Settings(_env_file=None, storage_backend="memory"))

    assert isinstance(repo, InMemoryResultRepository)


def test_firestore_backend_requires_project_id():
    with pytest.raises(ValueError, match="GCP_PROJECT_ID"):
        build_repository(Settings(_env_file=None, storage_backend="firestore"))
