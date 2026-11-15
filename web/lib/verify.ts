// Independent TypeScript implementation of the TTAP trust check: ES256 JWS over the RFC 8785 (JCS)
// canonical form of the offer. The gateway is Python; this proves the protocol is language-neutral.
import canonicalize from "canonicalize";
import { compactVerify, importJWK, type JWK } from "jose";

export async function verifyOffer(offer: Record<string, unknown>, jwk: JWK): Promise<boolean> {
  const signature = offer.signature;
  if (typeof signature !== "string") return false;
  const { signature: _omit, ...payload } = offer;
  void _omit;
  try {
    const { kid: _kid, ...publicJwk } = jwk;
    void _kid;
    const key = await importJWK(publicJwk, "ES256");
    const { payload: signed } = await compactVerify(signature, key);
    return new TextDecoder().decode(signed) === canonicalize(payload);
  } catch {
    return false;
  }
}
