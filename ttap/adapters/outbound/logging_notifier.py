from __future__ import annotations

import logging

from ttap.domain.approval_card import render_card_text
from ttap.domain.models import ApprovalCard, Order

log = logging.getLogger("ttap.notifier")


class LoggingNotifier:
    """Fallback when no messaging channel is configured: logs the card and keeps it for inspection."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def request_approval(self, order: Order, card: ApprovalCard) -> None:
        text = render_card_text(card)
        self.sent.append((order.order_id, text))
        log.info("approval requested\n%s", text)
