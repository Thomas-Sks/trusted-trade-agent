"""Approval card: raw facts, triggered rules and deviation from usual behaviour — no LLM advocacy."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ttap.domain.explain import explain_rules
from ttap.domain.offer import resolve_selection
from ttap.domain.models import (
    ApprovalCard, Candidate, CardLine, Mandate, Offer, Order, OriginAssurance, StockStatus,
)

CENT = Decimal("0.01")
HIGH_RATIO = Decimal("1.5")
LOW_RATIO = Decimal("0.5")


def selected_candidates(order: Order, offer: Offer) -> list[Candidate]:
    return resolve_selection(offer, order.selected)


def _vs_usual(c: Candidate, mandate: Mandate | None) -> str | None:
    if mandate is None or not mandate.usual_list:
        return None
    usual = {u.product_id: u.median_qty for u in mandate.usual_list}
    if c.product_id not in usual:
        return "nouveau produit"
    median = usual[c.product_id]
    if median <= 0:
        return None
    ratio = c.qty_sales_units / median
    if ratio >= HIGH_RATIO or ratio <= LOW_RATIO:
        return f"×{ratio.quantize(Decimal('0.1'))} vs habitude"
    return None


def build_card(order: Order, offer: Offer, mandate: Mandate | None, now: datetime) -> ApprovalCard:
    cands = selected_candidates(order, offer)
    warnings: list[str] = []
    unverified = sum((c.line_total_net for c in cands if c.stock == StockStatus.UNKNOWN_SUPPLIER_STOCK), Decimal(0))
    if unverified:
        warnings.append(f"stock fournisseur non vérifié pour {unverified} € HT")
    for c in cands:
        if c.origin == OriginAssurance.CONFLICT:
            warnings.append(f"origine contradictoire ({'/'.join(c.origins)}) : {c.name}")
    lines_by_id = {line.line_id: line for line in offer.lines}
    for sel in order.selected:
        line = lines_by_id[sel.line_id]
        if sel.tier == "split" and line.backorder_qty > 0:
            warnings.append(f"reliquat non couvert : {line.backorder_qty.normalize():f} (unité demandée)")
    cutoffs = [c.order_cutoff for c in cands if c.order_cutoff is not None]
    minutes = int((min(cutoffs) - now).total_seconds() // 60) if cutoffs else None
    gross = sum((c.line_total_net * (1 + c.vat_rate / 100) for c in cands), Decimal(0)).quantize(CENT)
    decision = order.decision
    return ApprovalCard(
        order_id=order.order_id, org_id=order.org_id, version=order.version,
        offer_hash_short=order.offer_hash.removeprefix("sha256:")[:8],
        total_net=order.total_net, total_gross=gross,
        reasons=explain_rules(decision.rules_fired, decision.context) if decision else [],
        lines=[CardLine(name=c.name, partial=c.partial, is_substitute=c.is_substitute, qty_sales_units=c.qty_sales_units, sales_unit=c.sales_unit,
                        unit_net=c.unit_net, line_total_net=c.line_total_net, stock=c.stock,
                        changes=c.changes_vs_request, vs_usual=_vs_usual(c, mandate)) for c in cands],
        warnings=warnings,
        delivery_date=min((c.delivery_date for c in cands), default=None),
        minutes_to_cutoff=minutes,
        step_up_required=mandate is not None and order.total_net > mandate.step_up_above_net,
    )


def render_card_text(card: ApprovalCard) -> str:
    rows = [f"🟠 Approbation requise — {card.org_id} · commande {card.order_id} · offre {card.offer_hash_short}",
            "Bloqué par :"]
    rows += [f" • {r}" for r in card.reasons] or [" • (aucune règle)"]
    rows.append("Lignes :")
    for line in card.lines:
        extra = [x for x in (line.vs_usual, *line.changes) if x]
        rows.append(f" • {line.qty_sales_units} {line.sales_unit} {line.name} — {line.line_total_net} € HT"
                    + (f" ({', '.join(extra)})" if extra else ""))
    if card.warnings:
        rows.append("Alertes : " + " · ".join(card.warnings))
    rows.append(f"Total {card.total_net} € HT / {card.total_gross} € TTC")
    if card.delivery_date:
        cutoff = f" — heure limite dans {card.minutes_to_cutoff} min" if card.minutes_to_cutoff is not None else ""
        rows.append(f"Livraison {card.delivery_date.isoformat()}{cutoff}")
    if card.step_up_required:
        rows.append("🔐 Montant élevé : approbation via la page web uniquement")
    return "\n".join(rows)
