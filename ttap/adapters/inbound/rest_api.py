from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from ttap.adapters.outbound.jws_signer import EcdsaSigner
from ttap.application.approvals import ApprovalService
from ttap.application.auditing import Auditor
from ttap.application.errors import TTAPError
from ttap.application.interpret import InterpretService
from ttap.application.lookup import LookupService
from ttap.application.mandates import MandateChanges, MandateService
from ttap.application.orders import OrderService
from ttap.application.requests import RequestService
from ttap.domain.audit_verify import verify_chain
from ttap.domain.models import (
    ApprovalCard, AuditEvent, Delivery, Offer, Order, OrderState, PurchaseRequest, RequestLine, SelectedLine,
)
from ttap.ports import Signer

log = logging.getLogger("ttap.rest")

PROTOCOL_VERSION = "2026-11-15"


@dataclass
class DemoControls:
    """Seller-admin demo levers. Everything they change is flagged SIMULATED in offers and audit."""
    scenario: object  # ScenarioGateway
    cache: object | None  # CachingGateway
    clock: object  # ShiftedClock
    store: object | None = None  # SqliteStore (for reset)


@dataclass
class Services:
    requests: RequestService
    lookup: LookupService
    orders: OrderService
    signer: Signer
    approvals: ApprovalService
    auditor: Auditor
    demo: DemoControls | None = None
    interpret: InterpretService | None = None
    mandates: MandateService | None = None


class InterpretBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str


class ClockAdvance(BaseModel):
    minutes: float


