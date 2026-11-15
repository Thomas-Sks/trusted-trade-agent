from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ttap.application.auditing import Auditor
from ttap.application.errors import NotFound
from ttap.domain.models import Mandate
from ttap.domain.simulation import SimulationResult, replay
from ttap.ports import MandateRepository, PolicyEngine


class MandateChanges(BaseModel):
    """Only the parameters an approver may tune; anything else is rejected."""
    model_config = ConfigDict(extra="forbid")
    limit_per_order_net: Decimal | None = None
    max_unverified_value_net: Decimal | None = None
    period_budget_net: Decimal | None = None
    max_orders_per_hour: int | None = None


class MandateService:
    def __init__(self, mandates: MandateRepository, policy: PolicyEngine, auditor: Auditor):
        self._mandates, self._policy, self._auditor = mandates, policy, auditor

    def get(self, org_id: str) -> Mandate:
        mandate = self._mandates.get(org_id)
        if mandate is None:
            raise NotFound(f"mandate for {org_id}")
        return mandate

    def simulate(self, org_id: str, changes: MandateChanges) -> SimulationResult:
        candidate = self.get(org_id).model_copy(update=changes.model_dump(exclude_none=True))
        decided = [e for e in self._auditor.log.list(org_id) if e.type == "org.ttap.approval.decided.v1"]
        return replay(decided, candidate, self._policy.decide)
