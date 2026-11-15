import json

from ttap.adapters.outbound.jsonl_audit import JsonlAuditLog
from ttap.adapters.outbound.jws_signer import EcdsaSigner
from ttap.domain.audit_verify import verify_chain
from ttap.domain.models import AuditEvent
from tests.factories import DEMO_NOW


def ev(i: int, org: str = "org_a") -> AuditEvent:
    return AuditEvent(id=f"e{i}", type="org.ttap.order.decided.v1", subject=f"order/or_{i}", time=DEMO_NOW,
                      org_id=org, step="order", actor="system", outcome="success", data={"i": i},
                      explanation=f"event {i}")


def test_chain_is_valid_and_linked(tmp_path):
    signer = EcdsaSigner()
    log = JsonlAuditLog(tmp_path / "audit.jsonl", signer)
    events = [log.append(ev(i)) for i in range(3)]
    assert events[0].prev_hash is None and events[1].prev_hash == events[0].hash
    assert verify_chain(log.list("org_a"), signer.public_jwk(), EcdsaSigner.verify_with_jwk) == []


def test_tampering_and_deletion_are_detected(tmp_path):
    signer = EcdsaSigner()
    path = tmp_path / "audit.jsonl"
    log = JsonlAuditLog(path, signer)
    for i in range(3):
        log.append(ev(i))
    lines = [json.loads(x) for x in path.read_text().splitlines()]
    tampered = [dict(lines[0]), dict(lines[1], explanation="nothing to see"), dict(lines[2])]
    problems = verify_chain([AuditEvent.model_validate(x) for x in tampered], signer.public_jwk(), EcdsaSigner.verify_with_jwk)
    assert any("e1" in p and "hash" in p for p in problems)
    deleted = [AuditEvent.model_validate(x) for x in (lines[0], lines[2])]
    assert any("e2" in p and "prev_hash" in p for p in verify_chain(deleted, signer.public_jwk(), EcdsaSigner.verify_with_jwk))


def test_orgs_have_independent_chains_and_restart_continues(tmp_path):
    signer = EcdsaSigner()
    path = tmp_path / "audit.jsonl"
    log = JsonlAuditLog(path, signer)
    a0 = log.append(ev(0, "org_a"))
    b0 = log.append(ev(1, "org_b"))
    assert b0.prev_hash is None
    restarted = JsonlAuditLog(path, signer)
    a1 = restarted.append(ev(2, "org_a"))
    assert a1.prev_hash == a0.hash
    assert [e.id for e in restarted.list("org_b")] == ["e1"]
    assert len(restarted.list()) == 3
    assert verify_chain(restarted.list("org_a"), signer.public_jwk(), EcdsaSigner.verify_with_jwk) == []
