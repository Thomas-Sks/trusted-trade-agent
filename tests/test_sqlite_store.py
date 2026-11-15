from datetime import timedelta
from decimal import Decimal

from ttap.adapters.outbound.sqlite_store import SqliteStore
from ttap.domain.models import Offer, Order, OrderState, SelectedLine
from tests.factories import DEMO_NOW


def offer(org="org_a") -> Offer:
    return Offer(offer_id="of_1", request_id="rq_1", org_id=org, issued_at=DEMO_NOW,
                 valid_until=DEMO_NOW + timedelta(minutes=30), catalog_version="v", lines=[])


def order(key="k1", oid="or_1") -> Order:
    return Order(order_id=oid, org_id="org_a", offer_id="of_1", offer_hash="h",
                 selected=[SelectedLine(line_id="L1", tier="good")], state=OrderState.PENDING_DECISION,
                 total_net=Decimal("10.00"), idempotency_key=key)


def test_offers_are_isolated_per_org_and_single_use():
    s = SqliteStore()
    s.save_offer(offer())
    assert s.get_offer("org_b", "of_1") is None
    assert s.claim_offer("org_a", "of_1") is True
    assert s.claim_offer("org_a", "of_1") is False


def test_idempotency_key_unique_per_org():
    s = SqliteStore()
    assert s.insert_order(order()) is True
    assert s.insert_order(order(oid="or_2")) is False
    assert s.get_order_by_idempotency_key("org_a", "k1").order_id == "or_1"


def test_transition_is_compare_and_set():
    s = SqliteStore()
    s.insert_order(order())
    updated = order().model_copy(update={"state": OrderState.AUTO_APPROVED, "version": 2})
    assert s.transition("org_a", "or_1", OrderState.PENDING_DECISION, 1, updated) is True
    stale = order().model_copy(update={"state": OrderState.CANCELLED, "version": 2})
    assert s.transition("org_a", "or_1", OrderState.PENDING_DECISION, 1, stale) is False
    assert s.get_order("org_a", "or_1").state == OrderState.AUTO_APPROVED
    assert s.get_order("org_b", "or_1") is None


def test_sandbox_stock_scope_keeps_visitors_from_draining_each_others_stock():
    from datetime import date
    day = date(2026, 11, 16)
    shared, sandbox = SqliteStore(), SqliteStore(stock_scope="org")
    for s in (shared, sandbox):
        assert s.reserve("org_a", "or_1", [("p1", day, Decimal("90"), Decimal("100"))]) == []
    # production: one ledger, so org_b sees what org_a holds and cannot over-reserve
    assert shared.reserved_qty(["p1"], day, "org_b") == {"p1": Decimal("90")}
    assert shared.reserve("org_b", "or_2", [("p1", day, Decimal("20"), Decimal("100"))]) == ["p1"]
    # public-demo sandbox: each organisation only sees and competes with its own reservations
    assert sandbox.reserved_qty(["p1"], day, "org_b") == {"p1": Decimal("0")}
    assert sandbox.reserve("org_b", "or_2", [("p1", day, Decimal("20"), Decimal("100"))]) == []
    assert sandbox.reserve("org_a", "or_3", [("p1", day, Decimal("20"), Decimal("100"))]) == ["p1"]
