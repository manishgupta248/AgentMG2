"""
Intent Router — top-level entrypoint that orchestrates the tier
fallthrough: normalize -> compound check -> Tier 1 -> (later: Tier 1.5
-> Tier 2 -> Tier 3 -> Tier 4). For M12 Step 1, only Tier 1 exists;
everything else falls through to "unresolved" for now.
"""

from __future__ import annotations

from app.router.normalize import normalize_text
from app.router.compound_detector import is_compound_request
from app.router import tier1_regex
from app.core.logging_setup import logger
from app.core.exceptions import IntentResolutionError


def resolve_intent(raw_text: str) -> tuple[str, dict]:
    """
    Resolves raw user text to (tool_name, tool_kwargs). Raises
    IntentResolutionError if no tier can resolve it. Currently only
    Tier 1 is implemented — Tier 1.5/2/3/4 are added in later steps.
    """
    text = normalize_text(raw_text)

    if is_compound_request(text):
        logger.info("Compound request detected, deferring past Tier 1: {!r}", text)
        raise IntentResolutionError(
            "This looks like a multi-step request, which isn't supported yet "
            "(Tier 1.5 pipelines land in a later step).",
            context={"text": text},
        )

    tier1_result = tier1_regex.try_match(text)
    if tier1_result is not None:
        tool_name, tool_kwargs = tier1_result
        logger.info("Tier 1 matched: {!r} -> tool={} kwargs={}", text, tool_name, tool_kwargs)
        return tool_name, tool_kwargs

    raise IntentResolutionError(
        "Could not resolve this request to a known tool (Tier 1 regex only, for now).",
        context={"text": text},
    )


__all__ = ["resolve_intent"]