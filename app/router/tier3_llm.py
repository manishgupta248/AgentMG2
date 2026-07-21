"""
Tier 3 — LLM single-tool resolution. Gemini primary, Groq fallback.
Used only when Tier 1 (regex), Tier 1.5 (pipelines, invoked
separately), and Tier 2 (fuzzy) all fail to resolve a request.

LESSON 1: Gemini's structured output rejects dict[str, Any] /
open-ended additionalProperties schemas. tool_kwargs is therefore
requested as a JSON STRING field (kwargs_json), not a raw dict field,
and parsed client-side after the LLM responds.

LESSON 2: the LLM must be given REAL parameter names (from each
tool's actual Pydantic input_schema fields) and told the real return
shape conventions — a prior planner guessed wrong parameter names
and assumed a dict-wrapped list when a tool actually returned a bare
list. The tool catalog built here reflects real schemas, and the
system prompt documents the list_* convention explicitly.

Every LLM-selected tool call still goes through call_tool() — the
LLM only ever produces a structured DECISION (which tool, what
params), never executes anything directly, per the project's
"LLMs never perform operations directly" constraint.
"""

from __future__ import annotations

import json

from pydantic import BaseModel

from app.core.registry import list_tools, get_tool
from app.core.config import settings
from app.core.logging_setup import logger
from app.core.exceptions import LLMProviderError, IntentResolutionError


class LLMToolDecision(BaseModel):
    """
    The LLM's structured output shape. tool_kwargs_json is a JSON
    STRING (not a dict field) — see LESSON 1 in the module docstring.
    reasoning is included to make wrong decisions debuggable, not
    used programmatically.
    """
    tool_name: str
    tool_kwargs_json: str  # JSON-encoded dict, parsed after the call
    reasoning: str


def _build_tool_catalog() -> str:
    """
    Builds a text catalog of available tools with REAL parameter
    names (from each tool's actual input_schema), not just
    descriptions — per LESSON 2. Also documents the list_* return
    shape convention explicitly, since a prior planner assumed a
    dict-wrapped list when a tool returned a bare list.
    """
    lines = [
        "Available tools (tool_name: description [params: real_param_names]):",
        "",
    ]
    for tool_name, registered in sorted(list_tools().items()):
        if tool_name.startswith("_test_"):
            continue  # exclude test-only tools from the real catalog
        param_names = []
        if registered.input_schema is not None:
            param_names = list(registered.input_schema.model_fields.keys())
        lines.append(f"- {tool_name}: {registered.description} [params: {param_names}]")

    lines.append("")
    lines.append(
        "RETURN SHAPE CONVENTION: tools whose name starts with 'list_' or "
        "contain 'search'/'list' in their behavior typically return a LIST "
        "directly as their result data, NOT a dict wrapping a list under a "
        "named field. Tools like kb_get return a single dict. Check the "
        "tool's description for its actual shape when in doubt."
    )
    return "\n".join(lines)


def _build_system_prompt() -> str:
    from datetime import datetime, timezone
    catalog = _build_tool_catalog()
    current_dt = datetime.now(timezone.utc)
    return (
        "You are a tool-selection assistant for a personal AI agent. "
        f"The current date and time is {current_dt.isoformat()} (UTC). "
        "Use this as the actual real-world 'now' for any date-relative "
        "request (e.g. 'today', 'tomorrow', 'this week') — do NOT guess "
        "or use a placeholder date from your training data.\n\n"
        "Given a user's request, select EXACTLY ONE tool from the catalog "
        "below that best fulfills it, and produce the correct arguments "
        "for that tool using its REAL parameter names.\n\n"
        f"{catalog}\n\n"
        "Respond with a JSON object with exactly these fields:\n"
        '{"tool_name": "<exact tool name from the catalog>", '
        '"tool_kwargs_json": "<a JSON-encoded STRING containing the arguments as a dict, e.g. \'{\\"text\\": \\"hello\\"}\'>", '
        '"reasoning": "<brief explanation of your choice>"}\n\n'
        "IMPORTANT: tool_kwargs_json must be a STRING containing valid JSON, "
        "not a nested JSON object. If a tool takes no arguments, use \"{}\".\n"
        "Respond with ONLY the JSON object, no markdown formatting, no preamble."
    )


def _try_gemini(user_text: str) -> LLMToolDecision:
    from google import genai

    client = genai.Client(api_key=settings.gemini_api_key)
    system_prompt = _build_system_prompt()

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=f"{system_prompt}\n\nUser request: {user_text}",
        config={
            "response_mime_type": "application/json",
            "response_schema": LLMToolDecision,
        },
    )

    decision = LLMToolDecision.model_validate_json(response.text)
    return decision


def _try_groq(user_text: str) -> LLMToolDecision:
    from groq import Groq

    client = Groq(api_key=settings.groq_api_key)
    system_prompt = _build_system_prompt()

    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    decision = LLMToolDecision.model_validate_json(raw)
    return decision


def resolve_via_llm(user_text: str) -> tuple[str, dict]:
    """
    Attempts Gemini first, falls back to Groq on any failure. Raises
    LLMProviderError if BOTH fail. Raises IntentResolutionError if the
    LLM picks a tool_name that isn't actually registered (LLM
    hallucination guard).
    """
    decision: LLMToolDecision | None = None
    gemini_error: Exception | None = None

    try:
        decision = _try_gemini(user_text)
        logger.info("Tier 3 (Gemini) decision: tool={} reasoning={!r}", decision.tool_name, decision.reasoning)
    except Exception as e:
        gemini_error = e
        logger.warning("Tier 3 Gemini call failed, falling back to Groq: {}", e)

    if decision is None:
        try:
            decision = _try_groq(user_text)
            logger.info("Tier 3 (Groq fallback) decision: tool={} reasoning={!r}", decision.tool_name, decision.reasoning)
        except Exception as groq_error:
            raise LLMProviderError(
                f"Both Gemini and Groq failed to resolve intent. "
                f"Gemini error: {gemini_error}. Groq error: {groq_error}",
                context={"user_text": user_text},
            ) from groq_error

    if get_tool(decision.tool_name) is None:
        raise IntentResolutionError(
            f"LLM selected tool '{decision.tool_name}', which is not registered "
            f"(possible hallucination).",
            context={"user_text": user_text, "hallucinated_tool": decision.tool_name},
        )

    try:
        tool_kwargs = json.loads(decision.tool_kwargs_json)
    except json.JSONDecodeError as e:
        raise IntentResolutionError(
            f"LLM produced invalid JSON in tool_kwargs_json: {decision.tool_kwargs_json!r}",
            context={"user_text": user_text},
        ) from e

    return decision.tool_name, tool_kwargs


__all__ = ["resolve_via_llm", "LLMToolDecision"]