from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from ttap.application.errors import (
    IdempotencyMismatch, InvalidOfferSignature, InvalidSelection, NotFound, OfferAlreadyUsed, OfferExpired,
)
from ttap.domain.decision import build_decision_context
from ttap.domain.models import Candidate, Offer, Order, OrderState, SelectedLine
from ttap.domain.offer import offer_hash, offer_payload
from ttap.ports import Clock, MandateRepository, PolicyEngine, Signer, Store

OUTCOME_TO_STATE = {"AUTO_APPROVED": OrderState.AUTO_APPROVED, "PENDING_HUMAN": OrderState.PENDING_HUMAN,
                    "DENIED": OrderState.DENIED}


class OrderService:
    def __init__(self, store: Store, signer: Signer, policy: PolicyEngine, mandates: MandateRepository,
                 clock: Clock, new_id: Callable[[str], str]):
        self._store, self._signer, self._policy = store, signer, policy
        self._mandates, self._clock, self._new_id = mandates, clock, new_id

    def get(self, org_id: str, order_id: str) -> Order:
        order = self._store.get_order(org_id, order_id)
        if order is None:
            raise NotFound(f"order {order_id}")
        return order

    def _replay(self, existing: Order, offer_id: str, selected: list[SelectedLine]) -> Order:
        if existing.offer_id != offer_id or existing.selected != selected:
            raise IdempotencyMismatch("same Idempotency-Key, different body")
        return existing

    @staticmethod
    def _resolve(offer: Offer, selected: list[SelectedLine]) -> list[Candidate]:
        lines = {line.line_id: line for line in offer.lines}
        out = []
        for sel in selected:
            line = lines.get(sel.line_id)
            if line is None or sel.tier not in line.tiers:
                raise InvalidSelection(f"{sel.line_id}/{sel.tier}")
            out.append(line.tiers[sel.tier])
        return out

    def place(self, org_id: str, offer_id: str, selected: list[SelectedLine], idempotency_key: str) -> Order:
        existing = self._store.get_order_by_idempotency_key(org_id, idempotency_key)
        if existing:
            return self._replay(existing, offer_id, selected)
        offer = self._store.get_offer(org_id, offer_id)
        if offer is None:
            raise NotFound(f"offer {offer_id}")
        if not offer.signature or not self._signer.verify(offer_payload(offer), offer.signature):
            raise InvalidOfferSignature(offer_id)
        now = self._clock.now()
        if now >= offer.valid_until:
            raise OfferExpired(offer_id)
        candidates = self._resolve(offer, selected)
        if not self._store.claim_offer(org_id, offer_id):
            existing = self._store.get_order_by_idempotency_key(org_id, idempotency_key)
            if existing:
                return self._replay(existing, offer_id, selected)
            raise OfferAlreadyUsed(offer_id)
        order = Order(order_id=self._new_id("or"), org_id=org_id, offer_id=offer_id, offer_hash=offer_hash(offer),
                      selected=selected, state=OrderState.PENDING_DECISION,
                      total_net=sum((c.line_total_net for c in candidates), Decimal("0")),
                      idempotency_key=idempotency_key)
        self._store.insert_order(order)
        decision = self._policy.decide(build_decision_context(candidates, self._mandates.get(org_id), now))
        decided = order.model_copy(update={"state": OUTCOME_TO_STATE[decision.outcome], "version": 2,
                                           "decision": decision})
        self._store.transition(org_id, order.order_id, OrderState.PENDING_DECISION, 1, decided)
        return decided