class Lifecycle(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...


class CreateRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lines: list[RequestLine]
    delivery: Delivery


class PlaceOrderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    offer_id: str
    selected: list[SelectedLine]


class ApproveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int | None = None


class RejectBody(ApproveBody):
    reason: str


class ModifyBody(ApproveBody):
    selected: list[SelectedLine]


class Unauthorized(TTAPError):
    code, status = "UNAUTHORIZED", 401


def create_app(services: Services, agent_keys: dict[str, str],
               approver_keys: dict[str, tuple[str, str]] | None = None,
               lifecycle: Lifecycle | None = None, expiry_interval_s: float = 30.0,
               admin_key: str | None = None) -> FastAPI:
    approver_keys = approver_keys or {}

    async def _expiry_loop() -> None:
        while True:
            await asyncio.sleep(expiry_interval_s)
            try:
                await services.approvals.remind_overdue()
                services.approvals.expire_due()
            except Exception:  # never let the loop die
                log.exception("expiry sweep failed")

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(_expiry_loop())
        if lifecycle:
            await lifecycle.start()
        try:
            yield
        finally:
            task.cancel()
            if lifecycle:
                await lifecycle.stop()

    app = FastAPI(title="Trusted Trade Agent Protocol", version=PROTOCOL_VERSION, lifespan=lifespan)

    @app.exception_handler(TTAPError)
    async def _problem(_: Request, exc: TTAPError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, media_type="application/problem+json",
                            content={"type": "about:blank", "title": exc.code, "status": exc.status,
                                     "code": exc.code, "detail": str(exc)})

    def _token(authorization: str) -> str:
        return authorization.removeprefix("Bearer ").strip()

    def org_id(authorization: str = Header()) -> str:
        org = agent_keys.get(_token(authorization))
        if org is None:
            raise Unauthorized("unknown agent key")
        return org

    def approver(authorization: str = Header()) -> tuple[str, str]:
        ref = approver_keys.get(_token(authorization))
        if ref is None:
            raise Unauthorized("unknown approver key")
        return ref

    def any_org(authorization: str = Header()) -> str:
        token = _token(authorization)
        if token in agent_keys:
            return agent_keys[token]
        if token in approver_keys:
            return approver_keys[token][0]
        raise Unauthorized("unknown key")

    def admin(authorization: str = Header()) -> str:
        if not admin_key or _token(authorization) != admin_key or services.demo is None:
            raise Unauthorized("admin key required")
        return "seller_admin"

    @app.put("/admin/scenario")
    def set_scenario(body: dict, _: str = Depends(admin)) -> dict:
        from ttap.adapters.outbound.scenario_gateway import Scenario
        services.demo.scenario.set(Scenario.model_validate(body))
        if services.demo.cache:
            services.demo.cache.clear()
        return {"active": services.demo.scenario.scenario.active()}

    @app.delete("/admin/scenario")
    def clear_scenario(_: str = Depends(admin)) -> dict:
        services.demo.scenario.clear()
        if services.demo.cache:
            services.demo.cache.clear()
        return {"active": []}

    @app.post("/admin/reset")
    def reset_demo(_: str = Depends(admin)) -> dict:
        services.demo.store.reset_demo()
        services.demo.scenario.clear()
        if services.demo.cache:
            services.demo.cache.clear()
        return {"reset": True}

    @app.get("/admin/state")
    def demo_state(_: str = Depends(admin)) -> dict:
        return {"now": services.demo.clock.now().isoformat(), "scenario": services.demo.scenario.scenario.active()}

    @app.post("/admin/clock/advance")
    def advance_clock(body: ClockAdvance, _: str = Depends(admin)) -> dict:
        return {"now": services.demo.clock.advance(body.minutes).isoformat()}

    @app.post("/interpret")
    async def interpret(body: InterpretBody, org: str = Depends(org_id)) -> dict:
        from ttap.application.interpret import InterpreterUnavailable
        if services.interpret is None:
            raise InterpreterUnavailable("interpretation not configured")
        return await services.interpret.interpret(org, body.text)

    @app.post("/requests", status_code=201, response_model=PurchaseRequest)
    def create_request(body: CreateRequestBody, org: str = Depends(org_id)) -> PurchaseRequest:
        return services.requests.create(org, body.lines, body.delivery)

    @app.post("/requests/{request_id}/lookup", response_model=Offer)
    async def lookup(request_id: str, org: str = Depends(org_id)) -> Offer:
        return await services.lookup.lookup(org, request_id)

    @app.post("/orders", status_code=202, response_model=Order)
    async def place_order(body: PlaceOrderBody, response: Response, org: str = Depends(org_id),
                          idempotency_key: str = Header(alias="Idempotency-Key")) -> Order:
        order = services.orders.place(org, body.offer_id, body.selected, idempotency_key)
        response.headers["Location"] = f"/orders/{order.order_id}"
        if order.state == OrderState.PENDING_HUMAN and order.version == 2:
            try:
                await services.approvals.escalate(order)
            except Exception:  # the order is safely pending even if the channel is down
                log.exception("escalation delivery failed for %s", order.order_id)
        return order

    @app.post("/orders/preview")
    def preview_order(body: PlaceOrderBody, org: str = Depends(org_id)) -> dict:
        """Dry run: the decision the mandate would take for this selection. Nothing is committed."""
        return services.orders.preview(org, body.offer_id, body.selected)

    @app.get("/orders", response_model=list[Order])
    def list_orders(org: str = Depends(any_org)) -> list[Order]:
        return services.orders.list(org)

    @app.get("/orders/{order_id}", response_model=Order)
    def get_order(order_id: str, org: str = Depends(any_org)) -> Order:
        return services.orders.get(org, order_id)

    @app.get("/approvals", response_model=list[Order])
    def pending_approvals(who: tuple[str, str] = Depends(approver)) -> list[Order]:
        return services.approvals.pending(who[0])

    @app.get("/orders/{order_id}/card", response_model=ApprovalCard)
    def approval_card(order_id: str, who: tuple[str, str] = Depends(approver)) -> ApprovalCard:
        return services.approvals.card(who[0], order_id)

    @app.post("/orders/{order_id}/approve", response_model=Order)
    def approve(order_id: str, body: ApproveBody, who: tuple[str, str] = Depends(approver)) -> Order:
        return services.approvals.approve(who[0], order_id, who[1], body.expected_version)

    @app.post("/orders/{order_id}/reject", response_model=Order)
    def reject(order_id: str, body: RejectBody, who: tuple[str, str] = Depends(approver)) -> Order:
        return services.approvals.reject(who[0], order_id, who[1], body.reason, body.expected_version)

    @app.post("/orders/{order_id}/modify", response_model=Order)
    async def modify(order_id: str, body: ModifyBody, who: tuple[str, str] = Depends(approver)) -> Order:
        order = services.approvals.modify(who[0], order_id, who[1], body.selected, body.expected_version)
        if order.state == OrderState.PENDING_HUMAN:
            await services.approvals.escalate(order)
        return order

    @app.get("/approvals/stats")
    def approval_stats(who: tuple[str, str] = Depends(approver)) -> dict:
        from ttap.domain.oversight import oversight_stats
        return oversight_stats(services.auditor.log.list(who[0])).model_dump()

    @app.get("/mandate")
    def get_mandate(who: tuple[str, str] = Depends(approver)) -> dict:
        return services.mandates.get(who[0]).model_dump(mode="json")

    @app.post("/mandate/pause")
    def pause_mandate(who: tuple[str, str] = Depends(approver)) -> dict:
        return services.mandates.set_status(who[0], "suspended", who[1]).model_dump(mode="json")

    @app.post("/mandate/resume")
    def resume_mandate(who: tuple[str, str] = Depends(approver)) -> dict:
        return services.mandates.set_status(who[0], "active", who[1]).model_dump(mode="json")

    @app.post("/mandate/simulate")
    def simulate_mandate(body: MandateChanges, who: tuple[str, str] = Depends(approver)) -> dict:
        """What-if: replay this organisation's recorded decisions with modified mandate parameters (read-only)."""
        return services.mandates.simulate(who[0], body).model_dump(mode="json")

    @app.get("/audit", response_model=list[AuditEvent])
    def audit(org: str = Depends(any_org)) -> list[AuditEvent]:
        return services.auditor.log.list(org)

    @app.get("/audit/verify")
    def audit_verify(org: str = Depends(any_org)) -> dict:
        events = services.auditor.log.list(org)
        problems = verify_chain(events, services.signer.public_jwk(), EcdsaSigner.verify_with_jwk)
        return {"org_id": org, "events": len(events), "valid": not problems, "problems": problems}

    @app.get("/.well-known/ttap.json")
    def well_known() -> dict:
        return {"protocol": "TTAP", "version": PROTOCOL_VERSION,
                "steps": ["request", "lookup", "order", "approval"],
                "jwks": {"keys": [services.signer.public_jwk()]}}

    return app
