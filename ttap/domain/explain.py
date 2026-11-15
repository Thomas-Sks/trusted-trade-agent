"""Deterministic, template-based explanations. Never produced by an LLM."""
from __future__ import annotations

from ttap.domain.formatting import money, when
from ttap.domain.models import Offer, Order

RULE_TEXT: dict[str, str] = {
    "total_over_order_limit": "Total {total_net} € HT > plafond par commande {limit_per_order_net} €",
    "unverified_stock_over_limit": (
        "Stock fournisseur non vérifié : {unverified_value_net} € HT > limite {max_unverified_value_net} €"),
    "origin_conflict": "Origine contradictoire entre Valio et le fabricant",
    "deviates_from_request": "Le choix s'écarte de la demande (substitut, origine ou marque)",
    "partial_fulfilment": "Disponibilité partielle : quantité demandée non couverte par le produit demandé",
    "period_budget_exceeded": "Budget de la période dépassé : {period_spend_net} € engagés > {period_budget_net} €",
    "order_velocity_exceeded": (
        "Rythme anormal : {orders_last_hour} commandes dans l'heure > {max_orders_per_hour} (fractionnement ?)"),
    "stale_data": "Données fournisseur périmées (servies depuis le cache pendant une panne)",
    "mandate_not_active": "Mandat inactif, suspendu ou expiré",
    "policy_evaluation_error": "Erreur d'évaluation des règles : refus par défaut",
}

OUTCOME_TEXT = {
    "AUTO_APPROVED": "approuvée automatiquement dans le mandat",
    "PENDING_HUMAN": "escaladée vers un approbateur humain",
    "DENIED": "refusée",
}


MONEY_KEYS = ("_net", "_value")


def _display(context: dict) -> dict:
    return {k: money(v) if k.endswith(MONEY_KEYS) and not isinstance(v, bool) else v for k, v in context.items()}


def explain_rules(rules: list[str], context: dict) -> list[str]:
    out = []
    shown = _display(context)
    for rule in rules:
        template = RULE_TEXT.get(rule)
        try:
            out.append(template.format(**shown) if template else f"Règle déclenchée : {rule}")
        except (KeyError, IndexError):
            out.append(f"Règle déclenchée : {rule}")
    return out


def explain_decision(order: Order) -> str:
    if order.decision is None:
        return f"Commande {order.order_id} en attente de décision."
    base = (f"Commande {order.order_id} : {money(order.total_net)} € HT, "
            f"{OUTCOME_TEXT[order.decision.outcome]}")
    reasons = explain_rules(order.decision.rules_fired, order.decision.context)
    return base + (" car : " + " ; ".join(reasons) if reasons else ".")


def explain_offer(offer: Offer) -> str:
    parts = []
    for line in offer.lines:
        good = line.tiers.get("good")
        if good is None:
            plan = f", plan mixte de {len(line.split)} produit(s)" if line.split else ""
            parts.append(f"{line.line_id} : aucun produit complet{plan} ({len(line.excluded)} écartés)")
        else:
            parts.append(f"{line.line_id} : meilleur prix {good.name} à {money(good.comparison_net)} €/unité "
                         f"de comparaison, {len(line.excluded)} produits écartés")
    return f"Offre signée valable jusqu'au {when(offer.valid_until)} — " + " ; ".join(parts)
