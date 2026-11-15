"""Short-lived cache in front of the supplier: fewer upstream calls, and a STALE fallback during outages."""
from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date

from ttap.domain.errors import UpstreamUnavailable
from ttap.domain.models import UpstreamAvailability, UpstreamPrice
from ttap.ports import SupplierGateway


class CachingGateway:
    def __init__(self, inner: SupplierGateway, availability_ttl: float = 60.0, price_ttl: float = 600.0,
                 monotonic: Callable[[], float] = time.monotonic):
        self._inner, self._now = inner, monotonic
        self._ttl = {"price": price_ttl, "availability": availability_ttl}
        self._cache: dict[tuple[str, str, date], tuple[float, object]] = {}
        self.stale_served: set[str] = set()

    async def _get(self, kind: str, ids: list[str], delivery: date, fetch) -> dict:
        now = self._now()
        fresh = {pid: v for pid in ids if (hit := self._cache.get((kind, pid, delivery)))
                 and now - hit[0] < self._ttl[kind] for v in [hit[1]]}
        missing = [pid for pid in ids if pid not in fresh]
        if not missing:
            return fresh
        try:
            got = await fetch(missing, delivery)
        except UpstreamUnavailable:
            stale = {pid: self._cache[(kind, pid, delivery)][1].model_copy(update={"stale": True})
                     for pid in missing if (kind, pid, delivery) in self._cache}
            if len(stale) < len(missing):
                raise
            self.stale_served.update(stale)
            return fresh | stale
        for pid, value in got.items():
            self._cache[(kind, pid, delivery)] = (now, value)
        return fresh | got

    def clear(self) -> None:
        self._cache.clear()

    async def prices(self, product_ids: list[str], delivery: date) -> dict[str, UpstreamPrice]:
        return await self._get("price", product_ids, delivery, self._inner.prices)

    async def availability(self, product_ids: list[str], delivery: date) -> dict[str, UpstreamAvailability]:
        out = await self._get("availability", product_ids, delivery, self._inner.availability)
        return out
