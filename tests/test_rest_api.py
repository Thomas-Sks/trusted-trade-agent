from fastapi.testclient import TestClient

from ttap.adapters.inbound.rest_api import Services, create_app
from tests.env import Env

A = {"Authorization": "Bearer key-a"}
B = {"Authorization": "Bearer key-b"}
BODY = {"lines": [{"line_id": "L1", "need": {"text": "lactose free milk", "required_claims": ["FREE_FROM_LACTOSE"]},
                   "quantity": {"value": "1000", "unit": "L"}}],
        "delivery": {"requested_date": "2026-11-16", "latest_acceptable_date": "2026-11-16"}}


def client() -> TestClient:
    env = Env()
    services = Services(requests=env.requests, lookup=env.lookup, orders=env.orders, signer=env.signer)
    return TestClient(create_app(services, {"key-a": "org_a", "key-b": "org_b"}))


def test_full_flow_request_lookup_order():
    c = client()
    rq = c.post("/requests", json=BODY, headers=A)
    assert rq.status_code == 201
    offer = c.post(f"/requests/{rq.json()['request_id']}/lookup", headers=A).json()
    order = c.post("/orders", json={"offer_id": offer["offer_id"], "selected": [{"line_id": "L1", "tier": "good"}]},
                   headers=A | {"Idempotency-Key": "k1"})
    assert order.status_code == 202 and order.json()["state"] == "AUTO_APPROVED"
    assert order.headers["Location"] == f"/orders/{order.json()['order_id']}"
    assert c.get(order.headers["Location"], headers=A).json()["order_id"] == order.json()["order_id"]


def test_org_is_taken_from_token_never_from_body():
    c = client()
    assert c.post("/requests", json=BODY | {"customer": "org_b"}, headers=A).status_code == 422
    assert c.post("/requests", json=BODY).status_code in (401, 422)
    assert c.post("/requests", json=BODY, headers={"Authorization": "Bearer nope"}).status_code == 401


def test_cross_org_access_returns_404_problem_json():
    c = client()
    rq = c.post("/requests", json=BODY, headers=A).json()
    r = c.post(f"/requests/{rq['request_id']}/lookup", headers=B)
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["code"] == "NOT_FOUND"


def test_well_known_publishes_public_key():
    doc = client().get("/.well-known/ttap.json").json()
    assert doc["steps"] == ["request", "lookup", "order", "approval"]
    assert "d" not in doc["jwks"]["keys"][0]
