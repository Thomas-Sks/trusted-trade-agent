from __future__ import annotations

import threading
from pathlib import Path

from ttap.domain.audit_verify import event_hash
from ttap.domain.models import AuditEvent
from ttap.ports import Signer


class JsonlAuditLog:
    """Append-only JSONL log, one hash chain per organisation, every entry signed (ES256)."""

    def __init__(self, path: str | Path, signer: Signer):
        self._path = Path(path)
        self._signer = signer
        self._lock = threading.Lock()
        self._events: list[AuditEvent] = []
        self._heads: dict[str, str] = {}
        if self._path.exists():
            for line in self._path.read_text().splitlines():
                if line.strip():
                    event = AuditEvent.model_validate_json(line)
                    self._events.append(event)
                    self._heads[event.org_id] = event.hash or ""

    def append(self, event: AuditEvent) -> AuditEvent:
        with self._lock:
            chained = event.model_copy(update={"prev_hash": self._heads.get(event.org_id), "hash": None,
                                               "signature": None})
            digest = event_hash(chained)
            signed = chained.model_copy(update={"hash": digest, "signature": self._signer.sign({"hash": digest})})
            with self._path.open("a") as fh:
                fh.write(signed.model_dump_json() + "\n")
            self._events.append(signed)
            self._heads[event.org_id] = digest
            return signed

    def list(self, org_id: str | None = None) -> list[AuditEvent]:
        with self._lock:
            return [e for e in self._events if org_id is None or e.org_id == org_id]


class MemoryAuditLog(JsonlAuditLog):
    """Same chaining and signing, written to a throwaway file (tests and in-memory setups)."""

    def __init__(self, signer: Signer, path: str | Path | None = None):
        import tempfile
        super().__init__(path or Path(tempfile.mkstemp(suffix=".jsonl")[1]), signer)
