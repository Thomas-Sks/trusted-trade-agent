"""Verify an audit log offline with only the gateway's public key.

Usage: uv run python scripts/verify_audit.py audit.jsonl jwk.json
(jwk.json = the key published at /.well-known/ttap.json -> jwks.keys[0])
"""
import json
import sys
from collections import defaultdict

from ttap.adapters.outbound.jws_signer import EcdsaSigner
from ttap.domain.audit_verify import verify_chain
from ttap.domain.models import AuditEvent


def main(log_path: str, jwk_path: str) -> int:
    jwk = json.loads(open(jwk_path).read())
    chains: dict[str, list[AuditEvent]] = defaultdict(list)
    for line in open(log_path):
        if line.strip():
            event = AuditEvent.model_validate_json(line)
            chains[event.org_id].append(event)
    failed = False
    for org, events in chains.items():
        problems = verify_chain(events, jwk, EcdsaSigner.verify_with_jwk)
        status = "chain valid" if not problems else f"{len(problems)} problem(s)"
        print(f"{org}: {len(events)} events — {status}")
        for p in problems:
            print("   ", p)
        failed |= bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
