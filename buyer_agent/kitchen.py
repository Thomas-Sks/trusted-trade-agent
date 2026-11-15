"""A small restaurant kitchen on the BUYER side: its inventory, and an agent that restocks it through TTAP.

The inventory belongs to the restaurant, not to the wholesaler. The restock agent reads it, orders what is below
its reorder point (one order per supplier category, as kitchens do), and the wholesaler's mandate engine decides each
order. The agent never decides an approval; it reports what the mandate decided.

Item status follows the chain request (products) → offer → order from self-describing tool results, then reads the
order's live state from the gateway, so it works the same whether Claude or the rule-based bot placed the order.
"""
from __future__ import annotations

import copy
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import ROUND_CEILING, Decimal

from buyer_agent.ttap_client import OfferNotTrusted, TTAPClient, TTAPError

DELIVERY = date(2026, 11, 16)
TIER_PREFERENCE = ("better", "good")


@dataclass
class Item:
    key: str
    label: str            # the kitchen's own name for it
    category: str         # supplier category: one order per category
    product_id: str       # the restaurant's usual product at the wholesaler
    unit: str             # L | KG | PIECE
    on_hand: float
    reorder_point: float
    par: float            # stock level to restock up to
    use_per_service: float

    def low(self) -> bool:
        return self.on_hand < self.reorder_point

    def to_order(self) -> float:
        return float(Decimal(str(self.par - self.on_hand)).quantize(Decimal("1"), rounding=ROUND_CEILING))


# A mini restaurant. Product ids are just the restaurant's usual products; nothing in TTAP depends on them.
# Sized so that, however many services run, each category order stays under a bistro's €800 per-order limit: the only
# order that needs a human is the one containing supplier-held cream that Valio cannot verify (> the €200 allowance).
TEMPLATE = [
    Item("milk", "Lactose-free milk", "Dairy", "464306", "L", 14, 30, 80, 9),
    Item("butter", "Butter 500 g", "Dairy", "464411", "PIECE", 9, 8, 24, 3),
    Item("cream", "Cooking cream 10 L (supplier direct)", "Dairy", "464396", "PIECE", 1, 3, 8, 1),
    Item("tomatoes", "Cherry tomatoes", "Produce", "462545", "KG", 3, 8, 24, 3),
    Item("lettuce", "Iceberg lettuce", "Produce", "460026", "PIECE", 4, 10, 30, 6),
    Item("basil", "Basil bunch", "Produce", "460362", "PIECE", 12, 6, 16, 2),
    Item("lemons", "Lemons", "Produce", "460846", "KG", 2, 3, 8, 1),
    Item("chicken", "Chicken breast fillet", "Meat & fish", "462281", "KG", 4, 8, 20, 3),
    Item("salmon", "Salmon fillet", "Meat & fish", "462150", "KG", 7, 5, 14, 2),
]


DELIVERED = ("AUTO_APPROVED", "APPROVED")


