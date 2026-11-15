from datetime import timedelta

from ttap.adapters.outbound.jws_signer import EcdsaSigner
from ttap.domain.models import Offer
from ttap.domain.offer import offer_hash, offer_payload, offer_valid_until
from tests.factories import DEMO_NOW


def make_offer() -> Offer:
    return Offer(offer_id="of_1", request_id="rq_1", org_id="org_a", issued_at=DEMO_NOW,
                 valid_until=DEMO_NOW + timedelta(minutes=30), catalog_version="sha256:x", lines=[])


def test_signature_roundtrip_and_tamper_detection():
    signer = EcdsaSigner()
    offer = make_offer()
    token = signer.sign(offer_payload(offer))
    assert signer.verify(offer_payload(offer), token)
    tampered = offer.model_copy(update={"org_id": "org_b"})
    assert not signer.verify(offer_payload(tampered), token)
    assert not signer.verify(offer_payload(offer), "garbage")


def test_hash_ignores_signature_field():
    offer = make_offer()
    signed = offer.model_copy(update={"signature": "abc"})
    assert offer_hash(offer) == offer_hash(signed)
    assert offer_hash(offer).startswith("sha256:")


def test_public_jwk_has_kid_and_no_private_part():
    jwk = EcdsaSigner(kid="k9").public_jwk()
    assert jwk["kid"] == "k9" and "d" not in jwk


def test_valid_until_is_capped_by_ttl_when_no_line_constraints():
    assert offer_valid_until(DEMO_NOW, timedelta(minutes=30), []) == DEMO_NOW + timedelta(minutes=30)


def test_key_is_persisted_and_reloaded(tmp_path):
    path = tmp_path / "key.json"
    first = EcdsaSigner.load_or_create(path)
    token = first.sign({"a": 1})
    second = EcdsaSigner.load_or_create(path)
    assert second.verify({"a": 1}, token)
    assert second.public_jwk() == first.public_jwk()


def test_verify_with_public_jwk_only():
    signer = EcdsaSigner()
    token = signer.sign({"a": 1})
    assert EcdsaSigner.verify_with_jwk(signer.public_jwk(), {"a": 1}, token)
    assert not EcdsaSigner.verify_with_jwk(signer.public_jwk(), {"a": 2}, token)
