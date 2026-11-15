from __future__ import annotations

from decimal import Decimal

from ttap.domain.models import CatalogProduct, Need, OriginAssurance, StockStatus, UpstreamAvailability

UNKNOWN_SUPPLIER_STOCK_SENTINEL = Decimal("999999")
UNLIMITED_SENTINEL = Decimal("9999999999")


def stock_status(av: UpstreamAvailability | None) -> StockStatus:
    if (av is None or av.sales_block or av.available_amount is None
            or av.available_amount <= 0 or av.available_date is None):
        return StockStatus.UNAVAILABLE
    if av.available_amount >= UNLIMITED_SENTINEL:
        return StockStatus.VERIFIED_UNLIMITED
    if av.available_amount == UNKNOWN_SUPPLIER_STOCK_SENTINEL:
        return StockStatus.UNKNOWN_SUPPLIER_STOCK
    return StockStatus.VERIFIED_QTY


def origin_assurance(p: CatalogProduct) -> tuple[OriginAssurance, list[str]]:
    valio = p.origin_valio
    manufacturer = set(p.origin_manufacturer)
    if not valio and not manufacturer:
        return OriginAssurance.MISSING, []
    if valio and manufacturer:
        status = OriginAssurance.CONSISTENT if valio in manufacturer else OriginAssurance.CONFLICT
        return status, sorted({valio} | manufacturer)
    return OriginAssurance.SINGLE_SOURCE, sorted({valio} if valio else manufacturer)


def need_violation(p: CatalogProduct, need: Need) -> str | None:
    hard = [*need.required_claims, *need.excluded_allergens, *need.required_labels]
    if hard and not p.has_classification_data:
        return f"NOT_VERIFIABLE:{hard[0]}"
    for claim in need.required_claims:
        if claim not in p.claims:
            return f"CLAIM_MISSING:{claim}"
    for allergen in need.excluded_allergens:
        if allergen in p.allergens_contained:
            return f"ALLERGEN_PRESENT:{allergen}"
    for label in need.required_labels:
        if label not in p.labels:
            return f"LABEL_MISSING:{label}"
    return None