@dataclass
class Kitchen:
    items: list[Item] = field(default_factory=lambda: copy.deepcopy(TEMPLATE))
    services: int = 0
    request_lines: dict[str, dict[str, float]] = field(default_factory=dict)   # request_id -> {product_id: qty}
    offer_lines: dict[str, dict[str, float]] = field(default_factory=dict)     # offer_id -> {product_id: qty}
    orders: dict[str, dict[str, float]] = field(default_factory=dict)          # order_id -> {product_id: qty}
    received: list[str] = field(default_factory=list)                          # order_ids already in stock

    def reset(self) -> None:
        self.items = copy.deepcopy(TEMPLATE)
        self.services = 0
        self.request_lines.clear(); self.offer_lines.clear(); self.orders.clear(); self.received.clear()
        save()

    def track(self, event: dict) -> None:
        """Follow request -> offer -> order from tool results; each result names its own ids."""
        if event.get("type") != "tool_result" or not isinstance(event.get("result"), dict):
            return
        r, tool = event["result"], event.get("tool")
        if tool == "create_request" and r.get("request_id"):
            self.request_lines[r["request_id"]] = {
                ln["need"]["product_id"]: float(ln["quantity"]["value"]) for ln in r.get("lines", [])
                if ln.get("need", {}).get("product_id") and ln.get("quantity")}
        elif tool == "lookup" and r.get("offer_id") and r.get("request_id"):
            self.offer_lines[r["offer_id"]] = self.request_lines.get(r["request_id"], {})
        elif tool == "place_order" and r.get("order_id") and r.get("offer_id"):
            self.orders[r["order_id"]] = self.offer_lines.get(r["offer_id"], {})
        save()

    def dinner_service(self) -> list[str]:
        self.services += 1
        used = []
        for it in self.items:
            take = min(it.on_hand, it.use_per_service)
            it.on_hand = round(it.on_hand - take, 2)
            used.append(f"{it.label}: −{take:g} {it.unit}")
        save()
        return used

    def receive(self, live_orders: list[dict]) -> list[str]:
        """Deliveries arrive: approved orders not yet received go into stock."""
        state = {o["order_id"]: o["state"] for o in live_orders}
        by_pid = {it.product_id: it for it in self.items}
        got = []
        for oid, lines in self.orders.items():
            if oid in self.received or state.get(oid) not in DELIVERED:
                continue
            for pid, qty in lines.items():
                if pid in by_pid:
                    by_pid[pid].on_hand = round(by_pid[pid].on_hand + qty, 2)
                    got.append(f"{by_pid[pid].label}: +{qty:g} {by_pid[pid].unit}")
            self.received.append(oid)
        save()
        return got

    def low_items(self) -> list[Item]:
        return [it for it in self.items if it.low()]

    def report(self) -> dict:
        """What an agent sees when it checks the inventory. Items already on order are not low any more."""
        pending = self._open_products()
        return {"delivery_date": DELIVERY.isoformat(),
                "low": [{"category": it.category, "item": it.label, "product_id": it.product_id,
                         "on_hand": it.on_hand, "reorder_point": it.reorder_point, "par": it.par,
                         "order_quantity": it.to_order(), "unit": it.unit}
                        for it in self.low_items() if it.product_id not in pending],
                "already_on_order": [it.label for it in self.low_items() if it.product_id in pending],
                "ok": [f"{it.label}: {it.on_hand:g} {it.unit} ≥ reorder point {it.reorder_point:g}"
                       for it in self.items if not it.low()]}

    def _open_products(self) -> set[str]:
        return {pid for oid, lines in self.orders.items() if oid not in self.received for pid in lines}

    def state(self, live_orders: list[dict]) -> dict:
        """Inventory with, per item, its open order (if any) and the order's live state at the wholesaler."""
        by_id = {o["order_id"]: o for o in live_orders}
        by_pid = {it.product_id: it for it in self.items}

        def view(oid: str) -> dict | None:
            o = by_id.get(oid)
            if o is None:
                return None
            lines = self.orders[oid]
            return {"order_id": oid, "state": o["state"], "total_net": o["total_net"],
                    "rules_fired": (o.get("decision") or {}).get("rules_fired", []),
                    "approved_by": o.get("approved_by"), "received": oid in self.received,
                    "category": next((by_pid[p].category for p in lines if p in by_pid), ""),
                    "items": [f"{by_pid[p].label} {q:g} {by_pid[p].unit}" for p, q in lines.items() if p in by_pid]}
        open_order: dict[str, str] = {}
        for oid, lines in self.orders.items():  # insertion order: later orders win
            if oid not in self.received:
                for pid in lines:
                    open_order[pid] = oid
        items = [{**asdict(it), "low": it.low(), "order_quantity": it.to_order(),
                  "incoming": self.orders.get(open_order.get(it.product_id, ""), {}).get(it.product_id, 0),
                  "order": view(open_order[it.product_id]) if it.product_id in open_order else None}
                 for it in self.items]
        return {"items": items, "services": self.services,
                "orders": [v for oid in self.orders if (v := view(oid))]}


