from __future__ import annotations

import hashlib
from collections.abc import Callable

import rfc8785

from ttap.domain.models import AuditEvent


def event_hash(event: AuditEvent) -> str:
    body = event.model_dump(mode="json", exclude={"hash", "signature"})
    return "sha256:" + hashlib.sha256(rfc8785.dumps(body)).hexdigest()


def verify_chain(events: list[AuditEvent], jwk: dict, verify: Callable[[dict, dict, str], bool]) -> list[str]:
    """Check one organisation's chain: recomputed hashes, links and signatures. Returns problems (empty = valid).

    `verify(jwk, payload, token)` is injected so the domain never depends on a crypto adapter."""
    problems: list[str] = []
    previous: str | None = None
    for e in events:
        if e.prev_hash != previous:
            problems.append(f"{e.id}: prev_hash does not match previous event (deleted or reordered entry?)")
        recomputed = event_hash(e)
        if e.hash != recomputed:
            problems.append(f"{e.id}: hash mismatch (content modified)")
        if not e.signature or not verify(jwk, {"hash": e.hash}, e.signature):
            problems.append(f"{e.id}: invalid signature")
        previous = e.hash
    return problems
