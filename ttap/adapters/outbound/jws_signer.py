from __future__ import annotations

import rfc8785
from joserfc import jws
from joserfc.errors import JoseError
from joserfc.jwk import ECKey


class EcdsaSigner:
    def __init__(self, key: ECKey | None = None, kid: str = "ttap-1"):
        self._key = key or ECKey.generate_key("P-256")
        self.kid = kid

    def sign(self, payload: dict) -> str:
        return jws.serialize_compact({"alg": "ES256", "kid": self.kid}, rfc8785.dumps(payload), self._key)

    def verify(self, payload: dict, token: str) -> bool:
        try:
            obj = jws.deserialize_compact(token, self._key)
        except JoseError:
            return False
        return obj.payload == rfc8785.dumps(payload)

    def public_jwk(self) -> dict:
        jwk = self._key.as_dict(private=False)
        jwk["kid"] = self.kid
        return jwk
