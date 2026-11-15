"""Mobile-first Telegram HTML rendering of approval cards (presentation only, no business logic)."""
from __future__ import annotations

from datetime import date
from html import escape

from ttap.domain.formatting import duration_minutes, money, qty, shorten
from ttap.domain.models import ApprovalCard, StockStatus

WEEKDAYS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
STOCK_LABEL = {
    StockStatus.VERIFIED_QTY: "✅ stock vérifié",
    StockStatus.VERIFIED_UNLIMITED: "✅ stock vérifié",
    StockStatus.UNKNOWN_SUPPLIER_STOCK: "❔ stock fournisseur non vérifié",
    StockStatus.UNAVAILABLE: "⛔ indisponible",
    StockStatus.STALE: "🕓 donnée périmée",
}


def _day(d: date) -> str:
    return f"{WEEKDAYS[d.weekday()]} {d.day:02d}/{d.month:02d}"


def _change(c: str) -> str:
    kind, _, value = c.partition(":")
    return {"origin": f"🌍 origine {value.upper()}", "brand": f"🏷 marque {value}",
            "substitute": f"🔁 substitut de {value}"}.get(kind, f"🔁 {c}")


def render_card_html(card: ApprovalCard, detailed: bool = False) -> str:
    e = escape
    rows = ["🟠 <b>Validation requise</b>",
            f"<code>{e(card.org_id)}</code> · <code>{e(card.order_id)}</code>", "", "<b>Pourquoi</b>"]
    rows += [f"⛔ {e(r)}" for r in card.reasons] or ["⛔ (aucune règle)"]
    rows += ["", "<b>Panier</b>"]
    for line in card.lines:
        rows.append(f"📦 <b>{e(shorten(line.name, 38 if not detailed else 80))}</b>")
        rows.append(f"      {qty(line.qty_sales_units)} × {money(line.unit_net)} € → <b>{money(line.line_total_net)} €</b>")
        tags = (["✂️ partiel (stock)"] if line.partial else []) + \
            ([f"📈 {line.vs_usual}"] if line.vs_usual else []) + [_change(c) for c in line.changes]
        if detailed:
            tags.append(STOCK_LABEL.get(line.stock, line.stock.value))
        if tags:
            rows.append("      " + " · ".join(e(t) for t in tags))
    if card.warnings:
        rows.append("")
        rows += [f"⚠️ <i>{e(w)}</i>" for w in card.warnings]
    rows += ["", f"💶 <b>{money(card.total_net)} € HT</b>  ({money(card.total_gross)} € TTC)"]
    if card.delivery_date:
        rows.append(f"🚚 Livraison {_day(card.delivery_date)}")
    if card.minutes_to_cutoff is not None:
        rows.append(f"⏰ Heure limite : <b>{duration_minutes(card.minutes_to_cutoff)}</b>")
    if card.step_up_required:
        rows.append("🔐 <i>Montant élevé : validation sur la page web</i>")
    if detailed:
        rows.append(f"🧾 offre <code>{e(card.offer_hash_short)}</code> · version {card.version}")
    return "\n".join(rows)


def status_html(kind: str, who: str, amount: object | None = None) -> str:
    if kind == "approved":
        return f"✅ <b>Approuvée</b> par {escape(who)}" + (f" · {money(amount)} € HT" if amount is not None else "")
    if kind == "rejected":
        return f"❌ <b>Refusée</b> par {escape(who)}"
    return escape(who)
