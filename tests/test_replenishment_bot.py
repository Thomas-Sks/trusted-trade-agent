from datetime import date

import httpx

from buyer_agent.replenishment_bot import ParLevel, replenish
from buyer_agent.ttap_client import TTAPClient
from tests.test_rest_api import client


async def test_bot_orders_only_below_par_and_is_governed_by_the_same_mandate():
    c = TTAPClient("http://t", "key-a", transport=httpx.ASGITransport(app=client(limit="100").app))
    logs: list[str] = []
    out = await replenish(c, [ParLevel("M1", "L", 60, 200, 35), ParLevel("M1", "L", 10, 40, 25)],
                          date(2026, 11, 16), log=logs.append)
    assert len(out) == 1
    assert out[0]["state"] == "PENDING_HUMAN"                      # 165 L * 1.01 > 100 € limit
    assert out[0]["decision"]["rules_fired"] == ["total_over_order_limit"]
    assert any("nothing to do" in line for line in logs)
