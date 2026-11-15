from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import cedarpy

from ttap.domain.models import Decision

ACTIONS = ("submit_order", "auto_approve")


def _cedar_value(value: object) -> object:
    if isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        return {"__extn": {"fn": "decimal", "arg": str(value.quantize(Decimal("0.0001")))}}
    return value


class CedarPolicyEngine:
    def __init__(self, policies: str):
        self._policies = policies

    @classmethod
    def from_file(cls, path: str | Path) -> CedarPolicyEngine:
        return cls(Path(path).read_text())

    def decide(self, context: dict) -> Decision:
        cedar_ctx = {k: _cedar_value(v) for k, v in context.items()}
        requests = [{"principal": 'Agent::"agent"', "action": f'Action::"{a}"',
                     "resource": 'Order::"order"', "context": cedar_ctx} for a in ACTIONS]
        try:
            submit, auto = cedarpy.is_authorized_batch(requests, self._policies, [])
        except Exception:  # unparsable policies: fail closed
            return Decision(outcome="DENIED", rules_fired=["policy_evaluation_error"], context=context)
        if submit.diagnostics.errors or auto.diagnostics.errors:
            return Decision(outcome="DENIED", rules_fired=["policy_evaluation_error"], context=context)
        if not submit.allowed:
            return Decision(outcome="DENIED", rules_fired=self._fired(submit), context=context)
        if auto.allowed:
            return Decision(outcome="AUTO_APPROVED", rules_fired=[], context=context)
        return Decision(outcome="PENDING_HUMAN", rules_fired=self._fired(auto), context=context)

    @staticmethod
    def _fired(result: cedarpy.AuthzResult) -> list[str]:
        return sorted(result.diagnostics.id_annotations_by_reason.values())
