class TTAPError(Exception):
    code = "ERROR"
    status = 400


class NotFound(TTAPError):
    code, status = "NOT_FOUND", 404


class OfferExpired(TTAPError):
    code, status = "OFFER_EXPIRED", 409


class OfferAlreadyUsed(TTAPError):
    code, status = "OFFER_ALREADY_USED", 409


class InvalidOfferSignature(TTAPError):
    code, status = "INVALID_OFFER_SIGNATURE", 400


class InvalidSelection(TTAPError):
    code, status = "INVALID_SELECTION", 422


class IdempotencyMismatch(TTAPError):
    code, status = "IDEMPOTENCY_MISMATCH", 422


class UpstreamError(TTAPError):
    code, status = "UPSTREAM_UNAVAILABLE", 503


class Conflict(TTAPError):
    code, status = "CONFLICT", 409


class PriceLockExpired(TTAPError):
    code, status = "PRICE_LOCK_EXPIRED", 409


class StockChanged(TTAPError):
    code, status = "STOCK_CHANGED", 409
