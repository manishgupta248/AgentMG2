"""
Tier 4 — Dynamic multi-step planning. Used only when the STEP
SEQUENCE ITSELF must be inferred, not just a single tool's parameters
(Tier 3) or a fixed hand-declared sequence (Tier 1.5/Workflow
Templates). The LLM produces a plan (ordered list of tool_name +
tool_kwargs, where tool_kwargs may contain $stepN references to prior
steps in THIS plan) — reusing the exact same reference_resolver from
M12, not a new mechanism.

LESSON FROM PRIOR BUILD: the planner guessed wrong parameter names
and wrong return shapes until given the real tool catalog (same
_build_tool_catalog from Tier 3, reused here) — this is why Tier 3
and Tier 4 share the catalog builder rather than each maintaining
their own.

LESSON: cross-step type mismatches (an int output feeding a function
expecting to slice a string) are fixed via deterministic type
coercion based on the TARGET tool's real Pydantic type hints — applied
here in _coerce_step_kwargs before execution, not left to chance.
"""

from __future__ import annotations

import json
from typing import get_type_hints

from pydantic import BaseModel

from app.core.config import settings
from app.core.logging_setup import logger
from app.core.registry import get_tool
from app.core.approval import ApprovalHandler
from app.core.executor import call_tool
from app.core.types import ToolResult
from app.core.exceptions import WorkflowError, IntentResolutionError, LLMProviderError
from app.router.tier3_llm import _build_tool_catalog
from app.router.reference_resolver import resolve_kwargs


class PlannedStep(BaseModel):
    tool_name: str
    tool_kwargs_json: str  # same JSON-string encoding as Tier 3, for the same Gemini-compatibility reason


class DynamicPlan(BaseModel):
    steps: list[PlannedStep]
    reasoning: str


def _build_planning_prompt(user_text: str) -> str:
    from datetime import datetime, timezone
    catalog = _build_tool_catalog()
    current_dt = datetime.now(timezone.utc)
    return (
        "You are a planning assistant for a personal AI agent. The user's "
        "request requires MULTIPLE sequential tool calls to fulfill, where "
        "later steps may depend on results from earlier steps. "
        f"The current date and time is {current_dt.isoformat()} (UTC).\n\n"
        f"{catalog}\n\n"
        "Produce an ORDERED plan of tool calls. If a step needs a value "
        "from an earlier step's result, reference it using the exact "
        "syntax $step<N> (whole result) or $step<N>.<path> (e.g. "
        "$step0.id or $step0.messages.0.subject for nested dict keys / "
        "list indices), where N is the 0-indexed position of the earlier "
        "step in THIS plan. Do not invent data — only reference what a "
        "prior step will actually return.\n\n"
        "Respond with a JSON object with exactly these fields:\n"
        '{"steps": [{"tool_name": "<tool>", "tool_kwargs_json": "<JSON-encoded STRING of args, using $stepN refs where needed>"}], '
        '"reasoning": "<brief explanation of the plan>"}\n\n'
        "Keep plans as SHORT as possible — only include steps genuinely "
        "necessary to fulfill the request. Respond with ONLY the JSON "
        "object, no markdown formatting, no preamble."
    )


def _generate_plan(user_text: str) -> DynamicPlan:
    """Gemini primary, Groq fallback — same provider pattern as Tier 3."""
    prompt = _build_planning_prompt(user_text)

    try:
        from google import genai
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=f"{prompt}\n\nUser request: {user_text}",
            config={"response_mime_type": "application/json", "response_schema": DynamicPlan},
        )
        plan = DynamicPlan.model_validate_json(response.text)
        logger.info("Tier 4 (Gemini) plan generated: {} step(s). reasoning={!r}", len(plan.steps), plan.reasoning)
        return plan
    except Exception as gemini_error:
        logger.warning("Tier 4 Gemini planning failed, falling back to Groq: {}", gemini_error)
        try:
            from groq import Groq
            client = Groq(api_key=settings.groq_api_key)
            response = client.chat.completions.create(
                model=settings.groq_model,
                messages=[{"role": "system", "content": prompt}, {"role": "user", "content": user_text}],
                response_format={"type": "json_object"},
            )
            plan = DynamicPlan.model_validate_json(response.choices[0].message.content)
            logger.info("Tier 4 (Groq fallback) plan generated: {} step(s).", len(plan.steps))
            return plan
        except Exception as groq_error:
            raise LLMProviderError(
                f"Both Gemini and Groq failed to generate a plan. "
                f"Gemini error: {gemini_error}. Groq error: {groq_error}",
                context={"user_text": user_text},
            ) from groq_error


