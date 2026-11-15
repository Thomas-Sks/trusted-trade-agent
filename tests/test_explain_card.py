from datetime import timedelta
from decimal import Decimal

from ttap.domain.approval_card import build_card, render_card_text
from ttap.domain.explain import explain_rules
from ttap.domain.models import (
    Candidate, Decision, Mandate, Offer, OfferLine, Order, OrderState, OriginAssurance, SelectedLine, StockStatus,
    UsualItem,
)
from tests.factories import DEMO_NOW, MONDAY


def test_rule_text_uses_context_values():
    ctx = {"total_net": Decimal("3030.00"), "limit_per_order_net": Decimal("2000")}
    assert explain_rules(["total_over_order_limit"], ctx) == ["Total 3 030,00 € HT > plafond par commande 2 000,00 €"]


def test_unknown_rule_never_raises():
    assert explain_rules(["something_new"], {}) == ["Règle déclenchée : something_new"]


def cand(pid="P1", qty="300", total="3030.00", stock=StockStatus.VERIFIED_UNLIMITED, changes=(),
         origin=OriginAssurance.CONSISTENT, origins=("fi",)) -> Candidate:
    return Candidate(product_id=pid, name="Milk 1 l", qty_sales_units=Decimal(qty), sales_unit="ST",
                     content_per_sales_unit=Decimal("1"), content_source="name", surplus=Decimal("0"),
                     unit_net=Decimal("10.10"), line_total_net=Decimal(total), vat_rate=Decimal("13.5"),
                     comparison_net=Decimal("10.10"), price_valid_to=None, stock=stock, available_amount=None,
                     delivery_date=MONDAY, order_cutoff=DEMO_NOW + timedelta(minutes=95), origin=origin,
                     origins=list(origins), changes_vs_request=list(changes), score=0.5)


def fixtures(c: Candidate, usual: list[UsualItem], step_up="5000"):
    offer = Offer(offer_id="of_1", request_id="rq_1", org_id="org_a", issued_at=DEMO_NOW,
                  valid_until=DEMO_NOW + timedelta(minutes=30), catalog_version="v",
                  lines=[OfferLine(line_id="L1", tiers={"good": c}, excluded=[], exceptions=[])])
    order = Order(order_id="or_1", org_id="org_a", offer_id="of_1", offer_hash="sha256:3fa9c1d2aaaa",
                  selected=[SelectedLine(line_id="L1", tier="good")], state=OrderState.PENDING_HUMAN, version=2,
                  total_net=Decimal(c.line_total_net), idempotency_key="k",
                  decision=Decision(outcome="PENDING_HUMAN", rules_fired=["total_over_order_limit"],
                                    context={"total_net": "3030.00", "limit_per_order_net": "2000"}))
    mandate = Mandate(org_id="org_a", version=1, valid_until=DEMO_NOW + timedelta(days=9),
                      limit_per_order_net=Decimal("2000"), max_unverified_value_net=Decimal("500"),
                      step_up_above_net=Decimal(step_up), usual_list=usual)
    return order, offer, mandate


def test_card_shows_rules_deviation_and_cutoff():
    order, offer, mandate = fixtures(cand(), [UsualItem(product_id="P1", median_qty=Decimal("100"))])
    card = build_card(order, offer, mandate, DEMO_NOW)
    assert card.reasons == ["Total 3 030,00 € HT > plafond par commande 2 000,00 €"]
    assert card.lines[0].vs_usual == "×3.0 vs habitude"
    assert card.minutes_to_cutoff == 95
    assert card.total_gross == Decimal("3439.05")
    assert card.step_up_required is False
    text = render_card_text(card)
    assert "Bloqué par" in text and "×3.0 vs habitude" in text and "3fa9c1d2" in text


def test_card_flags_new_product_unverified_stock_origin_and_step_up():
    c = cand(stock=StockStatus.UNKNOWN_SUPPLIER_STOCK, changes=["origin:nl"],
             origin=OriginAssurance.CONFLICT, origins=("gb", "nl"))
    order, offer, mandate = fixtures(c, [UsualItem(product_id="OTHER", median_qty=Decimal("5"))], step_up="1000")
    card = build_card(order, offer, mandate, DEMO_NOW)
    assert card.lines[0].vs_usual == "nouveau produit"
    assert any("stock fournisseur non vérifié" in w for w in card.warnings)
    assert any("origine contradictoire" in w for w in card.warnings)
    assert card.lines[0].changes == ["origin:nl"]
    assert card.step_up_required is True


def test_telegram_html_is_short_escaped_and_french():
    from ttap.adapters.outbound.telegram_format import render_card_html
    c = cand(changes=["origin:nl"])
    c = c.model_copy(update={"name": "Milk <special> & co " + "x" * 60})
    order, offer, mandate = fixtures(c, [UsualItem(product_id="P1", median_qty=Decimal("100"))])
    html = render_card_html(build_card(order, offer, mandate, DEMO_NOW))
    assert "&lt;special&gt; &amp; co" in html and "<special>" not in html
    assert "3 030,00 €" in html and "1 h 35" in html and "🌍 origine NL" in html and "lun. 16/11" in html
    assert max(len(line) for line in html.splitlines() if line.startswith("📦")) < 60
