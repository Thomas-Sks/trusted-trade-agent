from decimal import Decimal

from ttap.domain.formatting import duration_minutes, money, qty, shorten


def test_money_french_grouping():
    assert money(Decimal("3030")) == "3,030.00"
    assert money("1234567.891") == "1,234,567.89"
    assert money(Decimal("0.5")) == "0.50"


def test_qty_and_duration_and_shorten():
    assert qty(Decimal("3000")) == "3,000" and qty(Decimal("4.5")) == "4.50"
    assert duration_minutes(4859) == "3 d 8 h"
    assert duration_minutes(95) == "1 h 35" and duration_minutes(7) == "7 min" and duration_minutes(-1) == "passed"
    assert shorten("x" * 50, 10) == "xxxxxxxxx…"
