"""NT$/USD interbank closing rate from the Central Bank of the R.O.C. (Taiwan).

Source: data.gov.tw dataset 7232, Government Open Data License v1.
Published every business day between 16:00 and 17:00 Taipei time.
"""

from dataclasses import dataclass
from datetime import date, datetime

import httpx

from app.pricing.errors import PricingError

CBC_FX_URL = "https://cpx.cbc.gov.tw/api/OpenData/FTDOpenData_Day"


@dataclass(frozen=True)
class FxRate:
    on: date
    usd_twd: float


async def fetch_usd_twd(client: httpx.AsyncClient) -> FxRate:
    try:
        response = await client.get(CBC_FX_URL)
        response.raise_for_status()
        rows = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise PricingError(f"Central Bank FX unavailable: {type(exc).__name__}") from exc

    if not isinstance(rows, list) or not rows:
        raise PricingError("Central Bank FX response has no rows")
    try:
        latest = max(rows, key=lambda row: row["日期"])
        rate = FxRate(
            on=datetime.strptime(latest["日期"], "%Y%m%d").date(),
            usd_twd=float(latest["NTD_USD"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PricingError("Central Bank FX row is malformed") from exc
    if rate.usd_twd <= 0:
        raise PricingError(f"implausible NT$/USD rate {rate.usd_twd}")
    return rate
