class UpstreamUnavailable(Exception):
    """The supplier system could not answer (network error, repeated 429/5xx)."""
