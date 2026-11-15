from __future__ import annotations

from datetime import UTC, datetime, timedelta


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    def __init__(self, at: datetime):
        self.at = at

    def now(self) -> datetime:
        return self.at


class ShiftedClock:
    """Demo clock: starts at `start` and advances in real time (mock data is frozen around 2026-11-12)."""

    def __init__(self, start: datetime):
        self._start = start
        self._boot = datetime.now(UTC)
        self._offset = timedelta(0)

    def advance(self, minutes: float) -> datetime:
        self._offset += timedelta(minutes=minutes)
        return self.now()

    def now(self) -> datetime:
        return self._start + (datetime.now(UTC) - self._boot) + self._offset
