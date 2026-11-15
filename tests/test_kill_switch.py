from datetime import timedelta

from ttap.adapters.inbound.telegram_logic import ApprovalBotLogic
from ttap.adapters.outbound.logging_notifier import LoggingNotifier
from ttap.application.approvals import ApprovalService
from ttap.application.mandates import MandateService
from ttap.domain.models import OrderState
from tests.env import GOOD, Env


async def test_pause_denies_every_order_and_resume_restores_it():
    env = Env()
    mandates = MandateService(env.mandates, env.policy, env.auditor)
    mandates.set_status("org_a", "suspended", "alice")
    denied = env.orders.place("org_a", (await env.offer()).offer_id, GOOD, "p1")
    assert denied.state == OrderState.DENIED and denied.decision.rules_fired == ["mandate_not_active"]
    mandates.set_status("org_a", "active", "alice")
    assert env.orders.place("org_a", (await env.offer()).offer_id, GOOD, "p2").state == OrderState.AUTO_APPROVED
    assert [e.type for e in env.audit.list("org_a") if "mandate_" in e.type] == [
        "org.ttap.approval.mandate_paused.v1", "org.ttap.approval.mandate_resumed.v1"]


async def test_telegram_pause_command_requires_pairing():
    env = Env()
    approvals = ApprovalService(env.store, env.policy, env.mandates, env.clock, env.auditor, LoggingNotifier())
    logic = ApprovalBotLogic(env.store, approvals, {"P": ("org_a", "alice")}, env.clock,
                             mandates=MandateService(env.mandates, env.policy, env.auditor))
    assert (await logic.command(42, "pause")).kind == "error"
    logic.link(42, "P")
    assert "paused" in (await logic.command(42, "pause")).html
    assert env.mandates.get("org_a").status == "suspended"
    assert "suspended" in (await logic.command(42, "status")).html


async def test_overdue_approval_is_reminded_once():
    env = Env(limit="500")
    notifier = LoggingNotifier()
    approvals = ApprovalService(env.store, env.policy, env.mandates, env.clock, env.auditor, notifier)
    order = env.orders.place("org_a", (await env.offer()).offer_id, GOOD, "r")
    assert await approvals.remind_overdue() == []
    env.clock.at = order.decided_at + (order.lock_until - order.decided_at) / 2 + timedelta(seconds=1)
    assert [o.order_id for o in await approvals.remind_overdue()] == [order.order_id]
    assert await approvals.remind_overdue() == []
    assert len(notifier.sent) == 1
