from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ttap.domain.models import Delivery, Need, PurchaseRequest, Quantity, RequestLine, Unit


def test_purchase_request_requires_at_least_one_line():
    with pytest.raises(ValidationError):
        PurchaseRequest(request_id="rq_1", org_id="org_a", lines=[],
                        delivery=Delivery(requested_date=date(2026, 11, 16),
                                          latest_acceptable_date=date(2026, 11, 16)))


def test_quantity_must_be_positive():
    with pytest.raises(ValidationError):
        Quantity(value=Decimal("0"), unit=Unit.L)


def test_request_line_defaults():
    line = RequestLine(line_id="L1", need=Need(text="milk"),
                       quantity=Quantity(value=Decimal("1000"), unit=Unit.L))
    assert line.substitution == "best_match"
    assert line.preferences.origin == []
