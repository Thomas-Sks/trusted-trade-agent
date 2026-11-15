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
from pydantic import BaseModel

from buyer_agent.reference_agent import run_events
from buyer_agent.replenishment_bot import DEMO_PAR_LEVELS, replenish
from buyer_agent.ttap_client import TTAPClient

GATEWAY = os.environ.get("TTAP_URL", "http://localhost:8811")
KEYS = {"hotel": os.environ.get("KEY_AGENT_HOTEL", "demo-key-hotel-a"),
        "resto": os.environ.get("KEY_AGENT_RESTO", "demo-key-resto-b")}
app = FastAPI(title="TTAP buyer agents")


class RunBody(BaseModel):
    org: str = "hotel"
    text: str = ""


def ndjson(stream):
    async def gen():
        async for event in stream:
            yield json.dumps(event, default=str) + "\n"
    return StreamingResponse(gen(), media_type="application/x-ndjson")


@app.post("/run/claude")
async def run_claude(body: RunBody):
    return ndjson(run_events(body.text, KEYS[body.org], GATEWAY))


@app.post("/run/bot")
async def run_bot(body: RunBody):
    async def stream():
        queue: asyncio.Queue = asyncio.Queue()
        client = TTAPClient(GATEWAY, KEYS[body.org], via="rest:replenishment-bot")

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
