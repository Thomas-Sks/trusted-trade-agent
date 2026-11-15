import json
from datetime import date
from decimal import Decimal

import httpx
import pytest
import respx

from ttap.adapters.outbound.valio_gateway import UpstreamUnavailable, ValioGateway

BASE = "https://valio.test"
PRICE_OK = {"customerId": "x", "currency": "EUR", "pricingDate": "2026-11-16T00:00:00+0200", "products": [
    {"productId": "1", "quantity": 1.0, "netPriceFound": True, "error": False,
     "catalogPrice": {"value": 31.31, "valueWithTax": 35.54, "validFrom": "2026-09-01T00:00:00+0300",
                      "validTo": "9999-12-31T00:00:00+0200", "currency": "EUR"},
     "comparisonPrice": {"value": 1.57, "valueWithTax": 1.78, "validFrom": "x", "validTo": "x", "currency": "EUR"},
     "comparisonUnit": "L", "tax": {"taxRate": 13.5, "taxValue": 4.23}},
    {"productId": "2", "quantity": 1.0, "netPriceFound": False, "error": True}]}
AVAIL_OK = {"timeNow": "x", "requestedDate": "x", "products": [
    {"productId": "1", "closingTime": "2026-11-12T15:00:00+0200", "salesBlock": False, "logisticModel": "Terminal",
     "scheduleLines": [{"salesBlock": False, "availableAmount": 999999.0, "availableDate": "2026-11-16", "salesUnit": "KI"}]},
    {"productId": "2", "salesBlock": False, "scheduleLines": []}]}


def make_gateway(sleeps: list[float]) -> ValioGateway:
    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
    return ValioGateway(httpx.AsyncClient(base_url=BASE), "k", sleep=fake_sleep, monotonic=lambda: 0.0)


@respx.mock
async def test_prices_parsed_and_api_key_sent():
    route = respx.post(f"{BASE}/api/price").mock(return_value=httpx.Response(200, json=PRICE_OK))
    out = await make_gateway([]).prices(["1", "2"], date(2026, 11, 16))
    assert route.calls[0].request.headers["X-API-Key"] == "k"
    assert out["1"].unit_net == Decimal("31.31") and out["1"].comparison_unit == "L"
    assert out["1"].vat_rate == Decimal("13.5")
    assert out["2"].error is True


@respx.mock
async def test_availability_parsed_empty_lines_unavailable():
    respx.post(f"{BASE}/api/availability").mock(return_value=httpx.Response(200, json=AVAIL_OK))
    out = await make_gateway([]).availability(["1", "2"], date(2026, 11, 16))
    assert out["1"].available_amount == Decimal("999999") and out["1"].logistic_model == "Terminal"
    assert out["2"].available_amount is None


@respx.mock
async def test_429_waits_30_seconds_then_retries():
    respx.post(f"{BASE}/api/price").mock(side_effect=[httpx.Response(429), httpx.Response(200, json=PRICE_OK)])
    sleeps: list[float] = []
    out = await make_gateway(sleeps).prices(["1"], date(2026, 11, 16))
    assert 30.0 in sleeps and "1" in out


@respx.mock
async def test_gives_up_after_max_attempts():
    respx.post(f"{BASE}/api/price").mock(return_value=httpx.Response(429))
    with pytest.raises(UpstreamUnavailable):
        await make_gateway([]).prices(["1"], date(2026, 11, 16))


@respx.mock
async def test_chunks_of_1000_and_dedup():
    route = respx.post(f"{BASE}/api/price").mock(
        return_value=httpx.Response(200, json={"customerId": "x", "currency": "EUR", "pricingDate": "x", "products": []}))
    ids = [str(i) for i in range(1500)] + ["1"]
    await make_gateway([]).prices(ids, date(2026, 11, 16))
    sizes = [len(json.loads(c.request.content)["products"]) for c in route.calls]
    assert sizes == [1000, 500]
