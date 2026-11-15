"""Buyer-side TTAP client: talks to any TTAP gateway over REST and VERIFIES every offer it receives.

This is the 'agent side' of the trust protocol: an offer whose ES256 signature does not verify against the
gateway's published key (/.well-known/ttap.json) is rejected before the agent can act on it.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

import httpx

from ttap.adapters.outbound.jws_signer import EcdsaSigner


class OfferNotTrusted(Exception):
    pass


class TTAPError(Exception):
    def __init__(self, status: int, body: dict):
        super().__init__(f"{status} {body.get('code')}: {body.get('detail')}")
        self.status, self.code, self.body = status, body.get("code"), body


class TTAPClient:
    def __init__(self, base_url: str, agent_key: str, transport: httpx.AsyncBaseTransport | None = None):
        self._http = httpx.AsyncClient(base_url=base_url, transport=transport, timeout=60.0,
                                       headers={"Authorization": f"Bearer {agent_key}"})
        self._protocol: dict | None = None

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _call(self, method: str, path: str, **kw: Any) -> Any:
        resp = await self._http.request(method, path, **kw)
        if resp.status_code >= 400:
            try:
                body = resp.json()
            except ValueError:
                body = {"code": "HTTP_ERROR", "detail": resp.text}
            raise TTAPError(resp.status_code, body)
        return resp.json()

    async def protocol(self) -> dict:
        if self._protocol is None:
            self._protocol = await self._call("GET", "/.well-known/ttap.json")
        return self._protocol

    async def create_request(self, lines: list[dict], requested_date: str, latest_acceptable_date: str) -> dict:
        return await self._call("POST", "/requests", json={"lines": lines, "delivery": {
            "requested_date": requested_date, "latest_acceptable_date": latest_acceptable_date}})

    async def interpret(self, text: str) -> dict:
        return await self._call("POST", "/interpret", json={"text": text})

    async def verify_offer(self, offer: dict) -> bool:
        jwk = (await self.protocol())["jwks"]["keys"][0]
        payload = {k: v for k, v in offer.items() if k != "signature"}
        return bool(offer.get("signature")) and EcdsaSigner.verify_with_jwk(jwk, payload, offer["signature"])

    async def lookup(self, request_id: str) -> dict:
        offer = await self._call("POST", f"/requests/{request_id}/lookup")
        if not await self.verify_offer(offer):
            raise OfferNotTrusted(f"offer {offer.get('offer_id')} signature does not verify: refusing to use it")
        offer["signature_verified"] = True
        return offer

    async def place_order(self, offer_id: str, selected: list[dict], idempotency_key: str | None = None) -> dict:
        key = idempotency_key or hashlib.sha256(
            json.dumps([offer_id, selected], sort_keys=True).encode()).hexdigest()[:32]
        return await self._call("POST", "/orders", json={"offer_id": offer_id, "selected": selected},
                                headers={"Idempotency-Key": key})

    async def get_order(self, order_id: str) -> dict:
        return await self._call("GET", f"/orders/{order_id}")

    async def audit(self) -> list[dict]:
        return await self._call("GET", "/audit")
