"""
Tier 2 — Fuzzy matching via rapidfuzz. Catches requests that are
CLOSE to a known example phrase but don't hit Tier 1's exact regex.

LESSON FROM PRIOR BUILD: threshold alone is insufficient — a
threshold of 85.5 produced false positives (unrelated requests
fuzzy-matching to the wrong tool). The threshold must be 88.0+ AND
example phrases must be tight/specific (not generic single words)
to avoid false positives even above that threshold.

Fuzzy matching here only determines WHICH TOOL is intended — it does
NOT extract structured parameters the way Tier 1's regex captures
do. A tool matched via Tier 2 is invoked with no kwargs beyond what's
already known; parameter-bearing tools are poor Tier 2 candidates
unless they have sensible defaults or the caller separately supplies
kwargs. This is a real, intentional limitation — Tier 3 (LLM) is what
extracts parameters for free-form phrasing.
"""

from __future__ import annotations

from rapidfuzz import fuzz, process

from app.core.registry import list_tools
from app.core.config import settings
from app.core.logging_setup import logger

MIN_SCORE = 88.0  # hard floor per the documented lesson — do not lower this


def _build_phrase_index() -> list[tuple[str, str]]:
    """Returns [(example_phrase, tool_name), ...] across all registered
    tools that declare example_phrases. Rebuilt on each call rather
    than cached, since the tool registry can grow as more modules are
    imported over a process's lifetime."""
    index: list[tuple[str, str]] = []
    for tool_name, registered in list_tools().items():
        for phrase in registered.example_phrases:
            index.append((phrase, tool_name))
    return index


def try_match(text: str) -> tuple[str, dict] | None:
    """
    Returns (tool_name, {}) if text fuzzy-matches an example phrase
    above MIN_SCORE, else None. Always returns empty kwargs — Tier 2
    determines WHICH tool, not its parameters (see module docstring).
    """
    index = _build_phrase_index()
    if not index:
        return None

    phrases = [p for p, _ in index]
    match = process.extractOne(text, phrases, scorer=fuzz.WRatio, score_cutoff=MIN_SCORE)

    if match is None:
        return None

    matched_phrase, score, phrase_idx = match
    tool_name = index[phrase_idx][1]

    logger.info(
        "Tier 2 fuzzy matched: {!r} ~ {!r} (score={:.1f}) -> tool={}",
        text, matched_phrase, score, tool_name,
    )
    return tool_name, {}


__all__ = ["try_match", "MIN_SCORE"]