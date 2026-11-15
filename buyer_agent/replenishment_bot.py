"""Second, deliberately different TTAP client: a deterministic replenishment bot (no LLM), plain REST.

It proves the protocol is agent-agnostic: an ERP-style script and an LLM agent use the same gateway, the same
signed offers and are governed by the same mandate engine. Run:

    uv run python -m buyer_agent.replenishment_bot --key demo-key-resto-b --once
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import date, timedelta

from buyer_agent.ttap_client import OfferNotTrusted, TTAPClient, TTAPError

TIER_PREFERENCE = ("better", "good")


@dataclass
class ParLevel:
    product_id: str
    unit: str           # L | KG | PIECE
    reorder_below: float
    target: float
    on_hand: float      # would come from the restaurant's inventory system


async def replenish(client: TTAPClient, items: list[ParLevel], delivery: date, log=print) -> list[dict]:
    results = []
    for item in items:
        if item.on_hand >= item.reorder_below:
            log(f"· {item.product_id}: {item.on_hand} {item.unit} on hand ≥ {item.reorder_below}, nothing to do")
            continue
        qty = round(item.target - item.on_hand, 3)
        log(f"▶ {item.product_id}: {item.on_hand} {item.unit} < {item.reorder_below} → order {qty} {item.unit}")
        try:
            rq = await client.create_request(
                [{"line_id": "L1", "need": {"text": item.product_id, "product_id": item.product_id},
                  "quantity": {"value": str(qty), "unit": item.unit}, "substitution": "best_match"}],
                delivery.isoformat(), delivery.isoformat())
            offer = await client.lookup(rq["request_id"])            # raises if the signature does not verify
            line = offer["lines"][0]
            tier = next((t for t in TIER_PREFERENCE if t in line["tiers"]), "split" if line["split"] else None)
            if tier is None:
                log(f"  ✗ no eligible offer: {line['exceptions']}")
                results.append({"product_id": item.product_id, "state": "NO_OFFER"})
                continue
            order = await client.place_order(offer["offer_id"], [{"line_id": "L1", "tier": tier}])
            rules = (order.get("decision") or {}).get("rules_fired", [])
            log(f"  ✓ {order['order_id']} tier={tier} {order['total_net']} € → {order['state']}"
                + (f" ({', '.join(rules)})" if rules else ""))
            results.append(order)
        except OfferNotTrusted as exc:
            log(f"  ✗ offer rejected by the bot: {exc}")
            results.append({"product_id": item.product_id, "state": "OFFER_NOT_TRUSTED"})
        except TTAPError as exc:
            log(f"  ✗ {exc.code}: {exc.body.get('detail')}")
            results.append({"product_id": item.product_id, "state": exc.code})
    return results


DEMO_PAR_LEVELS = [
    ParLevel("464306", "L", reorder_below=60, target=200, on_hand=35),      # lactose-free milk 1 l
    ParLevel("462545", "KG", reorder_below=20, target=80, on_hand=8),       # cherry tomatoes 4 kg case
    ParLevel("461583", "PIECE", reorder_below=10, target=40, on_hand=25),   # ketchup: enough stock
]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--key", default="demo-key-resto-b")
    p.add_argument("--url", default="http://localhost:8811")
    p.add_argument("--delivery", default=(date(2026, 11, 12) + timedelta(days=4)).isoformat())
    p.add_argument("--once", action="store_true")
    p.add_argument("--every", type=float, default=60.0)
    a = p.parse_args()

    async def loop() -> None:
        client = TTAPClient(a.url, a.key, via="rest:replenishment-bot")
        while True:
            await replenish(client, DEMO_PAR_LEVELS, date.fromisoformat(a.delivery))
            if a.once:
                break
            await asyncio.sleep(a.every)
        await client.aclose()

    asyncio.run(loop())


if __name__ == "__main__":
    main()
