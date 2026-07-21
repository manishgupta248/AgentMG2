"""
Input normalization — applied before ANY tier attempts matching.

Lesson from prior build: mobile keyboard smart/curly quotes and stray
spaces around apostrophes broke literal pattern matches (e.g. a
message typed on a phone sends " ' " as a curly ’ character, silently
failing a regex that expects a straight apostrophe).
"""

from __future__ import annotations

_REPLACEMENTS = {
    "\u2018": "'",  # left single quote
    "\u2019": "'",  # right single quote
    "\u201c": '"',  # left double quote
    "\u201d": '"',  # right double quote
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u00a0": " ",  # non-breaking space
}


def normalize_text(text: str) -> str:
    """Normalizes smart quotes/dashes/nbsp to plain ASCII equivalents,
    collapses repeated whitespace, and strips leading/trailing space."""
    result = text
    for smart, plain in _REPLACEMENTS.items():
        result = result.replace(smart, plain)
    result = " ".join(result.split())  # collapse all whitespace runs to single spaces
    return result.strip()


__all__ = ["normalize_text"]