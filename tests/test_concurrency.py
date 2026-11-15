import pytest

from ttap.adapters.outbound.logging_notifier import LoggingNotifier
from ttap.application.approvals import ApprovalService
from ttap.application.errors import StockChanged
from ttap.domain.models import OrderState
from tests.env import GOOD, Env


async def test_two_orgs_race_for_last_units_second_gets_stock_changed_then_partial_view():
    env = Env(stock_amount="1000")
    offer_a = await env.offer("1000", org="org_a")
    offer_b = await env.offer("1000", org="org_b")
    assert env.orders.place("org_a", offer_a.offer_id, GOOD, "a").state == OrderState.AUTO_APPROVED
    with pytest.raises(StockChanged):
        env.orders.place("org_b", offer_b.offer_id, GOOD, "b")
    again = await env.offer("1000", org="org_b")
    assert again.lines[0].tiers == {} and again.lines[0].exceptions == ["NO_ELIGIBLE_PRODUCT"]


async def test_released_reservation_makes_stock_available_again():
    env = Env(limit="500", stock_amount="1000")
    approvals = ApprovalService(env.store, env.policy, env.mandates, env.clock, env.auditor, LoggingNotifier())
    held = env.orders.place("org_a", (await env.offer("1000")).offer_id, GOOD, "a")
    assert held.state == OrderState.PENDING_HUMAN
    assert (await env.offer("600", org="org_b")).lines[0].tiers == {}
    approvals.reject("org_a", held.order_id, "alice", "no")
    assert (await env.offer("600", org="org_b")).lines[0].tiers["good"].qty_sales_units == 600


async def test_period_budget_reserved_atomically_second_order_escalates():
    env = Env(budget="1500")
    first = env.orders.place("org_a", (await env.offer("1000")).offer_id, GOOD, "1")
    second = env.orders.place("org_a", (await env.offer("1000")).offer_id, GOOD, "2")
    assert first.state == OrderState.AUTO_APPROVED
    assert second.state == OrderState.PENDING_HUMAN and second.decision.rules_fired == ["period_budget_exceeded"]


async def test_order_splitting_velocity_escalates():
    env = Env(max_per_hour=2)
    states = [env.orders.place("org_a", (await env.offer("100")).offer_id, GOOD, str(i)).state for i in range(3)]
    assert states[:2] == [OrderState.AUTO_APPROVED] * 2
    assert states[2] == OrderState.PENDING_HUMAN
