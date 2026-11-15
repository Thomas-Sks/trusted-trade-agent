"""Order response aligned on Peppol BIS Ordering 3 (OrderResponseCode UNCL4343 subset, LineStatusCode UNCL1229).

Peppol rules honoured: CA (conditionally accepted) MUST carry lines; AP, RE, AB MUST NOT.
"""
from __future__ import annotations

from decimal import Decimal

from ttap.domain.models import Candidate, Offer, Order, OrderResponse, OrderResponseLine, OrderState

ACCEPTED, CHANGED, ADDED, NOT_ACCEPTED = 5, 3, 1, 7
REJECTED_STATES = {OrderState.DENIED, OrderState.REJECTED, OrderState.EXPIRED, OrderState.CANCELLED}


def _substituted_for(c: Candidate) -> str | None:
    return next((x.split(":", 1)[1] for x in c.changes_vs_request if x.startswith("substitute:")), None)


def _line(line_id: str, c: Candidate, backorder: Decimal = Decimal("0")) -> OrderResponseLine:
    if c.is_substitute:
        status, reason = ADDED, "SUBSTITUTED"
    elif c.partial:
        status, reason = CHANGED, "PARTIAL_WITH_BACKORDER" if backorder > 0 else "PARTIAL_COMPLETED_BY_SUBSTITUTE"
    elif c.changes_vs_request:
        status, reason = CHANGED, "CHANGED:" + ",".join(c.changes_vs_request)
    else:
        status, reason = ACCEPTED, None
    return OrderResponseLine(line_id=line_id, status=status, product_id=c.product_id, quantity=c.qty_sales_units,
                             sales_unit=c.sales_unit, substituted_for=_substituted_for(c),
                             backorder_qty=backorder if not c.is_substitute else Decimal("0"), reason=reason)


def build_order_response(order: Order, offer: Offer) -> OrderResponse:
    if order.state in REJECTED_STATES:
        return OrderResponse(code="RE", lines=[])
    offer_lines = {line.line_id: line for line in offer.lines}
    lines: list[OrderResponseLine] = []
    for sel in order.selected:
        line = offer_lines[sel.line_id]
        if sel.tier == "split":
            for i, c in enumerate(line.split):
                lines.append(_line(sel.line_id, c, line.backorder_qty if i == 0 else Decimal("0")))
        else:
            lines.append(_line(sel.line_id, line.tiers[sel.tier]))
    if all(ln.status == ACCEPTED for ln in lines):
        return OrderResponse(code="AP", lines=[])
    return OrderResponse(code="CA", lines=lines)
