from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ttap.domain.models import Candidate, Mandate, OriginAssurance, StockStatus

ZERO = Decimal("0")


UNLIMITED_MONEY = Decimal("1000000000000")
UNLIMITED_COUNT = 1_000_000


def build_decision_context(candidates: list[Candidate], mandate: Mandate | None, now: datetime,
                           committed_spend: Decimal = ZERO, orders_last_hour: int = 0) -> dict:
    total = sum((c.line_total_net for c in candidates), ZERO)
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
        "data_stale": any(c.stale for c in candidates),
        "period_spend_net": committed_spend + total,
        "period_budget_net": (mandate.period_budget_net if mandate and mandate.period_budget_net is not None
                              else UNLIMITED_MONEY),
        "orders_last_hour": orders_last_hour + 1,
        "max_orders_per_hour": (mandate.max_orders_per_hour if mandate and mandate.max_orders_per_hour is not None
                                else UNLIMITED_COUNT),
    }
