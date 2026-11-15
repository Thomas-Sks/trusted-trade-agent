"""Live smoke test against the Valio mock API. Run: uv run --env-file .env python scripts/smoke_milk.py"""
import asyncio
from datetime import date
from decimal import Decimal

from ttap.bootstrap import build_live
from ttap.domain.models import Delivery, Need, Quantity, RequestLine, SelectedLine, Unit

MONDAY = date(2026, 11, 16)


async def run(litres: str, key: str) -> None:
    services, _ = build_live()
    req = services.requests.create("org_hotel_a", [RequestLine(
        line_id="L1", need=Need(text="lactose free milk", required_claims=["FREE_FROM_LACTOSE"]),
        quantity=Quantity(value=Decimal(litres), unit=Unit.L))],
        Delivery(requested_date=MONDAY, latest_acceptable_date=MONDAY))
    offer = await services.lookup.lookup("org_hotel_a", req.request_id)
    line = offer.lines[0]
    for tier, c in line.tiers.items():
        print(f"{tier:6} {c.product_id} {c.name[:50]:50} {c.qty_sales_units} {c.sales_unit} "
              f"{c.comparison_net} EUR/L total {c.line_total_net} stock {c.stock}")
    print(f"excluded: {len(line.excluded)}  valid_until: {offer.valid_until}")
    order = services.orders.place("org_hotel_a", offer.offer_id, [SelectedLine(line_id="L1", tier="good")], key)
    print("ORDER", order.state, order.total_net, order.decision.rules_fired)


if __name__ == "__main__":
    asyncio.run(run("1000", "smoke-1000"))
    asyncio.run(run("3000", "smoke-3000"))
