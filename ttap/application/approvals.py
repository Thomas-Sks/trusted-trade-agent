from __future__ import annotations

from ttap.application.auditing import Auditor
from ttap.application.errors import Conflict, InvalidSelection, NotFound, PriceLockExpired, StockChanged
from ttap.application.orders import RESERVATION_FOR_STATE, reservation_items
from ttap.domain.approval_card import build_card
from ttap.domain.decision import build_decision_context
from ttap.domain.explain import explain_decision
from ttap.domain.models import ApprovalCard, Offer, Order, OrderState, SelectedLine
from ttap.domain.offer import resolve_selection
from ttap.domain.order_response import build_order_response
from ttap.ports import Clock, MandateRepository, Notifier, PolicyEngine, Store

MODIFY_OUTCOME = {"AUTO_APPROVED": OrderState.APPROVED, "PENDING_HUMAN": OrderState.PENDING_HUMAN,
                  "DENIED": OrderState.DENIED}


class ApprovalService:
    """Step 4 (human side): approve / reject / modify with compare-and-set, fail-closed expiry, full audit."""

    def __init__(self, store: Store, policy: PolicyEngine, mandates: MandateRepository, clock: Clock,
                 auditor: Auditor, notifier: Notifier):
        self._store, self._policy, self._mandates = store, policy, mandates
        self._clock, self._auditor, self._notifier = clock, auditor, notifier

    def _load(self, org_id: str, order_id: str, expected_version: int | None) -> Order:
        order = self._store.get_order(org_id, order_id)
        if order is None:
            raise NotFound(f"order {order_id}")
        if expected_version is not None and expected_version != order.version:
            raise Conflict(f"order {order_id} is at version {order.version}, not {expected_version}")
        return order

    def _offer(self, order: Order) -> Offer:
        offer = self._store.get_offer(order.org_id, order.offer_id)
        if offer is None:
            raise NotFound(f"offer {order.offer_id}")
        return offer

    def _pending_and_locked(self, order: Order) -> None:
        if order.state != OrderState.PENDING_HUMAN:
            raise Conflict(f"order {order.order_id} is {order.state}, not PENDING_HUMAN")
        if order.lock_until is not None and self._clock.now() >= order.lock_until:
            raise PriceLockExpired(f"price lock ended at {order.lock_until.isoformat()}")

    def _commit(self, before: Order, after: Order) -> Order:
        after = after.model_copy(update={"order_response": build_order_response(after, self._offer(after))})
        if not self._store.transition(before.org_id, before.order_id, before.state, before.version, after):
            raise Conflict(f"order {before.order_id} changed concurrently")
        self._store.set_reservation_status(after.order_id, RESERVATION_FOR_STATE.get(after.state, "HELD"))
        return after

    def card(self, org_id: str, order_id: str) -> ApprovalCard:
        order = self._load(org_id, order_id, None)
        return build_card(order, self._offer(order), self._mandates.get(org_id), self._clock.now())

    def pending(self, org_id: str) -> list[Order]:
        return [o for o in self._store.list_orders_by_state(OrderState.PENDING_HUMAN) if o.org_id == org_id]

    async def escalate(self, order: Order) -> None:
        card = self.card(order.org_id, order.order_id)
        await self._notifier.request_approval(order, card)
        self._auditor.record(
            org_id=order.org_id, step="approval", action="escalated", subject=f"order/{order.order_id}",
            actor="system", outcome="PENDING_HUMAN",
            explanation=f"Carte d'approbation envoyée : {' ; '.join(card.reasons)}",
            data={"card": card.model_dump(mode="json")})

    def approve(self, org_id: str, order_id: str, approver: str, expected_version: int | None = None) -> Order:
        order = self._load(org_id, order_id, expected_version)
        self._pending_and_locked(order)
        done = self._commit(order, order.model_copy(update={
            "state": OrderState.APPROVED, "version": order.version + 1, "approved_by": approver}))
        self._auditor.record(
            org_id=org_id, step="approval", action="approved", subject=f"order/{order_id}",
            actor=f"approver:{approver}", outcome="APPROVED",
            explanation=f"Commande {order_id} approuvée par {approver} ({order.total_net} € HT)",
            data={"version": done.version})
        return done

    def reject(self, org_id: str, order_id: str, approver: str, reason: str,
               expected_version: int | None = None) -> Order:
        order = self._load(org_id, order_id, expected_version)
        if order.state != OrderState.PENDING_HUMAN:
            raise Conflict(f"order {order_id} is {order.state}, not PENDING_HUMAN")
        done = self._commit(order, order.model_copy(update={
            "state": OrderState.REJECTED, "version": order.version + 1, "rejection_reason": reason,
            "approved_by": approver}))
        self._auditor.record(
            org_id=org_id, step="approval", action="rejected", subject=f"order/{order_id}",
            actor=f"approver:{approver}", outcome="REJECTED",
            explanation=f"Commande {order_id} rejetée par {approver} : {reason}", data={"reason": reason})
        return done

    def modify(self, org_id: str, order_id: str, approver: str, selected: list[SelectedLine],
               expected_version: int | None = None) -> Order:
        order = self._load(org_id, order_id, expected_version)
        self._pending_and_locked(order)
        try:
            candidates = resolve_selection(self._offer(order), selected)
        except KeyError as exc:
            raise InvalidSelection(f"unknown line or tier: {exc}") from exc
        now = self._clock.now()
        self._store.set_reservation_status(order_id, "RELEASED")
        short = self._store.reserve(org_id, order_id, reservation_items(candidates))
        if short:
            self._store.reserve(org_id, order_id, reservation_items(resolve_selection(self._offer(order),
                                                                                    order.selected)))
            raise StockChanged(f"stock no longer available for {', '.join(short)}")
        decision = self._policy.decide(build_decision_context(candidates, self._mandates.get(org_id), now))
        state = MODIFY_OUTCOME[decision.outcome]
        done = self._commit(order, order.model_copy(update={
            "state": state, "version": order.version + 1, "selected": selected, "decision": decision,
            "decided_at": now, "total_net": sum((c.line_total_net for c in candidates), order.total_net * 0),
            "approved_by": approver if state == OrderState.APPROVED else None}))
        self._auditor.record(
            org_id=org_id, step="approval", action="modified", subject=f"order/{order_id}",
            actor=f"approver:{approver}", outcome=state.value,
            explanation=f"Modifiée par {approver}, réévaluée : {explain_decision(done)}",
            data={"selected": [s.model_dump() for s in selected], "rules_fired": decision.rules_fired})
        return done

    def expire_due(self) -> list[Order]:
        now = self._clock.now()
        expired = []
        for order in self._store.list_orders_by_state(OrderState.PENDING_HUMAN):
            if order.lock_until is None or now < order.lock_until:
                continue
            after = order.model_copy(update={"state": OrderState.EXPIRED, "version": order.version + 1})
            after = after.model_copy(update={"order_response": build_order_response(after, self._offer(after))})
            if self._store.transition(order.org_id, order.order_id, order.state, order.version, after):
                self._store.set_reservation_status(order.order_id, "RELEASED")
                self._auditor.record(
                    org_id=order.org_id, step="approval", action="expired", subject=f"order/{order.order_id}",
                    actor="system", outcome="EXPIRED",
                    explanation=f"Commande {order.order_id} expirée sans approbation : refus par défaut",
                    data={"lock_until": order.lock_until.isoformat()})
                expired.append(after)
        return expired
