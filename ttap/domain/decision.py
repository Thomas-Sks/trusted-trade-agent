from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ttap.domain.models import Candidate, Mandate, OriginAssurance, StockStatus

ZERO = Decimal("0")


def build_decision_context(candidates: list[Candidate], mandate: Mandate | None, now: datetime) -> dict:
    return {
        "mandate_active": mandate is not None and mandate.status == "active" and now < mandate.valid_until,
        "total_net": sum((c.line_total_net for c in candidates), ZERO),
        "limit_per_order_net": mandate.limit_per_order_net if mandate else ZERO,
        "unverified_value_net": sum(
            (c.line_total_net for c in candidates if c.stock == StockStatus.UNKNOWN_SUPPLIER_STOCK), ZERO),
        "max_unverified_value_net": mandate.max_unverified_value_net if mandate else ZERO,
        "has_origin_conflict": any(c.origin == OriginAssurance.CONFLICT for c in candidates),
        "has_changes_vs_request": any(c.changes_vs_request for c in candidates),
        "has_partial": any(c.partial for c in candidates),
    }
