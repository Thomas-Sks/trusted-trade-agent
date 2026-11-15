"""Deterministic, template-based explanations. Never produced by an LLM."""
from __future__ import annotations

from ttap.domain.models import Offer, Order

RULE_TEXT: dict[str, str] = {
    "total_over_order_limit": "Total {total_net} € HT > plafond par commande {limit_per_order_net} €",
    "unverified_stock_over_limit": (
        "Stock fournisseur non vérifié pour {unverified_value_net} € HT > limite {max_unverified_value_net} €"),
    "origin_conflict": "Origine contradictoire entre Valio et le fabricant",
    "deviates_from_request": "Le choix s'écarte de la demande (origine ou marque)",
    "mandate_not_active": "Mandat inactif, suspendu ou expiré",
    "policy_evaluation_error": "Erreur d'évaluation des règles : refus par défaut",
}

OUTCOME_TEXT = {
    "AUTO_APPROVED": "approuvée automatiquement dans le mandat",
    "PENDING_HUMAN": "escaladée vers un approbateur humain",
    "DENIED": "refusée",
}


def explain_rules(rules: list[str], context: dict) -> list[str]:
    out = []
    for rule in rules:
        template = RULE_TEXT.get(rule)
        try:
            out.append(template.format(**context) if template else f"Règle déclenchée : {rule}")
        except (KeyError, IndexError):
            out.append(f"Règle déclenchée : {rule}")
    return out


def explain_decision(order: Order) -> str:
    if order.decision is None:
        return f"Commande {order.order_id} en attente de décision."
    base = (f"Commande {order.order_id} : {order.total_net} € HT, "
            f"{OUTCOME_TEXT[order.decision.outcome]}")
    reasons = explain_rules(order.decision.rules_fired, order.decision.context)
    return base + (" car : " + " ; ".join(reasons) if reasons else ".")


def explain_offer(offer: Offer) -> str:
    parts = []
    for line in offer.lines:
        good = line.tiers.get("good")
        if good is None:
            parts.append(f"{line.line_id} : aucun produit éligible ({len(line.excluded)} exclus)")
        else:
            parts.append(f"{line.line_id} : meilleur choix {good.name} à {good.comparison_net} €/unité "
                         f"de comparaison, {len(line.excluded)} produits exclus")
    return f"Offre {offer.offer_id} valable jusqu'à {offer.valid_until.isoformat()} — " + " ; ".join(parts)
