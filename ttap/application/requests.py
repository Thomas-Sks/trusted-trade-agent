from __future__ import annotations

from collections.abc import Callable

from ttap.domain.models import Delivery, PurchaseRequest, RequestLine
from ttap.ports import Store


class RequestService:
    def __init__(self, store: Store, new_id: Callable[[str], str]):
        self._store = store
        self._new_id = new_id

    def create(self, org_id: str, lines: list[RequestLine], delivery: Delivery) -> PurchaseRequest:
        req = PurchaseRequest(request_id=self._new_id("rq"), org_id=org_id, lines=lines, delivery=delivery)
        self._store.save_request(req)
        return req
