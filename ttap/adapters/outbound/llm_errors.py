"""Turns Anthropic API failures into codes and plain-English messages an operator can act on."""
from __future__ import annotations

import anthropic

_STILL_WORKS = "Lookup, orders, approvals and the replenishment bot (no AI) still work."


def describe_llm_error(exc: BaseException) -> tuple[str, str]:
    text = str(exc).lower()
    status = getattr(exc, "status_code", None)
    if status == 402 or "credit balance" in text or "billing" in text:
        return ("AI_CREDITS_EXHAUSTED",
                f"The Anthropic API key has no credit left, so the AI agent cannot run. {_STILL_WORKS}")
    if isinstance(exc, anthropic.AuthenticationError | anthropic.PermissionDeniedError) or status in (401, 403):
        return "AI_KEY_INVALID", f"The Anthropic API key is invalid or revoked. {_STILL_WORKS}"
    if isinstance(exc, anthropic.RateLimitError) or status == 429:
        return "AI_RATE_LIMITED", "The Anthropic API is rate-limiting this key. Try again in a minute."
    if status == 529 or "overloaded" in text:
        return "AI_OVERLOADED", "The Anthropic API is temporarily overloaded. Try again in a moment."
    return "AI_UNAVAILABLE", f"The AI service is unavailable ({type(exc).__name__}). {_STILL_WORKS}"


class LLMFailure(Exception):
    """Raised by LLM adapters; `code` is one of the AI_* codes above."""

    def __init__(self, exc: BaseException):
        self.code, message = describe_llm_error(exc)
        super().__init__(message)
