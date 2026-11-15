from tests.test_rest_api import APPROVER, A, client

MILK = lambda litres: {"lines": [{"line_id": "L1", "need": {"text": "lactose free milk", "required_claims": ["FREE_FROM_LACTOSE"]},
                                  "quantity": {"value": litres, "unit": "L"}}],
                       "delivery": {"requested_date": "2026-11-16", "latest_acceptable_date": "2026-11-16"}}


def order(c, litres, key):
    rq = c.post("/requests", json=MILK(litres), headers=A).json()
    offer = c.post(f"/requests/{rq['request_id']}/lookup", headers=A).json()
    return c.post("/orders", json={"offer_id": offer["offer_id"], "selected": [{"line_id": "L1", "tier": "good"}]},
                  headers=A | {"Idempotency-Key": key}).json()


def test_what_if_replays_recorded_decisions_deterministically():
    c = client(limit="500")
    big = order(c, "1000", "a")            # 1,010 € > 500 -> PENDING_HUMAN
    small = order(c, "300", "b")           # 303 € <= 500 -> AUTO_APPROVED
    assert (big["state"], small["state"]) == ("PENDING_HUMAN", "AUTO_APPROVED")

    same = c.post("/mandate/simulate", json={}, headers=APPROVER).json()
    assert same["replayed"] == 2 and same["changed"] == 0          # determinism: current mandate -> no change

    looser = c.post("/mandate/simulate", json={"limit_per_order_net": "2000"}, headers=APPROVER).json()
    assert looser["summary"] == "1 of 2 past orders would have changed decision"
    assert looser["changes"][0] | {"rules_after": []} == {
        "order_id": big["order_id"], "total_net": "1010.00", "before": "PENDING_HUMAN", "after": "AUTO_APPROVED",
        "rules_before": ["total_over_order_limit"], "rules_after": []}

    stricter = c.post("/mandate/simulate", json={"limit_per_order_net": "100"}, headers=APPROVER).json()
    assert stricter["changed"] == 1 and stricter["changes"][0]["order_id"] == small["order_id"]


def test_simulation_is_approver_only_and_rejects_unknown_parameters():
    c = client()
    assert c.post("/mandate/simulate", json={}, headers=A).status_code == 401
    assert c.post("/mandate/simulate", json={"allowed_categories": "*"}, headers=APPROVER).status_code == 422


def test_old_decisions_missing_newer_facts_replay_with_neutral_defaults():
    from decimal import Decimal
    from ttap.domain.simulation import restore_context
    old = {"mandate_active": True, "total_net": "1010.00", "limit_per_order_net": "2000",
           "max_unverified_value_net": "500"}
    ctx = restore_context(old)
    assert ctx["has_partial"] is False and ctx["period_spend_net"] == Decimal("1010.00")
    assert ctx["total_net"] == Decimal("1010.00")
