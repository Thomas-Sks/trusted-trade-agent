from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

import rfc8785

from ttap.domain.models import Offer, OfferLine


def offer_payload(offer: Offer) -> dict:
    return offer.model_dump(mode="json", exclude={"signature"})


def offer_hash(offer: Offer) -> str:
    return "sha256:" + hashlib.sha256(rfc8785.dumps(offer_payload(offer))).hexdigest()


def offer_valid_until(now: datetime, ttl: timedelta, lines: list[OfferLine]) -> datetime:
    bounds = [now + ttl]
    for line in lines:
        for cand in line.tiers.values():
            bounds += [b for b in (cand.price_valid_to, cand.order_cutoff) if b is not None]
    return min(bounds)
