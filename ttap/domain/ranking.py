"""Deterministic, product-agnostic response logic: candidate evaluation, good/better/best, partial fulfilment."""
from __future__ import annotations

from datetime import datetime
from decimal import ROUND_FLOOR, Decimal

from ttap.domain.assurance import need_violation, origin_assurance, stock_status
from ttap.domain.models import (
    CatalogProduct, Candidate, Delivery, Exclusion, OfferLine, RequestLine, StockStatus, Unit,
    UpstreamAvailability, UpstreamPrice,
)
from ttap.domain.quantities import content_per_sales_unit, sales_units_needed

CENT = Decimal("0.01")
ZERO = Decimal("0")
DEFAULT_RELIABILITY = Decimal("0.9")
NO_CARBON = Decimal("1e9")


def best_key(c: Candidate) -> tuple:
    """Quality first (labels, stock certainty, delivery reliability, lower carbon), then price — all generic."""
    reliability = c.reliability if c.reliability is not None else DEFAULT_RELIABILITY
    carbon = c.carbon_kg_per_kg if c.carbon_kg_per_kg is not None else NO_CARBON
    return (-c.score, -reliability, carbon, c.comparison_net, c.product_id)


def _floor_to_lot(value: Decimal, lot: Decimal) -> Decimal:
    return (value / lot).to_integral_value(rounding=ROUND_FLOOR) * lot


def _changes(p: CatalogProduct, origins: list[str], line: RequestLine, requested: CatalogProduct | None) -> list[str]:
    changes: list[str] = []
    if requested is not None and p.product_id != requested.product_id:
        changes.append(f"substitute:{requested.product_id}")
        if not line.preferences.origin:
            requested_origins = set(origin_assurance(requested)[1])
            if requested_origins and not set(origins) & requested_origins:
                changes.append(f"origin:{'/'.join(origins) or 'unknown'}")
    if line.preferences.origin and not set(origins) & set(line.preferences.origin):
        changes.append(f"origin:{'/'.join(origins) or 'unknown'}")
    if line.preferences.brands and p.brand not in line.preferences.brands:
        changes.append(f"brand:{p.brand}")
    return changes


def evaluate_candidate(p: CatalogProduct, line: RequestLine, price: UpstreamPrice | None,
                       av: UpstreamAvailability | None, delivery: Delivery, *, now: datetime | None = None,
                       requested: CatalogProduct | None = None) -> Candidate | Exclusion:
    is_substitute = requested is not None and p.product_id != requested.product_id
    if is_substitute and line.substitution == "no_substitute":
        return Exclusion(product_id=p.product_id, reason="SUBSTITUTION_NOT_ALLOWED")
    reason = need_violation(p, line.need)
    if reason:
        return Exclusion(product_id=p.product_id, reason=reason)
    if price is None or price.error or price.unit_net is None:
        return Exclusion(product_id=p.product_id, reason="NO_PRICE")
    unit = line.quantity.unit
    if unit != Unit.PIECE and price.comparison_unit != unit.value:
        return Exclusion(product_id=p.product_id, reason="COMPARISON_UNIT_MISMATCH")
    status = stock_status(av)
    if status == StockStatus.UNAVAILABLE:
        return Exclusion(product_id=p.product_id, reason="UNAVAILABLE")
    assert av is not None and av.available_date is not None
    if av.available_date > delivery.latest_acceptable_date:
        return Exclusion(product_id=p.product_id, reason="DELIVERY_TOO_LATE")
    if now is not None and av.closing_time is not None and av.closing_time <= now:
        return Exclusion(product_id=p.product_id, reason="CUTOFF_PASSED")
    if unit == Unit.PIECE:
        content, source = Decimal("1"), "name"
    else:
        found = content_per_sales_unit(p, unit, price.unit_net, price.comparison_net)
        if found is None:
            return Exclusion(product_id=p.product_id, reason="CONTENT_UNKNOWN")
        content, source = found
    qty = sales_units_needed(line.quantity.value, content, p.lot_size)
    partial, missing = False, ZERO
    if status == StockStatus.VERIFIED_QTY and av.available_amount is not None and av.available_amount < qty:
        qty = _floor_to_lot(av.available_amount, p.lot_size)
        if qty <= 0:
            return Exclusion(product_id=p.product_id, reason="INSUFFICIENT_STOCK:0")
        partial, missing = True, line.quantity.value - qty * content
    origin, origins = origin_assurance(p)
    label_hits = len(set(line.preferences.labels) & p.labels)
    verified_bonus = 0.5 if status in (StockStatus.VERIFIED_QTY, StockStatus.VERIFIED_UNLIMITED) else 0.0
    return Candidate(
        product_id=p.product_id, name=p.display_name(), qty_sales_units=qty, sales_unit=p.sales_unit,
        content_per_sales_unit=content, content_source=source,
        surplus=ZERO if partial else qty * content - line.quantity.value,
        unit_net=price.unit_net, line_total_net=(price.unit_net * qty).quantize(CENT),
        vat_rate=price.vat_rate or ZERO,
        comparison_net=price.comparison_net if price.comparison_net is not None else price.unit_net,
        price_valid_to=price.valid_to, stock=status, available_amount=av.available_amount,
        delivery_date=av.available_date, order_cutoff=av.closing_time, origin=origin, origins=origins,
        changes_vs_request=_changes(p, origins, line, requested), score=label_hits + verified_bonus,
        reliability=p.reliability, carbon_kg_per_kg=p.carbon_kg_per_kg, is_substitute=is_substitute,
        partial=partial, missing_qty=missing, lot_size=p.lot_size,
        upstream_available=(av.available_amount + av.reserved) if av.available_amount is not None else None,
    )


