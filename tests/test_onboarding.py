from fastapi.testclient import TestClient

from ttap.adapters.inbound.rest_api import create_app
from ttap.application.onboarding import OnboardingService
from tests.test_rest_api import BODY, client




def test_self_service_onboarding_end_to_end():
    from tests.env import Env
    from ttap.adapters.outbound.logging_notifier import LoggingNotifier
    from ttap.application.approvals import ApprovalService
    from ttap.application.mandates import MandateService
    from ttap.adapters.inbound.rest_api import Services
    env = Env()
    agent_keys, approver_keys, pairing = {}, {}, {}
    svc = Services(requests=env.requests, lookup=env.lookup, orders=env.orders, signer=env.signer,
                   approvals=ApprovalService(env.store, env.policy, env.mandates, env.clock, env.auditor, LoggingNotifier()),
                   auditor=env.auditor, mandates=MandateService(env.mandates, env.policy, env.auditor))
    svc.onboarding = OnboardingService(env.store, env.mandates, env.clock, env.auditor, agent_keys, approver_keys,
                                       pairing, telegram_bot="ttap_demo_bot")
    c = TestClient(create_app(svc, agent_keys, approver_keys))

    org = c.post("/onboarding/organisations", json={"name": "Junction Jury Café", "approver_name": "Jane Judge",
                                                     "limit_per_order_net": "500"}).json()
    assert org["org_id"].startswith("org_junction_jury_caf") and org["telegram_link"].startswith("https://t.me/ttap_demo_bot?start=PAIR-")
    assert pairing[org["pairing_code"]] == (org["org_id"], "jane_judge")
    agent = {"Authorization": f"Bearer {org['agent_key']}"}
    approver = {"Authorization": f"Bearer {org['approver_key']}"}

    rq = c.post("/requests", json=BODY, headers=agent).json()               # the new agent key works immediately
    offer = c.post(f"/requests/{rq['request_id']}/lookup", headers=agent).json()
    order = c.post("/orders", json={"offer_id": offer["offer_id"], "selected": [{"line_id": "L1", "tier": "good"}]},
                   headers=agent | {"Idempotency-Key": "j1"}).json()
    assert order["state"] == "PENDING_HUMAN"                                # its own mandate: 1,010 > 500
    assert c.get("/onboarding/status", headers=approver).json()["telegram_paired"] is False
    env.store.link_approver(777, org["org_id"], "jane_judge")
    assert c.get("/onboarding/status", headers=approver).json()["telegram_paired"] is True
    assert c.post(f"/orders/{order['order_id']}/approve", json={}, headers=approver).json()["state"] == "APPROVED"

    reloaded_keys, reloaded_approvers, reloaded_pairing = {}, {}, {}
    again = OnboardingService(env.store, env.mandates, env.clock, env.auditor, reloaded_keys, reloaded_approvers,
                              reloaded_pairing)
    assert again.load_all() == 1 and reloaded_keys[org["agent_key"]] == org["org_id"]


def test_onboarding_validates_input():
    c = client()
    assert c.post("/onboarding/organisations", json={"name": "x", "approver_name": "y"}).status_code in (401, 422)
