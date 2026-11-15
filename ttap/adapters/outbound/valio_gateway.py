from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from datetime import date
from decimal import Decimal

import httpx

from ttap.domain.errors import UpstreamUnavailable
from ttap.domain.models import UpstreamAvailability, UpstreamPrice

__all__ = ["ValioGateway", "UpstreamUnavailable"]

MAX_IDS_PER_CALL = 1000
UPSTREAM_CUSTOMER = "ttap-gateway"


def _dec(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _chunks(ids: list[str]) -> Iterator[list[str]]:
    unique = list(dict.fromkeys(ids))
    for i in range(0, len(unique), MAX_IDS_PER_CALL):
        yield unique[i:i + MAX_IDS_PER_CALL]


def _parse_price(p: dict) -> UpstreamPrice:
    if p.get("error"):
        return UpstreamPrice(product_id=p["productId"], error=True)
    cat = p.get("catalogPrice") or {}
    cmp_ = p.get("comparisonPrice") or {}
    tax = p.get("tax") or {}
    lst = p.get("listPrice") or {}
    return UpstreamPrice(
        product_id=p["productId"], error=False, unit_net=_dec(cat.get("value")), vat_rate=_dec(tax.get("taxRate")),
        comparison_net=_dec(cmp_.get("value")), comparison_unit=p.get("comparisonUnit"),
        list_net=_dec(lst.get("value")), valid_to=cat.get("validTo"), net_price_found=bool(p.get("netPriceFound")),
    )


def _parse_availability(p: dict) -> UpstreamAvailability:
    lines = p.get("scheduleLines") or []
    line = lines[0] if lines else {}
    return UpstreamAvailability(
        product_id=p["productId"],
        sales_block=bool(p.get("salesBlock")) or bool(line.get("salesBlock")),
        logistic_model=p.get("logisticModel"),
        available_amount=_dec(line.get("availableAmount")),
        available_date=line.get("availableDate"),
        sales_unit=line.get("salesUnit"),
        closing_time=p.get("closingTime"),
    )


class ValioGateway:
    def __init__(self, client: httpx.AsyncClient, api_key: str, *, min_interval: float = 0.125,
                 retry_after_429: float = 30.0, max_attempts: int = 3,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 monotonic: Callable[[], float] | None = None):
        self._client = client
        self._api_key = api_key
        self._min_interval = min_interval
        self._retry_after_429 = retry_after_429
        self._max_attempts = max_attempts
        self._sleep = sleep
        self._monotonic = monotonic or (lambda: asyncio.get_running_loop().time())
        self._lock = asyncio.Lock()
        self._last_call: float | None = None

    async def _post(self, path: str, ids: list[str], delivery: date) -> dict:
        body = {"customer": UPSTREAM_CUSTOMER, "requestedDate": delivery.isoformat(), "products": ids}
        async with self._lock:  # upstream blocks the whole key on 429: serialise everything
            for _ in range(self._max_attempts):
                if self._last_call is not None:
                    wait = self._min_interval - (self._monotonic() - self._last_call)
                    if wait > 0:
                        await self._sleep(wait)
                self._last_call = self._monotonic()
                try:
                    resp = await self._client.post(path, json=body, headers={"X-API-Key": self._api_key})
                except httpx.HTTPError as exc:
                    raise UpstreamUnavailable(str(exc)) from exc
                if resp.status_code == 429:
                    await self._sleep(self._retry_after_429)
                    continue
                if resp.status_code >= 500:
                    await self._sleep(1.0)
                    continue
                resp.raise_for_status()
                return resp.json()
        raise UpstreamUnavailable(f"{path}: retries exhausted")

    async def prices(self, product_ids: list[str], delivery: date) -> dict[str, UpstreamPrice]:
        out: dict[str, UpstreamPrice] = {}
        for chunk in _chunks(product_ids):
            data = await self._post("/api/price", chunk, delivery)
            out.update({p["productId"]: _parse_price(p) for p in data["products"]})
        return out

    async def availability(self, product_ids: list[str], delivery: date) -> dict[str, UpstreamAvailability]:
        out: dict[str, UpstreamAvailability] = {}
        for chunk in _chunks(product_ids):
            data = await self._post("/api/availability", chunk, delivery)
            out.update({p["productId"]: _parse_availability(p) for p in data["products"]})
        return out
