from datetime import timedelta
from decimal import Decimal

import pytest

from ttap.application.errors import IdempotencyMismatch, InvalidOfferSignature, NotFound, OfferExpired
from ttap.domain.models import OrderState, SelectedLine
from tests.env import GOOD, Env
from tests.factories import DEMO_NOW


async def test_happy_path_auto_approved():
    env = Env()
    offer = await env.offer()
    assert offer.signature and offer.lines[0].tiers["good"].line_total_net == Decimal("1010.00")
    order = env.orders.place("org_a", offer.offer_id, GOOD, "idem-1")
    assert order.state == OrderState.AUTO_APPROVED and order.version == 2


async def test_over_limit_goes_to_human_with_reason():
    env = Env(limit="500")
    order = env.orders.place("org_a", (await env.offer()).offer_id, GOOD, "idem-1")
    assert order.state == OrderState.PENDING_HUMAN
    assert order.decision.rules_fired == ["total_over_order_limit"]


async def test_idempotent_replay_and_mismatch():
    env = Env()
    offer = await env.offer()
    first = env.orders.place("org_a", offer.offer_id, GOOD, "idem-1")
    assert env.orders.place("org_a", offer.offer_id, GOOD, "idem-1").order_id == first.order_id
    with pytest.raises(IdempotencyMismatch):
        env.orders.place("org_a", offer.offer_id, [SelectedLine(line_id="L1", tier="best")], "idem-1")


async def test_other_org_cannot_use_offer():
    env = Env()
    offer = await env.offer()
    with pytest.raises(NotFound):
        env.orders.place("org_b", offer.offer_id, GOOD, "idem-x")


async def test_expired_and_tampered_offers_rejected():
    env = Env()
    offer = await env.offer()
    env.clock.at = DEMO_NOW + timedelta(hours=1)
    with pytest.raises(OfferExpired):
        env.orders.place("org_a", offer.offer_id, GOOD, "idem-2")
    env.clock.at = DEMO_NOW
    offer2 = await env.offer()
    forged = offer2.model_copy(update={"signature": offer.signature})
    env.store._write("UPDATE offers SET body = ? WHERE id = ?", (forged.model_dump_json(), offer2.offer_id))
    with pytest.raises(InvalidOfferSignature):
        env.orders.place("org_a", offer2.offer_id, GOOD, "idem-3")
