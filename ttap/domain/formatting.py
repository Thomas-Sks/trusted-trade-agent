"""Human-readable French formatting shared by every channel (deterministic)."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

NBSP = " "


def money(value: object, decimals: int = 2) -> str:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)
    q = d.quantize(Decimal(1).scaleb(-decimals)) if decimals else d.quantize(Decimal(1))
    sign = "-" if q < 0 else ""
    whole, _, frac = f"{abs(q):f}".partition(".")
    groups = []
    while whole:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    out = " ".join(groups) or "0"
    return f"{sign}{out},{frac}" if frac else f"{sign}{out}"


def qty(value: object) -> str:
    d = Decimal(str(value))
    return money(d, 0) if d == d.to_integral_value() else money(d, 2)


def duration_minutes(minutes: int) -> str:
    if minutes < 0:
        return "dépassée"
    days, rem = divmod(minutes, 60 * 24)
    hours, mins = divmod(rem, 60)
    if days:
        return f"{days} j {hours} h"
    if hours:
        return f"{hours} h {mins:02d}"
    return f"{mins} min"


def shorten(text: str, limit: int = 42) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
