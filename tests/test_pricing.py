from datetime import date

import httpx
import pytest
import respx

from app.pricing.cost import call_cost_usd
from app.pricing.errors import PricingError
from app.pricing.fx import CBC_FX_URL, FxRate, fetch_usd_twd
from app.pricing.openrouter import OPENROUTER_MODELS_URL, Price, fetch_prices


@respx.mock
async def test_fetch_prices_parses_per_token_usd():
    respx.get(OPENROUTER_MODELS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "a/model",
                        "pricing": {"prompt": "0.0000003", "completion": "0.0000025"},
                    },
                    {"id": "b/no-pricing"},
                    {"id": "c/bad", "pricing": {"prompt": "n/a", "completion": "1"}},
                ]
            },
        )
    )

    async with httpx.AsyncClient() as client:
        prices = await fetch_prices(client)

    assert prices == {"a/model": Price(prompt_usd=0.0000003, completion_usd=0.0000025)}


@respx.mock
async def test_fetch_prices_raises_pricing_error_on_http_failure():
    respx.get(OPENROUTER_MODELS_URL).mock(return_value=httpx.Response(503))

    async with httpx.AsyncClient() as client:
        with pytest.raises(PricingError):
            await fetch_prices(client)


@respx.mock
async def test_fetch_usd_twd_uses_latest_business_day():
    respx.get(CBC_FX_URL).mock(
        return_value=httpx.Response(
            200,
            json=[
                {"日期": "20261119", "NTD_USD": "32.942"},
                {"日期": "20261120", "NTD_USD": "32.936"},
                {"日期": "20261118", "NTD_USD": "33.001"},
            ],
        )
    )

    async with httpx.AsyncClient() as client:
        rate = await fetch_usd_twd(client)

    assert rate == FxRate(on=date(2026, 11, 20), usd_twd=32.936)


@pytest.mark.parametrize(
    "body",
    [
        [],
        [{"日期": "20261120", "NTD_USD": "-1"}],
        [{"日期": "bad", "NTD_USD": "32.9"}],
        {"unexpected": True},
    ],
)
@respx.mock
async def test_fetch_usd_twd_rejects_unusable_data(body):
    respx.get(CBC_FX_URL).mock(return_value=httpx.Response(200, json=body))

    async with httpx.AsyncClient() as client:
        with pytest.raises(PricingError):
            await fetch_usd_twd(client)


@respx.mock
async def test_fetch_usd_twd_raises_on_network_error():
    respx.get(CBC_FX_URL).mock(side_effect=httpx.ConnectError("down"))

    async with httpx.AsyncClient() as client:
        with pytest.raises(PricingError):
            await fetch_usd_twd(client)


def test_apply_costs_prices_known_models_only():
    from app.pricing.cost import apply_costs
    from tests.test_stats import make_result

    priced = make_result(model="known")
    unknown = make_result(model="other")
    prices = {"known": Price(prompt_usd=0.001, completion_usd=0.01)}

    known_out, other_out = apply_costs([priced, unknown], prices)

    assert known_out.cost_usd == pytest.approx(10 * 0.001 + 5 * 0.01)
    assert other_out.cost_usd is None
    assert priced.cost_usd is None  # inputs are not mutated


def test_call_cost_is_tokens_times_price():
    price = Price(prompt_usd=0.000001, completion_usd=0.000002)

    assert call_cost_usd(price, input_tokens=100, output_tokens=50) == pytest.approx(0.0002)
