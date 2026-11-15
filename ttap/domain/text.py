"""Language-agnostic tokenisation shared by catalogue search and relevance filtering."""
from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-zåäöéü0-9]+")


def tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if len(t) >= 3}
