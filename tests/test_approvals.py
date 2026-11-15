from datetime import timedelta
from decimal import Decimal

import pytest

from ttap.adapters.outbound.logging_notifier import LoggingNotifier
from ttap.application.approvals import ApprovalService
from ttap.application.errors import Conflict, PriceLockExpired
from ttap.domain.models import OrderState, SelectedLine
from tests.env import GOOD, Env
from tests.factories import DEMO_NOW


async def pending(limit: str = "500"):
    env = Env(limit=limit)
    notifier = LoggingNotifier()
    approvals = ApprovalService(env.store, env.policy, env.mandates, env.clock, env.auditor, notifier)
    order = env.orders.place("org_a", (await env.offer()).offer_id, GOOD, "idem-1")
    assert order.state == OrderState.PENDING_HUMAN
    return env, approvals, notifier, order


async def test_escalate_sends_card_and_audits():
    env, approvals, notifier, order = await pending()
    await approvals.escalate(order)
    assert notifier.sent[0][0] == order.order_id and "Blocked by" in notifier.sent[0][1]
    assert env.audit.list("org_a")[-1].type == "org.ttap.approval.escalated.v1"


async def test_approve_then_second_approval_conflicts():
    env, approvals, _, order = await pending()
    approved = approvals.approve("org_a", order.order_id, "alice", expected_version=order.version)
    assert approved.state == OrderState.APPROVED and approved.approved_by == "alice"
    with pytest.raises(Conflict):
        approvals.approve("org_a", order.order_id, "alice")
    assert env.audit.list("org_a")[-1].actor == "approver:alice"


async def test_stale_version_conflicts():
    _, approvals, _, order = await pending()
    with pytest.raises(Conflict):
        approvals.approve("org_a", order.order_id, "alice", expected_version=order.version - 1)


async def test_approval_after_price_lock_is_refused():
    env, approvals, _, order = await pending()
    env.clock.at = order.lock_until + timedelta(seconds=1)
    with pytest.raises(PriceLockExpired):
        approvals.approve("org_a", order.order_id, "alice")


async def test_reject_keeps_reason():
    _, approvals, _, order = await pending()
    rejected = approvals.reject("org_a", order.order_id, "alice", "too expensive")
    assert rejected.state == OrderState.REJECTED and rejected.rejection_reason == "too expensive"


async def test_modify_reevaluates_mandate():
    env, approvals, _, order = await pending()
    env.mandates._mandates["org_a"] = env.mandates.get("org_a").model_copy(update={"limit_per_order_net": Decimal("5000")})
    modified = approvals.modify("org_a", order.order_id, "alice", [SelectedLine(line_id="L1", tier="best")])
    assert modified.state == OrderState.APPROVED and modified.selected[0].tier == "best"
    assert env.audit.list("org_a")[-1].type == "org.ttap.approval.modified.v1"


async def test_timeout_expires_fail_closed():
    env, approvals, _, order = await pending()
    env.clock.at = DEMO_NOW + timedelta(days=1)
    expired = approvals.expire_due()
    assert [o.order_id for o in expired] == [order.order_id]
    assert env.store.get_order("org_a", order.order_id).state == OrderState.EXPIRED
    assert approvals.pending("org_a") == []
