"""
Compound-request detector.

Lesson from prior build: a single-tool Tier 1 regex's .search() could
match an embedded sub-phrase within a longer, multi-action request,
silently ignoring the rest (e.g. "ping the server and then email me
the result" matched the ping pattern and the email half was dropped
entirely, with no error). Compound requests must be detected BEFORE
Tier 1 attempts a match, and deferred to pipeline/LLM tiers instead
of accepting a confidently-wrong partial match.
"""

from __future__ import annotations

import re

# Conjunctions/phrasing that typically indicate multiple sequential
# actions in one message. Kept as a simple heuristic list — not
# exhaustive, but catches the common cases; false negatives fall
# through to Tier 1 (acceptable), false positives just defer to a
# higher tier unnecessarily (safe, just slightly less optimal).
_COMPOUND_MARKERS = [
    r"\band then\b",
    r"\bthen\b",
    r"\bafter that\b",
    r"\bfollowed by\b",
    r"\band also\b",
]

_COMPOUND_PATTERN = re.compile("|".join(_COMPOUND_MARKERS), re.IGNORECASE)


def is_compound_request(text: str) -> bool:
    """Returns True if the text appears to describe multiple sequential
    actions, and should therefore be deferred past Tier 1's
    single-tool matching."""
    return bool(_COMPOUND_PATTERN.search(text))


__all__ = ["is_compound_request"]