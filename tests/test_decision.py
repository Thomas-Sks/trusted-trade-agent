from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from ttap.adapters.outbound.cedar_engine import CedarPolicyEngine
from ttap.domain.decision import build_decision_context
from ttap.domain.models import Mandate
from tests.factories import DEMO_NOW

POLICIES = Path(__file__).resolve().parent.parent / "policies" / "base.cedar"
MANDATE = Mandate(org_id="org_a", version=1, valid_until=DEMO_NOW + timedelta(days=30),
                  limit_per_order_net=Decimal("2000"), max_unverified_value_net=Decimal("500"))


def ctx(**over):
    base = {"mandate_active": True, "total_net": Decimal("1010.00"), "limit_per_order_net": Decimal("2000"),
            "unverified_value_net": Decimal("0"), "max_unverified_value_net": Decimal("500"),
            "has_origin_conflict": False, "has_changes_vs_request": False, "has_partial": False}
    return base | over


def test_within_mandate_is_auto_approved():
    d = CedarPolicyEngine.from_file(POLICIES).decide(ctx())
    assert d.outcome == "AUTO_APPROVED" and d.rules_fired == []


def test_all_escalation_reasons_are_listed():
    d = CedarPolicyEngine.from_file(POLICIES).decide(
        ctx(total_net=Decimal("2340.00"), has_origin_conflict=True))
    assert d.outcome == "PENDING_HUMAN"
    assert d.rules_fired == ["origin_conflict", "total_over_order_limit"]


def test_inactive_mandate_is_denied():
    d = CedarPolicyEngine.from_file(POLICIES).decide(ctx(mandate_active=False))
    assert d.outcome == "DENIED" and d.rules_fired == ["mandate_not_active"]


def test_broken_policy_fails_closed():
    d = CedarPolicyEngine("this is not cedar").decide(ctx())
    assert d.outcome == "DENIED"


def test_context_is_computed_from_candidates_and_mandate():
    c = build_decision_context([], MANDATE, DEMO_NOW)
    assert c["mandate_active"] is True and c["total_net"] == Decimal("0")
    assert build_decision_context([], None, DEMO_NOW)["mandate_active"] is False