def _rescale(c: Candidate, remaining: Decimal) -> Candidate:
    """Take only what is needed from c to cover `remaining` (requested unit), within its known stock."""
    units = sales_units_needed(remaining, c.content_per_sales_unit, c.lot_size)
    capped = False
    if c.stock == StockStatus.VERIFIED_QTY and c.available_amount is not None and units > c.available_amount:
        units, capped = _floor_to_lot(c.available_amount, c.lot_size), True
    covered = units * c.content_per_sales_unit
    return c.model_copy(update={
        "qty_sales_units": units, "line_total_net": (c.unit_net * units).quantize(CENT),
        "partial": capped, "missing_qty": max(remaining - covered, ZERO),
        "surplus": max(covered - remaining, ZERO)})


def build_split(line: RequestLine, primary: Candidate | None, pool: list[Candidate]) -> tuple[list[Candidate], Decimal]:
    """Partial primary first, then official substitutes, then other candidates by price; rest is backordered."""
    plan: list[Candidate] = []
    remaining = line.quantity.value
    if primary is not None:
        plan.append(primary)
        remaining -= primary.qty_sales_units * primary.content_per_sales_unit
    if line.substitution != "no_substitute":
        others = sorted((c for c in pool if primary is None or c.product_id != primary.product_id),
                        key=lambda c: (not c.is_substitute, c.comparison_net, c.product_id))
        for c in others:
            if remaining <= 0:
                break
            piece = _rescale(c, remaining)
            if piece.qty_sales_units > 0:
                plan.append(piece)
                remaining -= piece.qty_sales_units * piece.content_per_sales_unit
    return plan, max(remaining, ZERO)


def build_offer_line(line: RequestLine, products: list[CatalogProduct], prices: dict[str, UpstreamPrice],
                     avail: dict[str, UpstreamAvailability], delivery: Delivery, *, now: datetime | None = None,
                     requested: CatalogProduct | None = None) -> OfferLine:
    candidates: list[Candidate] = []
    excluded: list[Exclusion] = []
    for p in products:
        result = evaluate_candidate(p, line, prices.get(p.product_id), avail.get(p.product_id), delivery,
                                    now=now, requested=requested)
        (candidates if isinstance(result, Candidate) else excluded).append(result)
    full = [c for c in candidates if not c.partial]
    partials = [c for c in candidates if c.partial]
    tiers: dict[str, Candidate] = {}
    if full:
        by_price = sorted(full, key=lambda c: (c.comparison_net, c.product_id))
        tiers["good"] = by_price[0]
        preferred = [c for c in by_price if not c.changes_vs_request]
        if preferred:
            tiers["better"] = preferred[0]
            tiers["best"] = sorted(preferred, key=best_key)[0]
    primary = None
    if requested is not None:
        primary = next((c for c in partials if c.product_id == requested.product_id), None)
    elif not full and partials:
        primary = sorted(partials, key=lambda c: (c.comparison_net, c.product_id))[0]
    split, backorder = (build_split(line, primary, candidates) if primary is not None else ([], ZERO))
    exceptions: list[str] = []
    if not candidates:
        exceptions.append("NO_ELIGIBLE_PRODUCT")
    if requested is not None and not any(c.product_id == requested.product_id for c in candidates):
        exceptions.append("REQUESTED_PRODUCT_UNAVAILABLE")
    if split:
        exceptions.append("PARTIAL_AVAILABILITY")
        if any(c.is_substitute for c in split):
            exceptions.append("SUBSTITUTED")
        if backorder > 0:
            exceptions.append("BACKORDER")
    return OfferLine(line_id=line.line_id, tiers=tiers, excluded=excluded, exceptions=exceptions,
                     split=split, backorder_qty=backorder)
