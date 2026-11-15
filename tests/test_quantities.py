from decimal import Decimal

from ttap.domain.models import Unit
from ttap.domain.quantities import content_per_sales_unit, parse_name_quantity, sales_units_needed
from tests.factories import product


def test_parse_name_quantity_handles_units_and_commas():
    assert parse_name_quantity("Milk drink 1,75 l lactose free") == (Decimal("1.75"), Unit.L)
    assert parse_name_quantity("Cream 2,5 dl") == (Decimal("0.25"), Unit.L)
    assert parse_name_quantity("Salad 400g") == (Decimal("0.4"), Unit.KG)
    assert parse_name_quantity("Steak ca2kg") == (Decimal("2"), Unit.KG)
    assert parse_name_quantity("Milk 1 lactose free") is None


def test_content_uses_case_multiplier_confirmed_by_price_ratio():
    # 2 x 10 l per case; API: 31.31 EUR per case, 1.57 EUR per litre -> ratio 19.94
    p = product("9", "Milk drink 10 l box", sales_unit="KI", base_unit="ST", units={"KI": 2.0, "ST": 1.0})
    assert content_per_sales_unit(p, Unit.L, Decimal("31.31"), Decimal("1.57")) == (Decimal("20"), "name")


def test_content_falls_back_to_price_ratio_when_name_is_inconsistent():
    p = product("9", "Milk drink 3 l", sales_unit="KI", base_unit="ST", units={"KI": 1.0, "ST": 1.0})
    assert content_per_sales_unit(p, Unit.L, Decimal("10.00"), Decimal("1.00")) == (Decimal("10.00"), "price_ratio")


def test_content_unknown_without_name_or_ratio():
    p = product("9", "Mystery product")
    assert content_per_sales_unit(p, Unit.L, Decimal("5"), None) is None


def test_sales_units_rounded_up_to_lot():
    assert sales_units_needed(Decimal("1000"), Decimal("20"), Decimal("1")) == 50
    assert sales_units_needed(Decimal("1001"), Decimal("20"), Decimal("1")) == 51
    assert sales_units_needed(Decimal("4"), Decimal("1"), Decimal("1.5")) == Decimal("4.5")
