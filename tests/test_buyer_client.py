import httpx
import pytest

from buyer_agent.ttap_client import OfferNotTrusted, TTAPClient
from tests.test_rest_api import BODY, client


def make() -> TTAPClient:
    app = client().app
    return TTAPClient("http://ttap.test", "key-a", transport=httpx.ASGITransport(app=app))


async def test_buyer_verifies_offer_signature_then_orders():
    c = make()
    rq = await c.create_request(BODY["lines"], "2026-11-16", "2026-11-16")
    offer = await c.lookup(rq["request_id"])
    assert offer["signature_verified"] is True
    order = await c.place_order(offer["offer_id"], [{"line_id": "L1", "tier": "good"}])
    assert order["state"] == "AUTO_APPROVED"
    again = await c.place_order(offer["offer_id"], [{"line_id": "L1", "tier": "good"}])
    assert again["order_id"] == order["order_id"]            # deterministic idempotency key


async def test_tampered_offer_is_refused_by_the_buyer():
    c = make()
    rq = await c.create_request(BODY["lines"], "2026-11-16", "2026-11-16")
    offer = await c._call("POST", f"/requests/{rq['request_id']}/lookup")
    offer["lines"][0]["tiers"]["good"]["unit_net"] = "0.01"   # a man-in-the-middle lowers the price
    assert await c.verify_offer(offer) is False
    real = await c._call("POST", f"/requests/{rq['request_id']}/lookup")
    assert await c.verify_offer(real) is True
    with pytest.raises(OfferNotTrusted):
        c._call = _tampering(c._call)
        await c.lookup(rq["request_id"])


def _tampering(call):
    async def wrapped(method, path, **kw):
        out = await call(method, path, **kw)
        if path.endswith("/lookup"):
            out["valid_until"] = "2099-01-01T00:00:00+02:00"
        return out
    return wrapped
