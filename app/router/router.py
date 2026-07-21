"""
Intent Router — top-level entrypoint that orchestrates the tier
fallthrough: normalize -> compound check -> Tier 1 -> Tier 2 -> Tier 3.
(Tier 1.5 pipelines and Workflow Templates are invoked separately via
run_pipeline/run_workflow, not through this single-tool resolver.)
"""

from __future__ import annotations

from app.router.normalize import normalize_text
from app.router.compound_detector import is_compound_request
from app.router import tier1_regex
from app.router import tier2_fuzzy
from app.router import tier3_llm
from app.core.logging_setup import logger
from app.core.exceptions import IntentResolutionError


def resolve_intent(raw_text: str, *, allow_llm: bool = True) -> tuple[str, dict]:
    """
    Resolves raw user text to (tool_name, tool_kwargs). Raises
    IntentResolutionError if no tier can resolve it.

    allow_llm=False skips Tier 3 (useful for tests / cost-sensitive
    contexts that want deterministic-only resolution).
    """
    text = normalize_text(raw_text)

    if is_compound_request(text):
        logger.info("Compound request detected, deferring past Tier 1: {!r}", text)
        raise IntentResolutionError(
            "This looks like a multi-step request. Use a workflow template "
            "or pipeline for multi-action requests.",
            context={"text": text},
        )

    tier1_result = tier1_regex.try_match(text)
    if tier1_result is not None:
        tool_name, tool_kwargs = tier1_result
        logger.info("Tier 1 matched: {!r} -> tool={} kwargs={}", text, tool_name, tool_kwargs)
        return tool_name, tool_kwargs

    tier2_result = tier2_fuzzy.try_match(text)
    if tier2_result is not None:
        return tier2_result

    if allow_llm:
        logger.info("Tiers 1-2 missed, falling through to Tier 3 (LLM): {!r}", text)
        return tier3_llm.resolve_via_llm(text)

    raise IntentResolutionError(
        "Could not resolve this request to a known tool (Tier 1 regex, Tier 2 fuzzy; LLM disabled).",
        context={"text": text},
    )


__all__ = ["resolve_intent"]