"""Deterministic, template-based explanations. Never produced by an LLM."""
from __future__ import annotations

from ttap.domain.formatting import money, when
from ttap.domain.models import Offer, Order

RULE_TEXT: dict[str, str] = {
    "total_over_order_limit": "Total €{total_net} excl. VAT > per-order limit €{limit_per_order_net}",
    "unverified_stock_over_limit": (
        "Unverified supplier stock worth €{unverified_value_net} > limit €{max_unverified_value_net}"),
    "origin_conflict": "Conflicting origin between Valio and the manufacturer",
    "deviates_from_request": "Choice deviates from the request (substitute, origin or brand)",
    "partial_fulfilment": "Partial availability: the requested product does not cover the full quantity",
    "period_budget_exceeded": "Period budget exceeded: €{period_spend_net} committed > €{period_budget_net}",
    "order_velocity_exceeded": (
        "Unusual pace: {orders_last_hour} orders within an hour > {max_orders_per_hour} (order splitting?)"),
    "stale_data": "Stale supplier data (served from cache during an outage)",
    "mandate_not_active": "Mandate inactive, suspended or expired",
    "policy_evaluation_error": "Policy evaluation error: denied by default",
}

OUTCOME_TEXT = {
    "AUTO_APPROVED": "auto-approved within the mandate",
    "PENDING_HUMAN": "escalated to a human approver",
    "DENIED": "denied",
}

MONEY_KEYS = ("_net", "_value")


def _display(context: dict) -> dict:
    return {k: money(v) if k.endswith(MONEY_KEYS) and not isinstance(v, bool) else v for k, v in context.items()}


def explain_rules(rules: list[str], context: dict) -> list[str]:
    out = []
    shown = _display(context)
    for rule in rules:
        template = RULE_TEXT.get(rule)
        try:
            out.append(template.format(**shown) if template else f"Rule triggered: {rule}")
        except (KeyError, IndexError):
            out.append(f"Rule triggered: {rule}")
    return out


def explain_decision(order: Order) -> str:
    if order.decision is None:
        return f"Order {order.order_id} awaiting decision."
    base = f"Order {order.order_id}: €{money(order.total_net)} excl. VAT, {OUTCOME_TEXT[order.decision.outcome]}"
    reasons = explain_rules(order.decision.rules_fired, order.decision.context)
    return base + (" because: " + "; ".join(reasons) if reasons else ".")


def explain_offer(offer: Offer) -> str:
    parts = []
    for line in offer.lines:
        good = line.tiers.get("good")
        if good is None:
            plan = f", mixed plan of {len(line.split)} product(s)" if line.split else ""
            parts.append(f"{line.line_id}: no full product{plan} ({len(line.excluded)} excluded)")
        else:
            parts.append(f"{line.line_id}: best price {good.name} at €{money(good.comparison_net)} per comparison "
                         f"unit, {len(line.excluded)} products excluded")
    return f"Signed offer valid until {when(offer.valid_until)} — " + "; ".join(parts)
