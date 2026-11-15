"""Thin python-telegram-bot adapter: long polling (no public URL needed), cards with inline buttons."""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from ttap.adapters.inbound.telegram_logic import ApprovalBotLogic
from ttap.adapters.outbound.sqlite_store import SqliteStore
from ttap.domain.approval_card import render_card_text
from ttap.domain.models import ApprovalCard, Order

log = logging.getLogger("ttap.telegram")


class TelegramNotifier:
    def __init__(self, token: str, store: SqliteStore):
        self._store = store
        self._logic: ApprovalBotLogic | None = None
        self._app = Application.builder().token(token).build()
        self._app.add_handler(CommandHandler("start", self._on_start))
        self._app.add_handler(CallbackQueryHandler(self._on_callback))

    def bind(self, logic: ApprovalBotLogic) -> None:
        """Late binding: the logic needs ApprovalService, which itself needs this notifier."""
        self._logic = logic

    async def start(self) -> None:
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)
        log.info("telegram bot polling")

    async def stop(self) -> None:
        await self._app.updater.stop()
        await self._app.stop()
        await self._app.shutdown()

    async def request_approval(self, order: Order, card: ApprovalCard) -> None:
        assert self._logic is not None, "call bind() first"
        chats = self._store.approver_chats(order.org_id)
        if not chats:
            log.warning("no paired approver for %s: card for %s not delivered", order.org_id, order.order_id)
            return
        buttons = self._logic.buttons(order, card)
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(label, url=url) if url else InlineKeyboardButton(label, callback_data=data)
            for label, data, url in buttons if data or url
        ]])
        text = render_card_text(card)
        for chat_id in chats:
            await self._app.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)

    async def _on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        assert self._logic is not None
        code = context.args[0] if context.args else ""
        await update.message.reply_text(self._logic.link(update.effective_user.id, code))

    async def _on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        assert self._logic is not None
        query = update.callback_query
        await query.answer()
        result = await self._logic.handle(query.from_user.id, query.data or "")
        if result.startswith(("✅", "❌")):
            await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(result)
