from __future__ import annotations

import re
from decimal import ROUND_CEILING, Decimal

from ttap.domain.models import CatalogProduct, Unit

_QTY_RE = re.compile(r"(?<![\d.,])(\d+(?:[.,]\d+)?)\s*(dl|cl|ml|kg|l|g)\b", re.IGNORECASE)
_MULTI_RE = re.compile(r"\b(\d+)\s*[x×]\s", re.IGNORECASE)
_FACTORS: dict[str, tuple[Decimal, Unit]] = {
    "l": (Decimal("1"), Unit.L), "dl": (Decimal("0.1"), Unit.L), "cl": (Decimal("0.01"), Unit.L),
    "ml": (Decimal("0.001"), Unit.L), "kg": (Decimal("1"), Unit.KG), "g": (Decimal("0.001"), Unit.KG),
}
TOLERANCE = Decimal("0.05")


def parse_name_quantity(name: str) -> tuple[Decimal, Unit] | None:
    match = _QTY_RE.search(name)
    if not match:
        return None
    factor, unit = _FACTORS[match.group(2).lower()]
    return Decimal(match.group(1).replace(",", ".")) * factor, unit


def content_per_sales_unit(product: CatalogProduct, requested_unit: Unit,
                           unit_net: Decimal | None, comparison_net: Decimal | None) -> tuple[Decimal, str] | None:
    ratio = unit_net / comparison_net if unit_net and comparison_net and comparison_net > 0 else None
    candidates: set[Decimal] = set()
    parsed = parse_name_quantity(product.display_name())
    if parsed and parsed[1] == requested_unit:
        single = parsed[0]
        candidates.add(single)
        sales, base = product.units.get(product.sales_unit), product.units.get(product.base_unit)
        if sales and base:
            candidates.add(single * sales / base)
        multi = _MULTI_RE.search(product.display_name())
        if multi:
            candidates.add(single * Decimal(multi.group(1)))
    if ratio is not None:
        if candidates:
            best = min(candidates, key=lambda c: abs(c - ratio))
            if abs(best - ratio) <= ratio * TOLERANCE:
                return best, "name"
        return ratio.quantize(Decimal("0.01")), "price_ratio"
    if len(candidates) == 1:
        return candidates.pop(), "name"
    return None


def sales_units_needed(requested: Decimal, content: Decimal, lot_size: Decimal) -> Decimal:
    steps = (requested / content / lot_size).to_integral_value(rounding=ROUND_CEILING)
    return steps * lot_size
