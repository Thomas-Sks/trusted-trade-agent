"""Step 0 output: a structured draft of the buyer's need. Produced by an LLM, ALWAYS shown back with its assumptions;
the deterministic core never trusts it blindly (it becomes a normal Request the mandate still governs)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from ttap.domain.models import Delivery, Need, Preferences, Quantity, RequestLine, Unit

CLAIM_CODES = ["FREE_FROM_LACTOSE", "LOW_LACTOSE", "FREE_FROM_GLUTEN", "VEGAN", "VEGETARIAN",
               "FREE_FROM_PRESERVATIVES", "FREE_FROM_ADDITIVES", "NO_ADDED_SUGARS", "HIGH_FIBRE", "FREE_FROM_EGGS",
               "HIGH_PROTEIN", "LOW_SODIUM_SALT", "FREE_FROM_SOY", "FREE_FROM_FAT", "LOW_FAT"]
LABEL_CODES = ["EU_ORGANIC_FARMING", "SVANEN", "RAINFOREST_ALLIANCE", "EU_ECO_LABEL",
               "MARINE_STEWARDSHIP_COUNCIL_LABEL", "FAIR_TRADE_MARK", "AQUACULTURE_STEWARDSHIP_COUNCIL", "KRAV_MARK",
               "GOODS_FROM_FINLAND_BLUE_SWAN", "MADE_IN_FINLAND_FLAG_WITH_KEY", "FINNISH_HEART_SYMBOL"]


class InterpretedLine(BaseModel):
    need_text: str = Field(description="Short English product description used for catalogue search, e.g. 'milk'")
    product_id: str | None = Field(None, description="Only when the buyer clearly means one of their usual products")
    required_claims: list[str] = Field(default_factory=list, description=f"Hard constraints, codes from {CLAIM_CODES}")
    required_labels: list[str] = Field(default_factory=list, description=f"Hard constraints, codes from {LABEL_CODES}")
    quantity_value: float
    quantity_unit: Literal["L", "KG", "PIECE"]
    origin_preferences: list[str] = Field(default_factory=list, description="ISO-2 lowercase, soft preference")
    label_preferences: list[str] = Field(default_factory=list, description="Soft preference label codes")
    substitution: Literal["best_match", "no_substitute"] = "best_match"


class InterpretedRequest(BaseModel):
    lines: list[InterpretedLine]
    requested_date: date
    latest_acceptable_date: date
    assumptions: list[str] = Field(description="Every default or guess made, in the buyer's language")
    questions: list[str] = Field(default_factory=list,
                                 description="Only questions whose answer would change the result materially")


def to_request(interp: InterpretedRequest) -> tuple[list[RequestLine], Delivery]:
    lines = []
    for i, ln in enumerate(interp.lines, start=1):
        lines.append(RequestLine(
            line_id=f"L{i}",
            need=Need(text=ln.need_text, product_id=ln.product_id,
                      required_claims=[c for c in ln.required_claims if c in CLAIM_CODES],
                      required_labels=[x for x in ln.required_labels if x in LABEL_CODES]),
            quantity=Quantity(value=Decimal(str(ln.quantity_value)), unit=Unit(ln.quantity_unit)),
            preferences=Preferences(origin=ln.origin_preferences, labels=ln.label_preferences),
            substitution=ln.substitution))
    return lines, Delivery(requested_date=interp.requested_date, latest_acceptable_date=interp.latest_acceptable_date)
