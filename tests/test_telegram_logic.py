from datetime import timedelta
from decimal import Decimal

from ttap.adapters.inbound.telegram_logic import ApprovalBotLogic
from ttap.adapters.outbound.logging_notifier import LoggingNotifier
from ttap.application.approvals import ApprovalService
from ttap.domain.models import OrderState
from tests.env import GOOD, Env

PAIRING = {"PAIR-A": ("org_a", "alice"), "PAIR-B": ("org_b", "bob")}


async def setup(step_up: str = "5000"):
    env = Env(limit="500")
    m = env.mandates.get("org_a")
    env.mandates._mandates["org_a"] = m.model_copy(update={"step_up_above_net": Decimal(step_up)})
    approvals = ApprovalService(env.store, env.policy, env.mandates, env.clock, env.auditor, LoggingNotifier())
    logic = ApprovalBotLogic(env.store, approvals, PAIRING, env.clock, web_base_url="https://ttap.example")
    order = env.orders.place("org_a", (await env.offer()).offer_id, GOOD, "idem-1")
    return env, logic, order


def data_for(buttons, label_prefix):
    return next(cb for label, cb, url in buttons if label.startswith(label_prefix))


async def test_pairing():
    env, logic, _ = await setup()
    assert "alice" in logic.link(111, "PAIR-A") and "Paired" in logic.link(111, "PAIR-A")
    assert "Unknown" in logic.link(222, "WRONG")
    assert env.store.approver_chats("org_a") == [111]


async def test_click_by_paired_approver_approves_once():
    env, logic, order = await setup()
    logic.link(111, "PAIR-A")
    buttons = logic.buttons(order, approvals_card(logic, order))
    approve = data_for(buttons, "✅")
    assert len(approve) <= 64
    assert (await logic.handle(111, approve)).kind == "approved"
    assert env.store.get_order("org_a", order.order_id).state == OrderState.APPROVED
    assert "already used" in (await logic.handle(111, approve)).html


async def test_unpaired_and_other_org_cannot_act():
    env, logic, order = await setup()
    logic.link(222, "PAIR-B")
    approve = data_for(logic.buttons(order, approvals_card(logic, order)), "✅")
    assert "not paired" in (await logic.handle(999, approve)).html
    assert "Not authorised" in (await logic.handle(222, approve)).html
    assert env.store.get_order("org_a", order.order_id).state == OrderState.PENDING_HUMAN


async def test_expired_token_refused():
    env, logic, order = await setup()
    logic.link(111, "PAIR-A")
    approve = data_for(logic.buttons(order, approvals_card(logic, order)), "✅")
    env.clock.at = env.clock.at + timedelta(days=1)
    assert "expired" in (await logic.handle(111, approve)).html


async def test_reject_and_detail():
    env, logic, order = await setup()
    logic.link(111, "PAIR-A")
    buttons = logic.buttons(order, approvals_card(logic, order))
    detail = await logic.handle(111, data_for(buttons, "🔎"))
    assert detail.kind == "detail" and "<b>Why</b>" in detail.html and "verified stock" in detail.html
    assert (await logic.handle(111, data_for(buttons, "❌"))).kind == "rejected"
    assert env.store.get_order("org_a", order.order_id).state == OrderState.REJECTED


async def test_step_up_replaces_approve_callback_with_web_link():
    _, logic, order = await setup(step_up="100")
    buttons = logic.buttons(order, approvals_card(logic, order))
    approve = buttons[0]
    assert approve[0].startswith("🔐")
    assert approve[1] is None and approve[2].startswith("https://ttap.example/")


def approvals_card(logic, order):
    return logic.approvals.card(order.org_id, order.order_id)


async def test_one_telegram_account_approves_for_every_org_it_paired():
    env, logic, order = await setup()
    logic.link(111, "PAIR-B")   # paired to another organisation first
    logic.link(111, "PAIR-A")   # pairing a second one keeps the first
    assert env.store.approver_chats("org_b") == [111] and env.store.approver_chats("org_a") == [111]
    approve = data_for(logic.buttons(order, approvals_card(logic, order)), "✅")
    assert (await logic.handle(111, approve)).kind == "approved"
    assert env.store.get_order("org_a", order.order_id).approved_by == "alice"
