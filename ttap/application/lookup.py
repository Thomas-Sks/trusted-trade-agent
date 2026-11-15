from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from ttap.application.auditing import Auditor
from ttap.application.errors import NotFound, UpstreamError
from ttap.domain.assurance import need_violation
from ttap.domain.errors import UpstreamUnavailable
from ttap.domain.models import CatalogProduct, Offer, RequestLine
from ttap.domain.explain import explain_offer
from ttap.domain.offer import offer_hash, offer_payload, offer_valid_until
from ttap.domain.ranking import build_offer_line
from ttap.ports import CatalogRepository, Clock, Signer, Store, SupplierGateway


class LookupService:
    def __init__(self, catalog: CatalogRepository, gateway: SupplierGateway, signer: Signer, clock: Clock,
                 store: Store, new_id: Callable[[str], str], auditor: Auditor,
                 offer_ttl: timedelta = timedelta(minutes=30), search_limit: int = 200,
                 simulated: Callable[[], list[str]] = lambda: [], usual: Callable[[str], set[str]] = lambda org: set()):
        self._catalog, self._gateway, self._signer = catalog, gateway, signer
        self._clock, self._store, self._new_id = clock, store, new_id
        self._ttl, self._limit = offer_ttl, search_limit
        self._auditor = auditor
        self._simulated = simulated
        self._usual = usual

    def _candidates(self, line: RequestLine, usual: set[str] = frozenset()) -> tuple[list[CatalogProduct], CatalogProduct | None]:
        """Explicit product -> itself + its official substitutes. Otherwise a catalogue search where hard constraints
        are applied BEFORE truncation and the buyer's usual products come first (order-guide prior)."""
        if line.need.product_id:
            requested = self._catalog.get(line.need.product_id)
            if requested is None:
                return [], None
            subs = [self._catalog.get(s) for s in requested.substitutes]
            return [requested, *[p for p in subs if p is not None]], requested
        matches = [p for p in self._catalog.search(line.need.text, limit=100_000) if need_violation(p, line.need) is None]
        matches.sort(key=lambda p: p.product_id not in usual)  # stable: keeps search relevance within each group
        return matches[: self._limit], None

    async def lookup(self, org_id: str, request_id: str) -> Offer:
        req = self._store.get_request(org_id, request_id)
        if req is None:
            raise NotFound(f"request {request_id}")
        usual = self._usual(org_id)
        per_line = {line.line_id: self._candidates(line, usual) for line in req.lines}
        ids = [p.product_id for products, _ in per_line.values() for p in products]
        try:
            prices = await self._gateway.prices(ids, req.delivery.requested_date) if ids else {}
            avail = await self._gateway.availability(ids, req.delivery.requested_date) if ids else {}
        except UpstreamUnavailable as exc:
            raise UpstreamError(str(exc)) from exc
        reserved = self._store.reserved_qty(list(avail), req.delivery.requested_date)
        avail = {pid: a.model_copy(update={"available_amount": a.available_amount - reserved[pid],
                                           "reserved": reserved[pid]})
                 if a.available_amount is not None and reserved.get(pid) else a for pid, a in avail.items()}
        now = self._clock.now()
        lines = [build_offer_line(line, per_line[line.line_id][0], prices, avail, req.delivery, now=now,
                                  requested=per_line[line.line_id][1]) for line in req.lines]
        offer = Offer(offer_id=self._new_id("of"), request_id=req.request_id, org_id=org_id, issued_at=now,
                      valid_until=offer_valid_until(now, self._ttl, lines),
                      catalog_version=self._catalog.version, lines=lines, simulated=self._simulated())
        offer.signature = self._signer.sign(offer_payload(offer))
        self._store.save_offer(offer)
        self._auditor.record(
            org_id=org_id, step="lookup", action="offer_issued", subject=f"offer/{offer.offer_id}",
            actor="system", outcome="success", explanation=explain_offer(offer),
            data={"offer_id": offer.offer_id, "offer_hash": offer_hash(offer),
                  "valid_until": offer.valid_until.isoformat(), "catalog_version": offer.catalog_version,
                  "simulated": offer.simulated,
                  "lines": [{"line_id": ln.line_id, "tiers": {t: c.product_id for t, c in ln.tiers.items()},
                             "split": [[c.product_id, str(c.qty_sales_units)] for c in ln.split],
                             "backorder_qty": str(ln.backorder_qty),
                             "excluded": [e.model_dump() for e in ln.excluded], "exceptions": ln.exceptions}
                            for ln in lines]})
        return offer