def _coerce_value_to_type(value, expected_type):
    """
    Deterministic type coercion for a single value against the
    TARGET tool's real expected type — the fix for the documented
    cross-step type mismatch bug (e.g. an int output feeding a
    function expecting to slice a string). Only coerces simple,
    unambiguous cases; leaves anything else unchanged rather than
    guessing destructively.
    """
    if value is None or expected_type is None:
        return value
    try:
        if expected_type is str and not isinstance(value, str):
            return str(value)
        if expected_type is int and isinstance(value, str) and value.lstrip("-").isdigit():
            return int(value)
        if expected_type is float and isinstance(value, (int, str)):
            return float(value)
    except (ValueError, TypeError):
        pass  # coercion not safely possible — leave as-is, let Pydantic validation catch it properly
    return value


def _coerce_step_kwargs(tool_name: str, resolved_kwargs: dict) -> dict:
    """Coerces resolved_kwargs values against the target tool's real
    Pydantic input_schema field types, where safely possible."""
    registered = get_tool(tool_name)
    if registered is None or registered.input_schema is None:
        return resolved_kwargs

    coerced = dict(resolved_kwargs)
    for field_name, field_info in registered.input_schema.model_fields.items():
        if field_name not in coerced:
            continue
        expected_type = field_info.annotation
        coerced[field_name] = _coerce_value_to_type(coerced[field_name], expected_type)
    return coerced


def run_dynamic_plan(user_text: str, *, approval_handler: ApprovalHandler | None = None) -> list[ToolResult]:
    """
    Generates a plan via LLM, then executes it step by step — resolving
    $stepN references against ACTUAL prior results (not the plan's
    guesses) and applying type coercion before each call_tool(),
    exactly mirroring run_pipeline()'s execution discipline but with
    an LLM-generated step sequence instead of a hand-declared one.
    """
    plan = _generate_plan(user_text)

    if not plan.steps:
        raise WorkflowError("LLM produced an empty plan (zero steps).", context={"user_text": user_text})

    step_results: dict[int, object] = {}
    tool_results: list[ToolResult] = []

    for i, step in enumerate(plan.steps):
        if get_tool(step.tool_name) is None:
            raise IntentResolutionError(
                f"Tier 4 plan step {i} references unregistered tool '{step.tool_name}' (possible hallucination).",
                context={"user_text": user_text, "step_index": i, "hallucinated_tool": step.tool_name},
            )

        try:
            raw_kwargs = json.loads(step.tool_kwargs_json)
        except json.JSONDecodeError as e:
            raise WorkflowError(
                f"Tier 4 plan step {i} has invalid JSON in tool_kwargs_json: {step.tool_kwargs_json!r}",
                context={"user_text": user_text, "step_index": i},
            ) from e

        resolved_kwargs = resolve_kwargs(raw_kwargs, step_results)
        coerced_kwargs = _coerce_step_kwargs(step.tool_name, resolved_kwargs)

        logger.info("Tier 4 executing step {}: tool={} kwargs={}", i, step.tool_name, coerced_kwargs)
        result = call_tool(step.tool_name, coerced_kwargs, approval_handler=approval_handler)
        step_results[i] = result.data
        tool_results.append(result)

    logger.info("Tier 4 dynamic plan completed. {} step(s) executed.", len(tool_results))
    return tool_results


__all__ = ["run_dynamic_plan", "DynamicPlan", "PlannedStep"]