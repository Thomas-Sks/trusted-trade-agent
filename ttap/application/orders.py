from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal

from ttap.application.auditing import Auditor
from ttap.application.errors import (
    IdempotencyMismatch, InvalidOfferSignature, InvalidSelection, NotFound, OfferAlreadyUsed, OfferExpired,
)
from ttap.domain.decision import build_decision_context
from ttap.domain.explain import explain_decision
from ttap.domain.models import Candidate, Offer, Order, OrderState, SelectedLine
from ttap.domain.offer import offer_hash, offer_payload, price_lock_until, resolve_selection
from ttap.ports import Clock, MandateRepository, PolicyEngine, Signer, Store

OUTCOME_TO_STATE = {"AUTO_APPROVED": OrderState.AUTO_APPROVED, "PENDING_HUMAN": OrderState.PENDING_HUMAN,
                    "DENIED": OrderState.DENIED}


class OrderService:
    def __init__(self, store: Store, signer: Signer, policy: PolicyEngine, mandates: MandateRepository,
                 clock: Clock, new_id: Callable[[str], str], auditor: Auditor):
        self._store, self._signer, self._policy = store, signer, policy
        self._mandates, self._clock, self._new_id = mandates, clock, new_id
        self._auditor = auditor

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
        try:
            return resolve_selection(offer, selected)
        except KeyError as exc:
            raise InvalidSelection(f"unknown line or tier: {exc}") from exc

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
        self._auditor.record(
            org_id=org_id, step="order", action="created", subject=f"order/{order.order_id}",
            actor=f"agent:{org_id}", outcome="success",
            explanation=f"Commande {order.order_id} à prix bloqué {order.total_net} € HT sur l'offre {offer_id}",
            data={"offer_id": offer_id, "offer_hash": order.offer_hash,
                  "selected": [s.model_dump() for s in selected], "idempotency_key": idempotency_key})
        mandate = self._mandates.get(org_id)
        decision = self._policy.decide(build_decision_context(candidates, mandate, now))
        decided = order.model_copy(update={"state": OUTCOME_TO_STATE[decision.outcome], "version": 2,
                                           "decision": decision, "decided_at": now,
                                           "lock_until": price_lock_until(
                                               now, mandate.approval_timeout if mandate else timedelta(0), candidates),
                                           "mandate_version": mandate.version if mandate else None})
        self._store.transition(org_id, order.order_id, OrderState.PENDING_DECISION, 1, decided)
        self._auditor.record(
            org_id=org_id, step="approval", action="decided", subject=f"order/{order.order_id}",
            actor="policy:cedar", outcome=decision.outcome, explanation=explain_decision(decided),
            data={"rules_fired": decision.rules_fired, "context": decided.model_dump(mode="json")["decision"]["context"],
                  "mandate_version": decided.mandate_version})
        return decided
