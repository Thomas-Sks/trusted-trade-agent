from datetime import timedelta

from ttap.domain.models import AuditEvent
from ttap.domain.oversight import oversight_stats
from tests.factories import DEMO_NOW


def ev(kind: str, order: str, secs: float) -> AuditEvent:
    return AuditEvent(id=f"{kind}{order}", type=f"org.ttap.approval.{kind}.v1", subject=f"order/{order}",
                      time=DEMO_NOW + timedelta(seconds=secs), org_id="o", step="approval", actor="x", outcome="x")


def test_fast_approvals_flag_rubber_stamp_risk():
    events = []
    for i, latency in enumerate([2, 3, 1, 40]):
        events += [ev("escalated", str(i), 0), ev("approved", str(i), latency)]
    s = oversight_stats(events)
    assert s.approved == 4 and s.approved_under_5s_pct == 75.0 and s.rubber_stamp_risk is False
    s2 = oversight_stats(events + [ev("escalated", "9", 0), ev("approved", "9", 1)])
    assert s2.approved_under_5s_pct == 80.0 and s2.rubber_stamp_risk is True
    assert "under 5 s" in s2.summary


def test_no_data():
    assert oversight_stats([]).summary == "No human approval recorded yet"
