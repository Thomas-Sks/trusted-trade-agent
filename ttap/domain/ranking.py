from __future__ import annotations

from decimal import Decimal

from ttap.domain.assurance import need_violation, origin_assurance, stock_status
from ttap.domain.models import (
    CatalogProduct, Candidate, Delivery, Exclusion, OfferLine, RequestLine, StockStatus, Unit,
    UpstreamAvailability, UpstreamPrice,
)
from ttap.domain.quantities import content_per_sales_unit, sales_units_needed

CENT = Decimal("0.01")


def evaluate_candidate(p: CatalogProduct, line: RequestLine, price: UpstreamPrice | None,
                       av: UpstreamAvailability | None, delivery: Delivery) -> Candidate | Exclusion:
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
    if unit == Unit.PIECE:
        content, source = Decimal("1"), "name"
    else:
        found = content_per_sales_unit(p, unit, price.unit_net, price.comparison_net)
        if found is None:
            return Exclusion(product_id=p.product_id, reason="CONTENT_UNKNOWN")
        content, source = found
    qty = sales_units_needed(line.quantity.value, content, p.lot_size)
    if status == StockStatus.VERIFIED_QTY and av.available_amount is not None and av.available_amount < qty:
        return Exclusion(product_id=p.product_id, reason=f"INSUFFICIENT_STOCK:{av.available_amount.normalize():f}")
    origin, origins = origin_assurance(p)
    changes: list[str] = []
    if line.preferences.origin and not set(origins) & set(line.preferences.origin):
        changes.append(f"origin:{'/'.join(origins) or 'unknown'}")
    if line.preferences.brands and p.brand not in line.preferences.brands:
        changes.append(f"brand:{p.brand}")
    label_hits = len(set(line.preferences.labels) & p.labels)
    verified_bonus = 0.5 if status in (StockStatus.VERIFIED_QTY, StockStatus.VERIFIED_UNLIMITED) else 0.0
    return Candidate(
        product_id=p.product_id, name=p.display_name(), qty_sales_units=qty, sales_unit=p.sales_unit,
        content_per_sales_unit=content, content_source=source, surplus=qty * content - line.quantity.value,
        unit_net=price.unit_net, line_total_net=(price.unit_net * qty).quantize(CENT),
        vat_rate=price.vat_rate or Decimal("0"),
        comparison_net=price.comparison_net if price.comparison_net is not None else price.unit_net,
        price_valid_to=price.valid_to, stock=status, available_amount=av.available_amount,
        delivery_date=av.available_date, order_cutoff=av.closing_time, origin=origin, origins=origins,
        changes_vs_request=changes, score=label_hits + verified_bonus,
    )


def build_offer_line(line: RequestLine, products: list[CatalogProduct], prices: dict[str, UpstreamPrice],
                     avail: dict[str, UpstreamAvailability], delivery: Delivery) -> OfferLine:
    candidates: list[Candidate] = []
    excluded: list[Exclusion] = []
    for p in products:
        result = evaluate_candidate(p, line, prices.get(p.product_id), avail.get(p.product_id), delivery)
        (candidates if isinstance(result, Candidate) else excluded).append(result)
    tiers: dict[str, Candidate] = {}
    if candidates:
        by_price = sorted(candidates, key=lambda c: (c.comparison_net, c.product_id))
        tiers["good"] = by_price[0]
        preferred = [c for c in by_price if not c.changes_vs_request]
        if preferred:
            tiers["better"] = preferred[0]
            tiers["best"] = sorted(preferred, key=lambda c: (-c.score, c.comparison_net, c.product_id))[0]
    return OfferLine(line_id=line.line_id, tiers=tiers, excluded=excluded,
                     exceptions=[] if candidates else ["NO_ELIGIBLE_PRODUCT"])
