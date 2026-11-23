from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_repository, get_stats_service
from app.api.main import create_app
from app.api.service import StatsService
from app.bench.summaries import build_run_summaries
from app.config import Settings
from app.pricing.fx import FxRate
from app.storage.memory import InMemoryResultRepository
from tests.conftest import FIXED_NOW
from tests.test_stats import make_result

FX = FxRate(on=FIXED_NOW.date(), usd_twd=32.0)
ORIGIN = "https://dashboard.example.com"


def seeded_repo() -> InMemoryResultRepository:
    repo = InMemoryResultRepository()
    for hours, model in ((0, "fast"), (6, "fast"), (6, "slow"), (24 * 40, "fast")):
        results = [
            make_result(model=model, latency=100.0 + i, correct=i % 2 == 0).model_copy(
                update={
                    "run_id": f"r{hours}",
                    "timestamp": FIXED_NOW - timedelta(hours=hours),
                    "cost_usd": 0.001,
                }
            )
            for i in range(4)
        ]
        repo.save_summaries(build_run_summaries(results, FX, price_refs={model: f"v/{model}"}))
    return repo


class CountingRepo(InMemoryResultRepository):
    def __init__(self, inner):
        super().__init__()
        self._inner = inner
        self.reads = 0

    def list_summaries(self, since=None, limit=1000):
        self.reads += 1
        return self._inner.list_summaries(since, limit)


@pytest.fixture
def repo():
    return CountingRepo(seeded_repo())


@pytest.fixture
async def client(repo):
    settings = Settings(_env_file=None, allowed_origins=[ORIGIN], api_rate_limit_per_minute=1000)
    app = create_app(settings)
    service = StatsService(repo, clock=lambda: FIXED_NOW, cache_ttl_s=300)
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_stats_service] = lambda: service
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def test_health_is_ok(client):
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_stats_returns_envelope_with_window(client):
    response = await client.get("/v1/stats", params={"days": 7})

    body = response.json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["error"] is None
    assert body["meta"]["days"] == 7
    stats = {s["model"]: s for s in body["data"]}
    assert stats["fast"]["runs"] == 2  # the 40-day-old run is outside the window
    assert stats["fast"]["calls"] == 8
    assert stats["fast"]["accuracy"] == 0.5
    assert stats["fast"]["cost_twd_per_call"] == pytest.approx(0.032)
    assert stats["slow"]["runs"] == 1


async def test_timeseries_has_one_point_per_run_oldest_first(client):
    response = await client.get("/v1/timeseries", params={"days": 7, "model": "fast"})

    [series] = response.json()["data"]
    assert series["model"] == "fast"
    timestamps = [p["timestamp"] for p in series["points"]]
    assert len(timestamps) == 2
    assert timestamps == sorted(timestamps)


async def test_models_lists_each_model_with_price_ref(client):
    response = await client.get("/v1/models")

    models = {m["model"]: m for m in response.json()["data"]}
    assert models["fast"]["price_ref"] == "v/fast"
    assert set(models) == {"fast", "slow"}


@pytest.mark.parametrize(
    "params",
    [{"days": 0}, {"days": 31}, {"days": "abc"}, {"model": "x" * 101}, {"model": "bad model!"}],
)
async def test_invalid_query_parameters_are_rejected(client, params):
    response = await client.get("/v1/timeseries", params=params)

    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None


async def test_repeated_requests_are_served_from_cache(client, repo):
    for _ in range(5):
        await client.get("/v1/stats", params={"days": 7})

    assert repo.reads == 1


async def test_unknown_route_uses_error_envelope(client):
    response = await client.get("/v1/nope")

    assert response.status_code == 404
    assert response.json()["success"] is False


async def test_cors_allows_only_configured_origin(client):
    allowed = await client.get("/health", headers={"Origin": ORIGIN})
    denied = await client.get("/health", headers={"Origin": "https://evil.example"})

    assert allowed.headers["access-control-allow-origin"] == ORIGIN
    assert "access-control-allow-origin" not in denied.headers


async def test_only_get_is_allowed(client):
    response = await client.post("/v1/stats")

    assert response.status_code == 405


async def test_security_headers_are_set(client):
    response = await client.get("/health")

    assert response.headers["x-content-type-options"] == "nosniff"


async def test_dashboard_is_served_at_root_with_strict_csp(client):
    response = await client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "LLM 選型評測" in response.text
    csp = response.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "unsafe-inline" not in csp
    assert "frame-ancestors 'none'" in csp
    assert response.headers["cache-control"] == "no-cache"


async def test_dashboard_assets_are_served(client):
    script = await client.get("/app.js")
    chart = await client.get("/vendor/chartjs-4.6.1/chart.umd.min.js")

    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]
    assert chart.status_code == 200


async def test_api_docs_keep_working_without_the_strict_policy(client):
    response = await client.get("/docs")

    assert response.status_code == 200
    assert "content-security-policy" not in response.headers


async def test_static_files_cannot_escape_the_frontend_folder(client):
    for path in ("/../app/config.py", "/%2e%2e/app/config.py", "/..%2Fpyproject.toml"):
        response = await client.get(path)
        assert response.status_code == 404, path
        assert "storage_backend" not in response.text


async def test_hsts_and_permissions_policy_are_set(client):
    response = await client.get("/")

    assert "max-age=" in response.headers["strict-transport-security"]
    assert "camera=()" in response.headers["permissions-policy"]


async def test_internal_errors_do_not_leak_details(repo):
    class BrokenRepo(InMemoryResultRepository):
        def list_summaries(self, since=None, limit=1000):
            raise RuntimeError("firestore credentials at /secret/path")

    app = create_app(Settings(_env_file=None, api_rate_limit_per_minute=1000))
    broken = StatsService(BrokenRepo(), clock=lambda: FIXED_NOW)
    app.dependency_overrides[get_stats_service] = lambda: broken
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/stats")

    assert response.status_code == 500
    assert "secret" not in response.text
    assert response.json() == {
        "success": False,
        "data": None,
        "error": "internal error",
        "meta": None,
    }


async def test_rate_limit_returns_429(repo):
    app = create_app(Settings(_env_file=None, api_rate_limit_per_minute=3))
    service = StatsService(repo, clock=lambda: FIXED_NOW)
    app.dependency_overrides[get_stats_service] = lambda: service
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        statuses = [(await ac.get("/v1/models")).status_code for _ in range(5)]

    assert statuses[:3] == [200, 200, 200]
    assert statuses[3:] == [429, 429]
