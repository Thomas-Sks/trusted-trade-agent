from datetime import date
from decimal import Decimal

import pytest

from ttap.adapters.outbound.caching_gateway import CachingGateway
from ttap.adapters.outbound.scenario_gateway import Scenario, ScenarioGateway
from ttap.domain.errors import UpstreamUnavailable
from tests.factories import price, stock
from tests.fakes import FakeGateway

D = date(2026, 11, 16)


def base():
    return FakeGateway({"A": price("A", "10", "1")}, {"A": stock("A", "9999999999")})


async def test_scenario_overrides_are_applied_and_listed():
    gw = ScenarioGateway(base())
    gw.set(Scenario(stock_override={"A": Decimal("5")}, price_increase_pct={"A": Decimal("10")}))
    assert (await gw.availability(["A"], D))["A"].available_amount == 5
    assert (await gw.prices(["A"], D))["A"].unit_net == Decimal("11.00")
    assert gw.scenario.active() == ["stock:A=5", "price:A+10%"]
    gw.set(Scenario(outage=True))
    with pytest.raises(UpstreamUnavailable):
        await gw.prices(["A"], D)


async def test_cache_serves_stale_during_outage_and_fails_without_cache():
    t = [0.0]
    scen = ScenarioGateway(base())
    cache = CachingGateway(scen, availability_ttl=60, monotonic=lambda: t[0])
    assert (await cache.availability(["A"], D))["A"].stale is False
    scen.set(Scenario(outage=True))
    t[0] = 120.0
    assert (await cache.availability(["A"], D))["A"].stale is True
    with pytest.raises(UpstreamUnavailable):
        await cache.prices(["A"], D)


async def test_stale_or_simulated_data_never_auto_approves():
    from tests.env import GOOD, Env
    from ttap.domain.models import OrderState
    env = Env()
    scen = ScenarioGateway(env.lookup._gateway)
    cache = CachingGateway(scen)
    env.lookup._gateway = cache
    await env.offer()                       # warm cache
    scen.set(Scenario(outage=True))
    cache._ttl["availability"] = cache._ttl["price"] = -1   # force refetch -> outage -> stale
    order = env.orders.place("org_a", (await env.offer()).offer_id, GOOD, "s")
    assert order.state == OrderState.PENDING_HUMAN and "stale_data" in order.decision.rules_fired
