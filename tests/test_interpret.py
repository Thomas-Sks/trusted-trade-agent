from datetime import date

from fastapi.testclient import TestClient

from ttap.adapters.inbound.rest_api import Services, create_app
from ttap.adapters.outbound.logging_notifier import LoggingNotifier
from ttap.application.approvals import ApprovalService
from ttap.application.interpret import InterpretService
from ttap.domain.interpretation import InterpretedLine, InterpretedRequest
from tests.env import Env

A = {"Authorization": "Bearer key-a"}


class FakeInterpreter:
    def __init__(self):
        self.seen = None

    async def interpret(self, text, today, usual):
        self.seen = (text, today, usual)
        return InterpretedRequest(
            lines=[InterpretedLine(need_text="milk", required_claims=["FREE_FROM_LACTOSE", "NOT_A_CODE"],
                                   quantity_value=1000, quantity_unit="L", origin_preferences=["fi"])],
            requested_date=date(2026, 11, 16), latest_acceptable_date=date(2026, 11, 16),
            assumptions=["semi-skimmed milk by default"], questions=[])


def app(interpreter):
    env = Env()
    approvals = ApprovalService(env.store, env.policy, env.mandates, env.clock, env.auditor, LoggingNotifier())
    svc = Services(requests=env.requests, lookup=env.lookup, orders=env.orders, signer=env.signer,
                   approvals=approvals, auditor=env.auditor,
                   interpret=InterpretService(interpreter, env.lookup._catalog, env.mandates, env.clock, env.auditor))
    return TestClient(create_app(svc, {"key-a": "org_a"})), env


def test_interpret_returns_protocol_draft_and_filters_unknown_codes():
    fake = FakeInterpreter()
    c, env = app(fake)
    draft = c.post("/interpret", json={"text": "1000 L de lait sans lactose pour lundi"}, headers=A).json()
    assert draft["lines"][0]["need"]["required_claims"] == ["FREE_FROM_LACTOSE"]
    assert draft["lines"][0]["quantity"] == {"value": "1000.0", "unit": "L"}
    assert draft["assumptions"] == ["semi-skimmed milk by default"]
    assert fake.seen[1] == date(2026, 11, 12)
    rq = c.post("/requests", json={"lines": draft["lines"], "delivery": draft["delivery"]}, headers=A)
    assert rq.status_code == 201
    assert env.audit.list("org_a")[0].type == "org.ttap.request.interpreted.v1"


def test_without_llm_the_protocol_still_works_and_interpret_says_so():
    c, _ = app(None)
    r = c.post("/interpret", json={"text": "x"}, headers=A)
    assert r.status_code == 503 and r.json()["code"] == "INTERPRETER_UNAVAILABLE"


class BrokeInterpreter:
    async def interpret(self, text, today, usual):
        import anthropic
        import httpx
        from ttap.adapters.outbound.llm_errors import LLMFailure
        req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        raise LLMFailure(anthropic.BadRequestError("Your credit balance is too low to access the Anthropic API.",
                                                   response=httpx.Response(400, request=req), body=None))


def test_exhausted_credit_reaches_the_client_as_its_own_code():
    client, _ = app(BrokeInterpreter())
    r = client.post("/interpret", json={"text": "1000 L milk"}, headers=A)
    assert r.status_code == 503
    assert r.json()["code"] == "AI_CREDITS_EXHAUSTED"
    assert "no credit left" in r.json()["detail"]


def test_overlong_interpret_text_is_rejected_before_the_llm():
    fake = FakeInterpreter()
    client, _ = app(fake)
    assert client.post("/interpret", json={"text": "x" * 1001}, headers=A).status_code == 422
    assert fake.seen is None
