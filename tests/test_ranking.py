from decimal import Decimal

from ttap.domain.models import Delivery, Need, Preferences, Quantity, RequestLine, StockStatus, Unit
from ttap.domain.ranking import build_offer_line
from tests.factories import MONDAY, price, product, stock

DELIVERY = Delivery(requested_date=MONDAY, latest_acceptable_date=MONDAY)


def line(**prefs) -> RequestLine:
    return RequestLine(line_id="L1", need=Need(text="milk", required_claims=["FREE_FROM_LACTOSE"]),
                       quantity=Quantity(value=Decimal("1000"), unit=Unit.L), preferences=Preferences(**prefs))


def test_good_is_cheapest_per_litre_meeting_hard_constraints():
    products = [product("A", "Milk 1 l", claims=("FREE_FROM_LACTOSE",)),
                product("B", "Milk 1 l", claims=("LOW_LACTOSE",)),
                product("C", "Milk 1 l", claims=("FREE_FROM_LACTOSE",))]
    prices = {"A": price("A", "1.20", "1.20"), "B": price("B", "0.90", "0.90"), "C": price("C", "1.05", "1.05")}
    avail = {pid: stock(pid, "9999999999") for pid in "ABC"}
    out = build_offer_line(line(), products, prices, avail, DELIVERY)
    assert out.tiers["good"].product_id == "C"
    assert out.tiers["good"].qty_sales_units == 1000
    assert out.tiers["good"].line_total_net == Decimal("1050.00")
    assert {e.product_id: e.reason for e in out.excluded} == {"B": "CLAIM_MISSING:FREE_FROM_LACTOSE"}


def test_better_respects_origin_preference_and_reports_changes():
    products = [product("NL", "Milk 1 l", claims=("FREE_FROM_LACTOSE",), origin="nl", synkka_origins=("528",)),
                product("FI", "Milk 1 l", claims=("FREE_FROM_LACTOSE",), origin="fi", synkka_origins=("246",))]
    prices = {"NL": price("NL", "1.00", "1.00"), "FI": price("FI", "1.10", "1.10")}
    avail = {pid: stock(pid, "9999999999") for pid in ("NL", "FI")}
    out = build_offer_line(line(origin=["fi"]), products, prices, avail, DELIVERY)
    assert out.tiers["good"].product_id == "NL"
    assert out.tiers["good"].changes_vs_request == ["origin:nl"]
    assert out.tiers["better"].product_id == "FI"


def test_exclusions_unit_mismatch_unavailable_insufficient_and_late():
    products = [product(p, "Milk 1 l", claims=("FREE_FROM_LACTOSE",)) for p in ("U", "X", "S", "T")]
    prices = {"U": price("U", "1", "1", comparison_unit="KG"), "X": price("X", "1", "1"),
              "S": price("S", "1", "1"), "T": price("T", "1", "1")}
    avail = {"U": stock("U", "9999999999"), "X": stock("X", "0"), "S": stock("S", "24"),
             "T": stock("T", "9999999999", available_date=MONDAY.replace(day=20))}
    out = build_offer_line(line(), products, prices, avail, DELIVERY)
    reasons = {e.product_id: e.reason for e in out.excluded}
    assert reasons == {"U": "COMPARISON_UNIT_MISMATCH", "X": "UNAVAILABLE",
                       "S": "INSUFFICIENT_STOCK:24", "T": "DELIVERY_TOO_LATE"}
    assert out.tiers == {} and out.exceptions == ["NO_ELIGIBLE_PRODUCT"]


def test_unknown_supplier_stock_is_kept_and_flagged():
    products = [product("T", "Milk 1 l", claims=("FREE_FROM_LACTOSE",))]
    out = build_offer_line(line(), products, {"T": price("T", "1", "1")},
                           {"T": stock("T", "999999", model="Terminal")}, DELIVERY)
    assert out.tiers["good"].stock == StockStatus.UNKNOWN_SUPPLIER_STOCK


def test_best_prefers_reliability_then_lower_carbon():
    from tests.factories import raw_product
    from ttap.adapters.outbound.catalog_json import parse_product
    base = dict(claims=("FREE_FROM_LACTOSE",))
    a = parse_product(raw_product("A", "Milk 1 l", **base)).model_copy(update={"reliability": Decimal("0.8")})
    b = parse_product(raw_product("B", "Milk 1 l", **base)).model_copy(
        update={"reliability": Decimal("1.0"), "carbon_kg_per_kg": Decimal("2.0")})
    c = parse_product(raw_product("C", "Milk 1 l", **base)).model_copy(
        update={"reliability": Decimal("1.0"), "carbon_kg_per_kg": Decimal("1.1")})
    prices = {p: price(p, "1.00", "1.00") for p in "ABC"}
    avail = {p: stock(p, "9999999999") for p in "ABC"}
    out = build_offer_line(line(), [a, b, c], prices, avail, DELIVERY)
    assert out.tiers["best"].product_id == "C"
    assert out.tiers["best"].reliability == Decimal("1.0")


def test_catalog_from_files_loads_reliability_and_carbon(tmp_path):
    import json
    from tests.factories import raw_product
    from ttap.adapters.outbound.catalog_json import JsonCatalog
    (tmp_path / "p.json").write_text(json.dumps([raw_product("1", "x"), raw_product("2", "y")]))
    (tmp_path / "r.csv").write_text("productId,deliveryReliability\n1,0.95\n")
    (tmp_path / "c.csv").write_text("productId,AVG kg CO2-eq/kg\n1,1.1\n2,3.5\n")
    cat = JsonCatalog.from_files(tmp_path / "p.json", tmp_path / "r.csv", tmp_path / "c.csv")
    assert cat.get("1").reliability == Decimal("0.95") and cat.get("2").reliability is None
    assert cat.get("2").carbon_kg_per_kg == Decimal("3.5")
