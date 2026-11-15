from __future__ import annotations

from collections.abc import Callable

from ttap.application.auditing import Auditor
from ttap.domain.formatting import when
from ttap.domain.models import Delivery, PurchaseRequest, RequestLine
from ttap.ports import Store


class RequestService:
    def __init__(self, store: Store, new_id: Callable[[str], str], auditor: Auditor):
        self._store = store
        self._new_id = new_id
        self._auditor = auditor

    def create(self, org_id: str, lines: list[RequestLine], delivery: Delivery) -> PurchaseRequest:
        req = PurchaseRequest(request_id=self._new_id("rq"), org_id=org_id, lines=lines, delivery=delivery)
        self._store.save_request(req)
        self._auditor.record(
            org_id=org_id, step="request", action="created", subject=f"request/{req.request_id}",
            actor=f"agent:{org_id}", outcome="success",
            explanation=(f"Demande {req.request_id} : {len(lines)} ligne(s), "
                         f"livraison souhaitée le {when(delivery.requested_date)}"),
            data={"request": req.model_dump(mode="json")})
        return req
