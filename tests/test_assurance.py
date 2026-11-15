from ttap.domain.assurance import need_violation, origin_assurance, stock_status
from ttap.domain.models import Need, OriginAssurance, StockStatus, UpstreamAvailability
from tests.factories import product, stock


def test_stock_status_sentinels():
    assert stock_status(stock("1", "999999", model="Terminal")) == StockStatus.UNKNOWN_SUPPLIER_STOCK
    assert stock_status(stock("1", "9999999999")) == StockStatus.VERIFIED_UNLIMITED
    assert stock_status(stock("1", "24")) == StockStatus.VERIFIED_QTY
    assert stock_status(stock("1", "0")) == StockStatus.UNAVAILABLE
    assert stock_status(UpstreamAvailability(product_id="1", sales_block=False)) == StockStatus.UNAVAILABLE
    assert stock_status(None) == StockStatus.UNAVAILABLE


def test_origin_conflict_exposes_both_sources():
    assert origin_assurance(product("1", "x", origin="gb", synkka_origins=("528",))) == (
        OriginAssurance.CONFLICT, ["gb", "nl"])
    assert origin_assurance(product("1", "x", origin="fi", synkka_origins=("246",)))[0] == OriginAssurance.CONSISTENT
    assert origin_assurance(product("1", "x", origin="fi", synkka_origins=()))[0] == OriginAssurance.SINGLE_SOURCE


def test_missing_data_is_not_a_satisfied_claim():
    need = Need(text="milk", required_claims=["FREE_FROM_LACTOSE"])
    assert need_violation(product("1", "x", with_classification=False), need) == "NOT_VERIFIABLE:FREE_FROM_LACTOSE"
    assert need_violation(product("1", "x", claims=("LOW_LACTOSE",)), need) == "CLAIM_MISSING:FREE_FROM_LACTOSE"
    assert need_violation(product("1", "x", claims=("FREE_FROM_LACTOSE",)), need) is None


def test_excluded_allergen_present():
    need = Need(text="bread", excluded_allergens=["AW"])
    assert need_violation(product("1", "x", allergens=("AW",)), need) == "ALLERGEN_PRESENT:AW"
