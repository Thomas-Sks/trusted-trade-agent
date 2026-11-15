"""Human-readable English formatting shared by every channel (deterministic)."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation


def money(value: object, decimals: int = 2) -> str:
    """3030 -> '3,030.00'."""
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)
    return f"{d:,.{decimals}f}"


def qty(value: object) -> str:
    d = Decimal(str(value))
    return money(d, 0) if d == d.to_integral_value() else money(d, 2)


def duration_minutes(minutes: int) -> str:
    if minutes < 0:
        return "passed"
    days, rem = divmod(minutes, 60 * 24)
    hours, mins = divmod(rem, 60)
    if days:
        return f"{days} d {hours} h"
    if hours:
        return f"{hours} h {mins:02d}"
    return f"{mins} min"


def shorten(text: str, limit: int = 42) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def when(dt) -> str:
    """'Mon 16 Nov, 08:30' (date or datetime)."""
    base = dt.strftime("%a %d %b")
    return f"{base}, {dt.hour:02d}:{dt.minute:02d}" if hasattr(dt, "hour") else base
