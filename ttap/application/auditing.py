from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from ttap.domain.models import AuditEvent, Step
from ttap.ports import Clock


class AuditLog(Protocol):
    def append(self, event: AuditEvent) -> AuditEvent: ...
    def list(self, org_id: str | None = None) -> list[AuditEvent]: ...


class Auditor:
    """Builds CloudEvents-shaped audit entries; the log adapter chains and signs them."""

    def __init__(self, log: AuditLog, clock: Clock, new_id: Callable[[str], str]):
        self.log, self._clock, self._new_id = log, clock, new_id

    def record(self, *, org_id: str, step: Step, action: str, subject: str, actor: str, outcome: str,
               explanation: str, data: dict[str, Any] | None = None) -> AuditEvent:
        return self.log.append(AuditEvent(
            id=self._new_id("ev"), type=f"org.ttap.{step}.{action}.v1", subject=subject, time=self._clock.now(),
            org_id=org_id, step=step, actor=actor, outcome=outcome, data=data or {}, explanation=explanation))
