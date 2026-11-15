"""Buyer-side agent service: runs the Claude reference agent or the replenishment bot and streams what they do.

    uv run --env-file .env uvicorn buyer_agent.agent_server:app --port 8820

It lives on the BUYER side (it holds the buyer's agent keys), next to the hotel's systems, not inside the gateway.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import date

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from buyer_agent.kitchen import kitchen_for, restock
from buyer_agent.reference_agent import KITCHEN_SYSTEM, run_events
from buyer_agent.replenishment_bot import DEMO_PAR_LEVELS, replenish
from buyer_agent.ttap_client import TTAPClient

GATEWAY = os.environ.get("TTAP_URL", "http://localhost:8811")
SELF_URL = os.environ.get("KITCHEN_URL", f"http://localhost:{os.environ.get('AGENT_PORT', '8820')}")
KEYS = {"hotel": os.environ.get("KEY_AGENT_HOTEL", "demo-key-hotel-a"),
        "resto": os.environ.get("KEY_AGENT_RESTO", "demo-key-resto-b")}
app = FastAPI(title="TTAP buyer agents")


class RunBody(BaseModel):
    org: str = "hotel"
    text: str = Field("", max_length=400)  # a purchasing request is short; caps what a visitor can send to the LLM
    agent_key: str | None = None  # organisations onboarded in the console bring their own key


def key_for(body: RunBody) -> str:
    return body.agent_key or KEYS.get(body.org, KEYS["hotel"])


def ndjson(stream):
    async def gen():
        async for event in stream:
            yield json.dumps(event, default=str) + "\n"
    return StreamingResponse(gen(), media_type="application/x-ndjson")


@app.post("/run/claude")
async def run_claude(body: RunBody):
    return ndjson(run_events(body.text, key_for(body), GATEWAY))


@app.post("/run/bot")
async def run_bot(body: RunBody):
    async def stream():
        queue: asyncio.Queue = asyncio.Queue()
        client = TTAPClient(GATEWAY, key_for(body), via="rest:replenishment-bot")

        async def drive():
            try:
                await replenish(client, DEMO_PAR_LEVELS, date(2026, 11, 16),
                                log=lambda line: queue.put_nowait({"type": "text", "text": line}))
            finally:
                await client.aclose()
                await queue.put({"type": "done"})

        yield {"type": "start", "model": "deterministic replenishment bot (no LLM)", "tools": ["REST"]}
        task = asyncio.create_task(drive())
        while (event := await queue.get())["type"] != "done":
            yield event
        await task
        yield {"type": "done"}
    return ndjson(stream())


# --- Kitchen: the restaurant's inventory (buyer side) and its restock agent -------------------------------------

class KitchenBody(BaseModel):
    org: str = "resto"
    agent_key: str | None = None
    mode: str = "bot"  # bot | claude


def kitchen_key(body: KitchenBody) -> str:
    return body.agent_key or KEYS.get(body.org, KEYS["resto"])


async def _orders(agent_key: str) -> list[dict]:
    client = TTAPClient(GATEWAY, agent_key, via="rest:kitchen-inventory")
    try:
        return await client._call("GET", "/orders")
    finally:
        await client.aclose()


@app.post("/kitchen/state")
async def kitchen_state(body: KitchenBody):
    key = kitchen_key(body)
    return kitchen_for(key).state(await _orders(key))


@app.post("/kitchen/report")
async def kitchen_report(body: KitchenBody):
    """What an agent sees when it checks the inventory (used by the MCP check_inventory tool)."""
    return kitchen_for(kitchen_key(body)).report()


@app.post("/kitchen/service")
async def kitchen_service(body: KitchenBody):
    return {"used": kitchen_for(kitchen_key(body)).dinner_service()}


@app.post("/kitchen/reset")
async def kitchen_reset(body: KitchenBody):
    kitchen_for(kitchen_key(body)).reset()
    return {"ok": True}


@app.post("/run/kitchen")
async def run_kitchen(body: KitchenBody):
    key = kitchen_key(body)
    kitchen = kitchen_for(key)

    async def stream():
        if body.mode == "claude":
            async for event in run_events("Check the kitchen inventory and restock what is low.", key, GATEWAY,
                                          system=KITCHEN_SYSTEM, extra_env={"KITCHEN_URL": SELF_URL}):
                kitchen.track(event)
                yield event
            return
        queue: asyncio.Queue = asyncio.Queue()
        client = TTAPClient(GATEWAY, key, via="rest:kitchen-bot")

        async def emit(event: dict) -> None:
            kitchen.track(event)
            await queue.put(event)

        async def drive():
            try:
                await restock(client, kitchen, emit)
            except Exception as exc:  # surfaced in the console
                await queue.put({"type": "error", "text": f"{type(exc).__name__}: {exc}"})
            finally:
                await client.aclose()
                await queue.put({"type": "done"})

        yield {"type": "start", "model": "rule-based restock agent (no LLM)", "tools": ["check_inventory", "REST"]}
        task = asyncio.create_task(drive())
        while (event := await queue.get())["type"] != "done":
            yield event
        await task
        yield {"type": "done"}
    return ndjson(stream())

