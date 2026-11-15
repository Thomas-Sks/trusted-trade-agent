"""What-if replay: re-run recorded decisions with a modified mandate. Deterministic and side-effect free.

Each `approval.decided` audit event stores the exact Cedar context the gateway evaluated. Only the mandate-derived
parameters are swapped; everything observed at the time (amounts, stock certainty, substitutions, committed spend,
order pace) is kept as recorded.
"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from ttap.domain.decision import UNLIMITED_COUNT, UNLIMITED_MONEY
from ttap.domain.models import AuditEvent, Mandate

MONEY_SUFFIXES = ("_net", "_value")


class ReplayedDecision(BaseModel):
    order_id: str
    total_net: Decimal
    before: str
    after: str
    rules_before: list[str]
    rules_after: list[str]


class SimulationResult(BaseModel):
    replayed: int
    changed: int
    summary: str
    changes: list[ReplayedDecision]
    note: str = ("Amounts, stock certainty, substitutions, committed spend and order pace are replayed as recorded; "
                 "only the mandate parameters change.")


# Facts added to the policy context after some decisions were recorded: neutral values, so an old decision is
# replayed exactly as it was evaluated (a missing attribute would otherwise make Cedar fail closed).
CONTEXT_DEFAULTS = {"has_partial": False, "data_stale": False, "has_origin_conflict": False,
                    "has_changes_vs_request": False, "unverified_value_net": "0", "orders_last_hour": 1}


def restore_context(recorded: dict) -> dict:
    """Audit JSON -> typed Cedar context (money back to Decimal), with neutral defaults for later-added facts."""
    recorded = CONTEXT_DEFAULTS | {"period_spend_net": recorded.get("total_net", "0")} | recorded
    out = {}
    for key, value in recorded.items():
        if key.endswith(MONEY_SUFFIXES) and isinstance(value, str):
            out[key] = Decimal(value)
        else:
            out[key] = value
    return out


def mandate_params(m: Mandate) -> dict:
    return {
        "limit_per_order_net": m.limit_per_order_net,
        "max_unverified_value_net": m.max_unverified_value_net,
        "period_budget_net": m.period_budget_net if m.period_budget_net is not None else UNLIMITED_MONEY,
        "max_orders_per_hour": m.max_orders_per_hour if m.max_orders_per_hour is not None else UNLIMITED_COUNT,
    }


def replay(decided_events: list[AuditEvent], candidate: Mandate, decide) -> SimulationResult:
    params = mandate_params(candidate)
    changes: list[ReplayedDecision] = []
    for event in decided_events:
        context = restore_context(event.data["context"]) | params
        new = decide(context)
        order_id = event.subject.removeprefix("order/")
        if new.outcome != event.outcome:
            changes.append(ReplayedDecision(order_id=order_id, total_net=context["total_net"], before=event.outcome,
                                            after=new.outcome, rules_before=event.data.get("rules_fired", []),
                                            rules_after=new.rules_fired))
    n, k = len(decided_events), len(changes)
    summary = (f"{k} of {n} past order{'s' if n != 1 else ''} would have changed decision" if n
               else "No past decisions to replay yet")
    return SimulationResult(replayed=n, changed=k, summary=summary, changes=changes)
