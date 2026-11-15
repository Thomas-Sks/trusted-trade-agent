from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

import rfc8785

from ttap.domain.models import Candidate, Offer, OfferLine, SelectedLine


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


def resolve_selection(offer: Offer, selected: list[SelectedLine]) -> list[Candidate]:
    """Raises KeyError when a line or tier does not exist in the offer."""
    lines = {line.line_id: line for line in offer.lines}
    return [lines[s.line_id].tiers[s.tier] for s in selected]


def price_lock_until(now: datetime, approval_timeout: timedelta, candidates: list[Candidate]) -> datetime:
    bounds = [now + approval_timeout]
    for c in candidates:
        bounds += [b for b in (c.price_valid_to, c.order_cutoff) if b is not None]
    return min(bounds)
