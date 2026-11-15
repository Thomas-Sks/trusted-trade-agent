"""TTAP v2026-11-15 conformance requirements (see SPEC.md)."""
from __future__ import annotations

import uuid

import pytest

from ttap.adapters.outbound.jws_signer import EcdsaSigner

LINE = {"line_id": "L1", "need": {"text": "lactose free milk", "required_claims": ["FREE_FROM_LACTOSE"]},
        "quantity": {"value": "10", "unit": "L"}}
DELIVERY = {"requested_date": "2026-11-16", "latest_acceptable_date": "2026-11-16"}


@pytest.fixture(scope="module")
def offer(agent):
    rq = agent.post("/requests", json={"lines": [LINE], "delivery": DELIVERY}).json()
    return agent.post(f"/requests/{rq['request_id']}/lookup").json()


def place(client, offer_id, key=None):
    tier = "good"
    return client.post("/orders", json={"offer_id": offer_id, "selected": [{"line_id": "L1", "tier": tier}]},
                       headers={"Idempotency-Key": key or uuid.uuid4().hex})


@pytest.mark.must
def test_discovery_document(anon):
    """/.well-known/ttap.json publishes protocol, version, the 4 steps and the offer-signing JWKS."""
    doc = anon.get("/.well-known/ttap.json").json()
    assert doc["protocol"] == "TTAP" and doc["steps"] == ["request", "lookup", "order", "approval"]
    assert doc["jwks"]["keys"][0]["kty"] == "EC" and "d" not in doc["jwks"]["keys"][0]


@pytest.mark.must
def test_agent_authentication_required(anon):
    """Every step requires an agent credential; the organisation is never taken from the body."""
    assert anon.post("/requests", json={"lines": [LINE], "delivery": DELIVERY}).status_code in (401, 422)


@pytest.mark.must
def test_unknown_fields_rejected(agent):
    """A request body carrying unknown fields (e.g. a customer id) is rejected."""
    r = agent.post("/requests", json={"lines": [LINE], "delivery": DELIVERY, "customer": "someone-else"})
    assert r.status_code in (400, 422)


@pytest.mark.must
def test_offer_signature_verifies_with_published_key(anon, offer):
    """Offers are ES256 JWS over the RFC 8785 canonical form; verifiable with the published key only."""
    jwk = anon.get("/.well-known/ttap.json").json()["jwks"]["keys"][0]
    payload = {k: v for k, v in offer.items() if k != "signature"}
    assert EcdsaSigner.verify_with_jwk(jwk, payload, offer["signature"])
    payload["valid_until"] = "2099-01-01T00:00:00+00:00"
    assert not EcdsaSigner.verify_with_jwk(jwk, payload, offer["signature"])


@pytest.mark.must
def test_offer_has_validity_and_assurance(offer):
    """Each candidate states its stock assurance level; the offer has a bounded validity."""
    assert offer["valid_until"] > offer["issued_at"]
    for line in offer["lines"]:
        for cand in [*line["tiers"].values(), *line["split"]]:
            assert cand["stock"] in {"VERIFIED_QTY", "VERIFIED_UNLIMITED", "UNKNOWN_SUPPLIER_STOCK", "STALE"}


@pytest.mark.must
def test_order_idempotency_and_single_use_offer(agent):
    """Same Idempotency-Key -> same order; a used offer cannot back a second order."""
    rq = agent.post("/requests", json={"lines": [LINE], "delivery": DELIVERY}).json()
    offer = agent.post(f"/requests/{rq['request_id']}/lookup").json()
    first = place(agent, offer["offer_id"], "conf-key-" + offer["offer_id"])
    again = place(agent, offer["offer_id"], "conf-key-" + offer["offer_id"])
    assert first.status_code == 202 and again.json()["order_id"] == first.json()["order_id"]
    reuse = place(agent, offer["offer_id"])
    assert reuse.status_code == 409 and reuse.json()["code"] == "OFFER_ALREADY_USED"


@pytest.mark.must
def test_decision_is_explicit(agent):
    """Step 4 yields AUTO_APPROVED, PENDING_HUMAN or DENIED with the rules that fired."""
    rq = agent.post("/requests", json={"lines": [LINE], "delivery": DELIVERY}).json()
    offer = agent.post(f"/requests/{rq['request_id']}/lookup").json()
    order = place(agent, offer["offer_id"]).json()
    assert order["state"] in {"AUTO_APPROVED", "PENDING_HUMAN", "DENIED"}
    assert isinstance(order["decision"]["rules_fired"], list)


@pytest.mark.must
def test_cross_organisation_isolation(agent, other, offer):
    """Another organisation cannot see or use an offer or order (404, not 403)."""
    assert place(other, offer["offer_id"]).status_code == 404
    orders = agent.get("/orders").json()
    if orders:
        assert other.get(f"/orders/{orders[0]['order_id']}").status_code == 404


@pytest.mark.must
def test_errors_are_problem_json(agent):
    """Errors use application/problem+json with a stable code."""
    r = agent.post("/requests/rq_does_not_exist/lookup")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["code"] == "NOT_FOUND"


@pytest.mark.must
def test_audit_chain_verifies(agent):
    """The organisation's audit trail is hash-chained, signed and verifiable."""
    report = agent.get("/audit/verify").json()
    assert report["valid"] is True and report["events"] > 0


@pytest.mark.should
def test_peppol_order_response(agent):
    """Order responses follow Peppol BIS Ordering codes; CA carries lines, AP/RE do not."""
    for order in agent.get("/orders").json():
        resp = order.get("order_response")
        if resp:
            assert resp["code"] in {"AB", "AP", "CA", "RE"}
            assert bool(resp["lines"]) == (resp["code"] == "CA")


@pytest.mark.should
def test_preview_commits_nothing(agent):
    """/orders/preview returns the would-be decision without creating an order."""
    rq = agent.post("/requests", json={"lines": [LINE], "delivery": DELIVERY}).json()
    offer = agent.post(f"/requests/{rq['request_id']}/lookup").json()
    before = len(agent.get("/orders").json())
    r = agent.post("/orders/preview", json={"offer_id": offer["offer_id"], "selected": [{"line_id": "L1", "tier": "good"}]})
    assert r.status_code == 200 and r.json()["outcome"] in {"AUTO_APPROVED", "PENDING_HUMAN", "DENIED"}
    assert len(agent.get("/orders").json()) == before
