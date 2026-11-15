from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from ttap.application.errors import NotFound, UpstreamError
from ttap.domain.errors import UpstreamUnavailable
from ttap.domain.models import CatalogProduct, Offer, RequestLine
from ttap.domain.offer import offer_payload, offer_valid_until
from ttap.domain.ranking import build_offer_line
from ttap.ports import CatalogRepository, Clock, Signer, Store, SupplierGateway


class LookupService:
    def __init__(self, catalog: CatalogRepository, gateway: SupplierGateway, signer: Signer, clock: Clock,
                 store: Store, new_id: Callable[[str], str], offer_ttl: timedelta = timedelta(minutes=30),
                 search_limit: int = 60):
        self._catalog, self._gateway, self._signer = catalog, gateway, signer
        self._clock, self._store, self._new_id = clock, store, new_id
        self._ttl, self._limit = offer_ttl, search_limit

    def _candidates(self, line: RequestLine) -> list[CatalogProduct]:
        if line.need.product_id:
            p = self._catalog.get(line.need.product_id)
            return [p] if p else []
        return self._catalog.search(line.need.text, limit=self._limit)

    async def lookup(self, org_id: str, request_id: str) -> Offer:
        req = self._store.get_request(org_id, request_id)
        if req is None:
            raise NotFound(f"request {request_id}")
        per_line = {line.line_id: self._candidates(line) for line in req.lines}
        ids = [p.product_id for products in per_line.values() for p in products]
        try:
            prices = await self._gateway.prices(ids, req.delivery.requested_date) if ids else {}
            avail = await self._gateway.availability(ids, req.delivery.requested_date) if ids else {}
        except UpstreamUnavailable as exc:
            raise UpstreamError(str(exc)) from exc
        lines = [build_offer_line(line, per_line[line.line_id], prices, avail, req.delivery) for line in req.lines]
        now = self._clock.now()
        offer = Offer(offer_id=self._new_id("of"), request_id=req.request_id, org_id=org_id, issued_at=now,
                      valid_until=offer_valid_until(now, self._ttl, lines),
                      catalog_version=self._catalog.version, lines=lines)
        offer.signature = self._signer.sign(offer_payload(offer))
        self._store.save_offer(offer)
        return offer
