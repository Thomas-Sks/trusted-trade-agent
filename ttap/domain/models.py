from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Unit(StrEnum):
    L = "L"
    KG = "KG"
    PIECE = "PIECE"


class Quantity(BaseModel):
    model_config = ConfigDict(frozen=True)
    value: Decimal = Field(gt=0)
    unit: Unit


class Need(BaseModel):
    text: str
    required_claims: list[str] = []
    excluded_allergens: list[str] = []
    required_labels: list[str] = []
    product_id: str | None = None


class Preferences(BaseModel):
    origin: list[str] = []
    brands: list[str] = []
    labels: list[str] = []


SubstitutionPref = Literal["best_match", "no_substitute"]


class RequestLine(BaseModel):
    line_id: str
    need: Need
    quantity: Quantity
    preferences: Preferences = Preferences()
    substitution: SubstitutionPref = "best_match"


class Delivery(BaseModel):
    requested_date: date
    latest_acceptable_date: date


class PurchaseRequest(BaseModel):
    request_id: str
    org_id: str
    lines: list[RequestLine] = Field(min_length=1)
    delivery: Delivery


class CatalogProduct(BaseModel):
    model_config = ConfigDict(frozen=True)
    product_id: str
    gtin: str | None
    names: dict[str, str]
    category: str
    vendor: str
    brand: str | None
    sales_unit: str
    base_unit: str
    units: dict[str, Decimal]
    lot_size: Decimal
    claims: frozenset[str]
    labels: frozenset[str]
    allergens_contained: frozenset[str]
    has_classification_data: bool
    origin_valio: str | None
    origin_manufacturer: tuple[str, ...]
    substitutes: tuple[str, ...]
    variable_weight: bool
    reliability: Decimal | None = None
    carbon_kg_per_kg: Decimal | None = None

    def display_name(self, lang: str = "en") -> str:
        return self.names.get(lang) or next(iter(self.names.values()), self.product_id)


class StockStatus(StrEnum):
    VERIFIED_QTY = "VERIFIED_QTY"
    VERIFIED_UNLIMITED = "VERIFIED_UNLIMITED"
    UNKNOWN_SUPPLIER_STOCK = "UNKNOWN_SUPPLIER_STOCK"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"


class OriginAssurance(StrEnum):
    CONSISTENT = "CONSISTENT"
    CONFLICT = "CONFLICT"
    SINGLE_SOURCE = "SINGLE_SOURCE"
    MISSING = "MISSING"


class UpstreamPrice(BaseModel):
    product_id: str
    error: bool
    unit_net: Decimal | None = None
    vat_rate: Decimal | None = None
    comparison_net: Decimal | None = None
    comparison_unit: str | None = None
    list_net: Decimal | None = None
    valid_to: datetime | None = None
    net_price_found: bool = False


class UpstreamAvailability(BaseModel):
    product_id: str
    sales_block: bool
    logistic_model: str | None = None
    available_amount: Decimal | None = None
    available_date: date | None = None
    sales_unit: str | None = None
    closing_time: datetime | None = None


Tier = Literal["good", "better", "best", "split"]


class Candidate(BaseModel):
    product_id: str
    name: str
    qty_sales_units: Decimal
    sales_unit: str
    content_per_sales_unit: Decimal
    content_source: Literal["name", "price_ratio"]
    surplus: Decimal
    unit_net: Decimal
    line_total_net: Decimal
    vat_rate: Decimal
    comparison_net: Decimal
    price_valid_to: datetime | None
    stock: StockStatus
    available_amount: Decimal | None
    delivery_date: date
    order_cutoff: datetime | None
    origin: OriginAssurance
    origins: list[str]
    changes_vs_request: list[str]
    score: float
    reliability: Decimal | None = None
    carbon_kg_per_kg: Decimal | None = None
    is_substitute: bool = False
    partial: bool = False
    missing_qty: Decimal = Decimal("0")
    lot_size: Decimal = Decimal("1")


