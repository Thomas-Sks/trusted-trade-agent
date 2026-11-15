from decimal import Decimal

from ttap.domain.models import Delivery, Offer, Order, OrderState, SelectedLine
from ttap.domain.order_response import build_order_response
from ttap.domain.ranking import build_offer_line
from tests.factories import DEMO_NOW, MONDAY
from tests.test_ranking import tomato_fixture

DELIVERY = Delivery(requested_date=MONDAY, latest_acceptable_date=MONDAY)


def order_for(offer: Offer, tier: str, state=OrderState.PENDING_HUMAN) -> Order:
    return Order(order_id="or_1", org_id="org_a", offer_id=offer.offer_id, offer_hash="h", state=state,
                 selected=[SelectedLine(line_id="L1", tier=tier)], total_net=Decimal("1"), idempotency_key="k")


def offer_from(substitution="best_match") -> Offer:
    ln, products, prices, avail, req = tomato_fixture(substitution)
    line = build_offer_line(ln, products, prices, avail, DELIVERY, requested=req)
    return Offer(offer_id="of_1", request_id="rq", org_id="org_a", issued_at=DEMO_NOW, valid_until=DEMO_NOW,
                 catalog_version="v", lines=[line])


def test_split_gives_conditionally_accepted_with_changed_and_added_lines():
    resp = build_order_response(order_for(offer_from(), "split"), offer_from())
    assert resp.code == "CA"
    assert [(ln.status, ln.product_id, ln.substituted_for) for ln in resp.lines] == [(3, "R", None), (1, "S", "R")]


def test_backorder_is_reported_on_the_partial_line():
    offer = offer_from("no_substitute")
    resp = build_order_response(order_for(offer, "split"), offer)
    assert resp.code == "CA" and resp.lines[0].backorder_qty == Decimal("316")
    assert resp.lines[0].reason == "PARTIAL_WITH_BACKORDER"


def test_exact_match_is_ap_without_lines_and_rejection_is_re():
    from tests.env import Env  # milk fixture: exact, full, no changes
    import asyncio
    env = Env()
    offer = asyncio.run(env.offer())
    assert build_order_response(order_for(offer, "good"), offer).model_dump() == {"code": "AP", "lines": []}
    assert build_order_response(order_for(offer, "good", OrderState.REJECTED), offer).code == "RE"
