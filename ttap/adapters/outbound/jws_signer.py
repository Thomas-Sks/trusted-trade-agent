from __future__ import annotations

import json
import os
from pathlib import Path

import rfc8785
from joserfc import jws
from joserfc.errors import JoseError
from joserfc.jwk import ECKey


def _verify(key: ECKey, payload: dict, token: str) -> bool:
    try:
        obj = jws.deserialize_compact(token, key)
    except JoseError:
        return False
    return obj.payload == rfc8785.dumps(payload)


class EcdsaSigner:
    def __init__(self, key: ECKey | None = None, kid: str = "ttap-1"):
        self._key = key or ECKey.generate_key("P-256")
        self.kid = kid

    @classmethod
    def load_or_create(cls, path: str | Path, kid: str = "ttap-1") -> EcdsaSigner:
        path = Path(path)
        if path.exists():
            return cls(ECKey.import_key(json.loads(path.read_text())), kid)
        signer = cls(kid=kid)
        path.write_text(json.dumps(signer._key.as_dict(private=True)))
        os.chmod(path, 0o600)
        return signer

    @staticmethod
    def verify_with_jwk(jwk: dict, payload: dict, token: str) -> bool:
        public = {k: v for k, v in jwk.items() if k != "kid"}
        return _verify(ECKey.import_key(public), payload, token)

    def sign(self, payload: dict) -> str:
        return jws.serialize_compact({"alg": "ES256", "kid": self.kid}, rfc8785.dumps(payload), self._key)

    def verify(self, payload: dict, token: str) -> bool:
        return _verify(self._key, payload, token)

    def public_jwk(self) -> dict:
        jwk = self._key.as_dict(private=False)
        jwk["kid"] = self.kid
        return jwk