class Exclusion(BaseModel):
    product_id: str
    reason: str


class OfferLine(BaseModel):
    line_id: str
    tiers: dict[str, Candidate]
    excluded: list[Exclusion]
    exceptions: list[str]
    split: list[Candidate] = []
    backorder_qty: Decimal = Decimal("0")


class Offer(BaseModel):
    offer_id: str
    request_id: str
    org_id: str
    issued_at: datetime
    valid_until: datetime
    catalog_version: str
    lines: list[OfferLine]
    signature: str | None = None


class OrderState(StrEnum):
    PENDING_DECISION = "PENDING_DECISION"
    AUTO_APPROVED = "AUTO_APPROVED"
    PENDING_HUMAN = "PENDING_HUMAN"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    CONFIRMED = "CONFIRMED"


class SelectedLine(BaseModel):
    line_id: str
    tier: Tier


class Decision(BaseModel):
    outcome: Literal["AUTO_APPROVED", "PENDING_HUMAN", "DENIED"]
    rules_fired: list[str]
    context: dict[str, Any]


class OrderResponseLine(BaseModel):
    line_id: str
    status: Literal[1, 3, 5, 7]
    product_id: str | None
    quantity: Decimal
    sales_unit: str
    substituted_for: str | None = None
    backorder_qty: Decimal = Decimal("0")
    reason: str | None = None


class OrderResponse(BaseModel):
    code: Literal["AB", "AP", "CA", "RE"]
    lines: list[OrderResponseLine] = []


class Order(BaseModel):
    order_id: str
    org_id: str
    offer_id: str
    offer_hash: str
    selected: list[SelectedLine]
    state: OrderState
    version: int = 1
    total_net: Decimal
    decision: Decision | None = None
    idempotency_key: str
    decided_at: datetime | None = None
    lock_until: datetime | None = None
    mandate_version: int | None = None
    approved_by: str | None = None
    rejection_reason: str | None = None
    order_response: OrderResponse | None = None


class UsualItem(BaseModel):
    product_id: str
    median_qty: Decimal


class Mandate(BaseModel):
    org_id: str
    version: int
    status: Literal["active", "suspended"] = "active"
    valid_until: datetime
    limit_per_order_net: Decimal
    max_unverified_value_net: Decimal
    approval_timeout: timedelta = timedelta(hours=2)
    step_up_above_net: Decimal = Decimal("5000")
    usual_list: list[UsualItem] = []


Step = Literal["request", "lookup", "order", "approval"]


class AuditEvent(BaseModel):
    specversion: Literal["1.0"] = "1.0"
    id: str
    source: str = "urn:ttap:gateway"
    type: str
    subject: str
    time: datetime
    datacontenttype: str = "application/json"
    org_id: str
    step: Step
    actor: str
    outcome: str
    data: dict[str, Any] = {}
    explanation: str = ""
    prev_hash: str | None = None
    hash: str | None = None
    signature: str | None = None


class CardLine(BaseModel):
    name: str
    partial: bool = False
    is_substitute: bool = False
    qty_sales_units: Decimal
    sales_unit: str
    unit_net: Decimal
    line_total_net: Decimal
    stock: StockStatus
    changes: list[str]
    vs_usual: str | None


class ApprovalCard(BaseModel):
    order_id: str
    org_id: str
    version: int
    offer_hash_short: str
    total_net: Decimal
    total_gross: Decimal
    reasons: list[str]
    lines: list[CardLine]
    warnings: list[str]
    delivery_date: date | None
    minutes_to_cutoff: int | None
    step_up_required: bool


class ApproverRef(BaseModel):
    org_id: str
    user_id: str


class ActionToken(BaseModel):
    token_id: str
    org_id: str
    order_id: str
    version: int
    action: Literal["approve", "reject", "detail"]
    expires_at: datetime
    used: bool = False
