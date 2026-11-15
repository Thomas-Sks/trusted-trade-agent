import httpx
import anthropic

from ttap.adapters.outbound.llm_errors import describe_llm_error


def _status_error(cls, status: int, message: str):
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls(message, response=httpx.Response(status, request=req), body=None)


def test_exhausted_credit_is_named_explicitly():
    exc = _status_error(anthropic.BadRequestError, 400,
                        "Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing.")
    code, message = describe_llm_error(exc)
    assert code == "AI_CREDITS_EXHAUSTED"
    assert "credit" in message and "still work" in message


def test_invalid_key_and_overload_and_unknown():
    assert describe_llm_error(_status_error(anthropic.AuthenticationError, 401, "invalid x-api-key"))[0] == "AI_KEY_INVALID"
    assert describe_llm_error(_status_error(anthropic.RateLimitError, 429, "rate limited"))[0] == "AI_RATE_LIMITED"
    assert describe_llm_error(_status_error(anthropic.InternalServerError, 529, "Overloaded"))[0] == "AI_OVERLOADED"
    assert describe_llm_error(ValueError("boom"))[0] == "AI_UNAVAILABLE"
