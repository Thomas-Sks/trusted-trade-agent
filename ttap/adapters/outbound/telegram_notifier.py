"""Thin python-telegram-bot adapter: long polling (no public URL needed), cards with inline buttons."""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from ttap.adapters.inbound.telegram_logic import ApprovalBotLogic
from ttap.adapters.outbound.sqlite_store import SqliteStore
from ttap.adapters.outbound.telegram_format import render_card_html
from ttap.domain.models import ApprovalCard, Order

log = logging.getLogger("ttap.telegram")


class TelegramNotifier:
    def __init__(self, token: str, store: SqliteStore):
        self._store = store
        self._logic: ApprovalBotLogic | None = None
        self._app = Application.builder().token(token).build()
        self._app.add_handler(CommandHandler("start", self._on_start))
        self._app.add_handler(CommandHandler(["pause", "resume", "status"], self._on_command))
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
        usable = [(label, data, url) for label, data, url in buttons if data or url]
        primary, secondary = usable[:2], usable[2:]
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(label, url=url) if url else InlineKeyboardButton(label, callback_data=data)
             for label, data, url in row] for row in (primary, secondary) if row])
        text = render_card_html(card)
        for chat_id in chats:
            await self._app.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard,
                                             parse_mode=ParseMode.HTML)

    async def _on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        assert self._logic is not None
        code = context.args[0] if context.args else ""
        await update.message.reply_text(self._logic.link(update.effective_user.id, code), parse_mode=ParseMode.HTML)

    async def _on_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        assert self._logic is not None
        name = (update.message.text or "/status").split()[0].lstrip("/").split("@")[0]
        reply = await self._logic.command(update.effective_user.id, name)
        await update.message.reply_text(reply.html, parse_mode=ParseMode.HTML)

    async def _on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        assert self._logic is not None
        query = update.callback_query
        await query.answer()
        reply = await self._logic.handle(query.from_user.id, query.data or "")
        if reply.kind in ("approved", "rejected"):
            # update the card in place: status appended, buttons removed
            await query.edit_message_text(f"{query.message.text_html}\n\n{reply.html}", parse_mode=ParseMode.HTML)
        else:
            await query.message.reply_text(reply.html, parse_mode=ParseMode.HTML)
