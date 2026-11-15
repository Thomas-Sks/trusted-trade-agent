from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from ttap.application.errors import TTAPError
from ttap.application.lookup import LookupService
from ttap.application.orders import OrderService
from ttap.application.requests import RequestService
from ttap.domain.models import Delivery, Offer, Order, PurchaseRequest, RequestLine, SelectedLine
from ttap.ports import Signer

PROTOCOL_VERSION = "2026-11-15"


@dataclass
class Services:
    requests: RequestService
    lookup: LookupService
    orders: OrderService
    signer: Signer


class CreateRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lines: list[RequestLine]
    delivery: Delivery


class PlaceOrderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    offer_id: str
    selected: list[SelectedLine]


class Unauthorized(TTAPError):
    code, status = "UNAUTHORIZED", 401


def create_app(services: Services, agent_keys: dict[str, str]) -> FastAPI:
    app = FastAPI(title="Trusted Trade Agent Protocol", version=PROTOCOL_VERSION)

    @app.exception_handler(TTAPError)
    async def _problem(_: Request, exc: TTAPError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, media_type="application/problem+json",
                            content={"type": "about:blank", "title": exc.code, "status": exc.status,
                                     "code": exc.code, "detail": str(exc)})

    def org_id(authorization: str = Header()) -> str:
        org = agent_keys.get(authorization.removeprefix("Bearer ").strip())
        if org is None:
            raise Unauthorized("unknown agent key")
        return org

    @app.post("/requests", status_code=201, response_model=PurchaseRequest)
    def create_request(body: CreateRequestBody, org: str = Depends(org_id)) -> PurchaseRequest:
        return services.requests.create(org, body.lines, body.delivery)

    @app.post("/requests/{request_id}/lookup", response_model=Offer)
    async def lookup(request_id: str, org: str = Depends(org_id)) -> Offer:
        return await services.lookup.lookup(org, request_id)

    @app.post("/orders", status_code=202, response_model=Order)
    def place_order(body: PlaceOrderBody, response: Response, org: str = Depends(org_id),
                    idempotency_key: str = Header(alias="Idempotency-Key")) -> Order:
        order = services.orders.place(org, body.offer_id, body.selected, idempotency_key)
        response.headers["Location"] = f"/orders/{order.order_id}"
        return order

    @app.get("/orders/{order_id}", response_model=Order)
    def get_order(order_id: str, org: str = Depends(org_id)) -> Order:
        return services.orders.get(org, order_id)

    @app.get("/.well-known/ttap.json")
    def well_known() -> dict:
        return {"protocol": "TTAP", "version": PROTOCOL_VERSION,
                "steps": ["request", "lookup", "order", "approval"],
                "jwks": {"keys": [services.signer.public_jwk()]}}

    return app
