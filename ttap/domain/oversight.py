"""Oversight quality from the audit log: how fast do humans approve? Near-instant approvals are a rubber-stamp risk."""
from __future__ import annotations

from statistics import median

from pydantic import BaseModel

from ttap.domain.models import AuditEvent

FAST_SECONDS = 5.0


class OversightStats(BaseModel):
    human_decisions: int
    approved: int
    rejected: int
    median_seconds: float | None
    approved_under_5s_pct: float | None
    rubber_stamp_risk: bool
    summary: str


def oversight_stats(events: list[AuditEvent]) -> OversightStats:
    sent: dict[str, float] = {}
    latencies: list[float] = []
    approved = rejected = 0
    for e in events:
        if e.type == "org.ttap.approval.escalated.v1":
            sent.setdefault(e.subject, e.time.timestamp())
        elif e.type in ("org.ttap.approval.approved.v1", "org.ttap.approval.rejected.v1"):
            approved += e.type.endswith("approved.v1")
            rejected += e.type.endswith("rejected.v1")
            if e.subject in sent and e.type.endswith("approved.v1"):
                latencies.append(max(e.time.timestamp() - sent[e.subject], 0.0))
    fast = (100.0 * sum(1 for x in latencies if x < FAST_SECONDS) / len(latencies)) if latencies else None
    risk = fast is not None and len(latencies) >= 3 and fast >= 80.0
    if not latencies:
        summary = "No human approval recorded yet"
    else:
        summary = f"{fast:.0f}% of approvals were given in under 5 s (median {median(latencies):.1f} s)"
        if risk:
            summary += " (possible rubber-stamping)"
    return OversightStats(human_decisions=approved + rejected, approved=approved, rejected=rejected,
                          median_seconds=round(median(latencies), 1) if latencies else None,
                          approved_under_5s_pct=round(fast, 1) if fast is not None else None,
                          rubber_stamp_risk=risk, summary=summary)
