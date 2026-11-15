"""Channel-agnostic approval-bot logic (pairing, signed one-shot action tokens, who-clicked checks).

Kept free of python-telegram-bot so it can be unit-tested without network and reused for other messengers.
"""
from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from html import escape

from ttap.adapters.outbound.sqlite_store import SqliteStore
from ttap.adapters.outbound.telegram_format import render_card_html, status_html
from ttap.application.approvals import ApprovalService
from ttap.application.errors import TTAPError
from ttap.domain.models import ActionToken, ApprovalCard, Order
from ttap.ports import Clock

Button = tuple[str, str | None, str | None]  # (label, callback_data, url)
PREFIX = "t:"


@dataclass
class BotReply:
    kind: str  # approved | rejected | detail | info | error
    html: str


class ApprovalBotLogic:
    def __init__(self, store: SqliteStore, approvals: ApprovalService, pairing_codes: dict[str, tuple[str, str]],
                 clock: Clock, web_base_url: str | None = None, token_ttl: timedelta = timedelta(hours=2),
                 new_token: Callable[[], str] = lambda: secrets.token_urlsafe(12)):
        self.approvals = approvals
        self._store, self._pairing, self._clock = store, pairing_codes, clock
        self._web, self._ttl, self._new_token = web_base_url, token_ttl, new_token

    def link(self, telegram_id: int, code: str) -> str:
        ref = self._pairing.get(code.strip())
        if ref is None:
            return "❓ Code d'appairage inconnu."
        org_id, user_id = ref
        self._store.link_approver(telegram_id, org_id, user_id)
        return (f"🤝 <b>Appairé</b> : {escape(user_id)} pour <code>{escape(org_id)}</code>\n"
                "Les demandes de validation arriveront ici.")

    def _token(self, order: Order, action: str) -> str:
        expires = self._clock.now() + self._ttl
        if order.lock_until is not None:
            expires = min(expires, order.lock_until)
        token = ActionToken(token_id=self._new_token(), org_id=order.org_id, order_id=order.order_id,
                            version=order.version, action=action, expires_at=expires)
        self._store.save_action_token(token)
        return PREFIX + token.token_id

    def buttons(self, order: Order, card: ApprovalCard) -> list[Button]:
        if card.step_up_required:
            approve: Button = ("🔐 Valider sur le web", None,
                               f"{self._web}/orders/{order.order_id}/review" if self._web else None)
        else:
            approve = ("✅ Approuver", self._token(order, "approve"), None)
        return [approve, ("❌ Refuser", self._token(order, "reject"), None),
                ("🔎 Détails", self._token(order, "detail"), None)]

    async def handle(self, telegram_id: int, data: str) -> BotReply:
        approver = self._store.approver_by_telegram(telegram_id)
        if approver is None:
            return BotReply("error", "🔒 Compte non appairé : ouvrez le lien d'appairage ou envoyez /start &lt;code&gt;.")
        token = self._store.get_action_token(data.removeprefix(PREFIX))
        if token is None or token.used or self._clock.now() >= token.expires_at:
            return BotReply("error", "⌛ Action expirée ou déjà utilisée.")
        if token.org_id != approver.org_id:
            return BotReply("error", "🚫 Non autorisé pour cette organisation.")
        try:
            if token.action == "detail":
                card = self.approvals.card(token.org_id, token.order_id)
                return BotReply("detail", render_card_html(card, detailed=True))
            if not self._store.consume_action_token(token.token_id):
                return BotReply("error", "⌛ Action expirée ou déjà utilisée.")
            if token.action == "approve":
                done = self.approvals.approve(token.org_id, token.order_id, approver.user_id, token.version)
                return BotReply("approved", status_html("approved", approver.user_id, done.total_net))
            self.approvals.reject(token.org_id, token.order_id, approver.user_id, "refus via Telegram", token.version)
            return BotReply("rejected", status_html("rejected", approver.user_id))
        except TTAPError as exc:
            return BotReply("error", f"⚠️ <b>{escape(exc.code)}</b> : {escape(str(exc))}")
