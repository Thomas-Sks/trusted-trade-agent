"""Mobile-first Telegram HTML rendering of approval cards (presentation only, no business logic)."""
from __future__ import annotations

from datetime import date
from html import escape

from ttap.domain.formatting import duration_minutes, money, qty, shorten
from ttap.domain.models import ApprovalCard, StockStatus

STOCK_LABEL = {
    StockStatus.VERIFIED_QTY: "✅ verified stock",
    StockStatus.VERIFIED_UNLIMITED: "✅ verified stock",
    StockStatus.UNKNOWN_SUPPLIER_STOCK: "❔ unverified supplier stock",
    StockStatus.UNAVAILABLE: "⛔ unavailable",
    StockStatus.STALE: "🕓 stale data",
}


def _day(d: date) -> str:
    return d.strftime("%a %d %b")


def _change(c: str) -> str:
    kind, _, value = c.partition(":")
    return {"origin": f"🌍 origin {value.upper()}", "brand": f"🏷 brand {value}",
            "substitute": f"🔁 substitute for {value}"}.get(kind, f"🔁 {c}")


def render_card_html(card: ApprovalCard, detailed: bool = False) -> str:
    e = escape
    rows = ["🟠 <b>Approval required</b>",
            f"<code>{e(card.org_id)}</code> · <code>{e(card.order_id)}</code>", "", "<b>Why</b>"]
    rows += [f"⛔ {e(r)}" for r in card.reasons] or ["⛔ (no rule)"]
    rows += ["", "<b>Basket</b>"]
    for line in card.lines:
        rows.append(f"📦 <b>{e(shorten(line.name, 38 if not detailed else 80))}</b>")
        rows.append(f"      {qty(line.qty_sales_units)} × €{money(line.unit_net)} → <b>€{money(line.line_total_net)}</b>")
        tags = (["✂️ partial (stock)"] if line.partial else []) + \
            ([f"📈 {line.vs_usual}"] if line.vs_usual else []) + [_change(c) for c in line.changes]
        if detailed:
            tags.append(STOCK_LABEL.get(line.stock, line.stock.value))
        if tags:
            rows.append("      " + " · ".join(e(t) for t in tags))
    if card.warnings:
        rows.append("")
        rows += [f"⚠️ <i>{e(w)}</i>" for w in card.warnings]
    rows += ["", f"💶 <b>€{money(card.total_net)} excl. VAT</b>  (€{money(card.total_gross)} incl. VAT)"]
    if card.delivery_date:
        rows.append(f"🚚 Delivery {_day(card.delivery_date)}")
    if card.minutes_to_cutoff is not None:
        rows.append(f"⏰ Order cut-off in <b>{duration_minutes(card.minutes_to_cutoff)}</b>")
    if card.step_up_required:
        rows.append("🔐 <i>High amount: approve on the web console</i>")
    if detailed:
        rows.append(f"🧾 offer <code>{e(card.offer_hash_short)}</code> · version {card.version}")
    return "\n".join(rows)


def status_html(kind: str, who: str, amount: object | None = None) -> str:
    if kind == "approved":
        return f"✅ <b>Approved</b> by {escape(who)}" + (f" · €{money(amount)} excl. VAT" if amount is not None else "")
    if kind == "rejected":
        return f"❌ <b>Rejected</b> by {escape(who)}"
    return escape(who)