KITCHENS: dict[str, Kitchen] = {}
STATE_FILE = os.environ.get("KITCHEN_STATE")  # survives agent-service restarts when set


def save() -> None:
    if not STATE_FILE:
        return
    data = {k: {**asdict(v), "items": [asdict(i) for i in v.items]} for k, v in KITCHENS.items()}
    tmp = f"{STATE_FILE}.tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, STATE_FILE)


def load() -> None:
    if not STATE_FILE or not os.path.exists(STATE_FILE):
        return
    with open(STATE_FILE) as f:
        for key, v in json.load(f).items():
            KITCHENS[key] = Kitchen(items=[Item(**i) for i in v["items"]], services=v["services"],
                                    request_lines=v["request_lines"], offer_lines=v["offer_lines"],
                                    orders=v["orders"], received=v["received"])


def kitchen_for(agent_key: str) -> Kitchen:
    return KITCHENS.setdefault(agent_key, Kitchen())


load()


async def restock(client: TTAPClient, kitchen: Kitchen, emit) -> None:
    """Rule-based restock agent (no LLM): same protocol, same mandate as the Claude agent."""
    await emit({"type": "tool_call", "tool": "check_inventory", "input": {}})
    report = kitchen.report()
    await emit({"type": "tool_result", "tool": "check_inventory", "result": report})
    if not report["low"]:
        await emit({"type": "text", "text": "Every item is at or above its reorder point. Nothing to order."})
        return
    by_cat: dict[str, list[dict]] = {}
    for row in report["low"]:
        by_cat.setdefault(row["category"], []).append(row)
    outcomes = []
    for cat, rows in by_cat.items():
        lines = [{"line_id": f"L{i + 1}", "need": {"text": r["item"], "product_id": r["product_id"]},
                  "quantity": {"value": str(r["order_quantity"]), "unit": r["unit"]}}
                 for i, r in enumerate(rows)]
        await emit({"type": "text", "text": f"{cat}: {len(rows)} item(s) below reorder point → one order."})
        try:
            await emit({"type": "tool_call", "tool": "create_request", "input": {"lines": lines}})
            rq = await client.create_request(lines, DELIVERY.isoformat(), DELIVERY.isoformat())
            await emit({"type": "tool_result", "tool": "create_request", "result": rq})
            await emit({"type": "tool_call", "tool": "lookup", "input": {"request_id": rq["request_id"]}})
            offer = await client.lookup(rq["request_id"])  # raises if the signature does not verify
            await emit({"type": "tool_result", "tool": "lookup", "result": offer})
            selected = []
            for ln in offer["lines"]:
                tier = next((t for t in TIER_PREFERENCE if t in ln["tiers"]), "split" if ln["split"] else None)
                if tier:
                    selected.append({"line_id": ln["line_id"], "tier": tier})
            if not selected:
                await emit({"type": "text", "text": f"{cat}: no eligible offer."})
                continue
            await emit({"type": "tool_call", "tool": "place_order", "input": {"offer_id": offer["offer_id"],
                                                                             "selected": selected}})
            order = await client.place_order(offer["offer_id"], selected)
            await emit({"type": "tool_result", "tool": "place_order", "result": order})
            outcomes.append((cat, order))
        except OfferNotTrusted as exc:
            await emit({"type": "error", "text": f"{cat}: offer rejected, signature does not verify ({exc})"})
        except TTAPError as exc:
            await emit({"type": "error", "text": f"{cat}: {exc.code}: {exc.body.get('detail')}"})
    auto = sum(1 for _, o in outcomes if o["state"] == "AUTO_APPROVED")
    summary = "; ".join(f"{c} €{o['total_net']} → {o['state'].replace('_', ' ').lower()}"
                        + (f" ({', '.join(o['decision']['rules_fired'])})" if o.get("decision") and
                           o["decision"]["rules_fired"] else "") for c, o in outcomes)
    await emit({"type": "text", "text": f"Placed {len(outcomes)} order(s), {auto} without a human. {summary}."})
