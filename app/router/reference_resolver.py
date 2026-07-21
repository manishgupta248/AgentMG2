"""
$stepN reference resolver — resolves references like $step0,
$step0.2.subject, $step1.results.0.id to actual values from prior
pipeline step results.

CRITICAL LESSON FROM PRIOR BUILD: a naive single-level resolver
silently passed through unresolved reference strings (e.g. the
literal text "$step0.2.subject") into real tool calls when the path
didn't match — this got written into a real spreadsheet as if it
were data. This resolver instead RAISES loudly, naming the exact
unresolved segment, whenever a reference can't be fully resolved.
Supports both dict-key and list-index path segments.
"""

from __future__ import annotations

import re

from app.core.exceptions import WorkflowError

_STEP_REF_PATTERN = re.compile(r"^\$step(\d+)((?:\.[^.]+)*)$")


def is_step_reference(value) -> bool:
    """True if value looks like a $stepN reference string at all
    (used to decide whether to attempt resolution vs. pass through
    literal values unchanged)."""
    return isinstance(value, str) and _STEP_REF_PATTERN.match(value) is not None


def resolve_reference(value: str, step_results: dict[int, object]):
    """
    Resolves a single $stepN[.path...] reference string against
    step_results (step_index -> that step's result data). Raises
    WorkflowError naming the exact unresolved segment if resolution
    fails at any point — NEVER returns the literal unresolved string.
    """
    match = _STEP_REF_PATTERN.match(value)
    if not match:
        raise WorkflowError(f"'{value}' is not a valid $stepN reference.", context={"reference": value})

    step_index = int(match.group(1))
    path_str = match.group(2)  # e.g. ".2.subject" or "" if no path

    if step_index not in step_results:
        raise WorkflowError(
            f"Reference '{value}' points to step {step_index}, which has no recorded result "
            f"(it may not have run yet, or the pipeline has fewer than {step_index + 1} steps).",
            context={"reference": value, "step_index": step_index},
        )

    current = step_results[step_index]

    if not path_str:
        return current

    segments = path_str.split(".")[1:]  # drop leading empty segment from the split on "."
    traversed = f"$step{step_index}"

    for segment in segments:
        traversed += f".{segment}"
        if isinstance(current, dict):
            if segment not in current:
                raise WorkflowError(
                    f"Reference '{value}' failed: '{traversed}' — key '{segment}' not found in dict "
                    f"(available keys: {list(current.keys())}).",
                    context={"reference": value, "failed_at": traversed},
                )
            current = current[segment]
        elif isinstance(current, list):
            if not segment.lstrip("-").isdigit():
                raise WorkflowError(
                    f"Reference '{value}' failed: '{traversed}' — '{segment}' is not a valid list index.",
                    context={"reference": value, "failed_at": traversed},
                )
            idx = int(segment)
            if idx >= len(current) or idx < -len(current):
                raise WorkflowError(
                    f"Reference '{value}' failed: '{traversed}' — index {idx} out of range "
                    f"(list has {len(current)} items).",
                    context={"reference": value, "failed_at": traversed},
                )
            current = current[idx]
        else:
            raise WorkflowError(
                f"Reference '{value}' failed: '{traversed}' — cannot index into a "
                f"{type(current).__name__} value (expected dict or list).",
                context={"reference": value, "failed_at": traversed},
            )

    return current


def resolve_kwargs(kwargs: dict, step_results: dict[int, object]) -> dict:
    """
    Walks a tool_kwargs dict and resolves any $stepN reference STRING
    values found at any depth (including inside nested dicts/lists
    within kwargs itself). Non-reference values pass through unchanged.
    """
    def _resolve_value(v):
        if is_step_reference(v):
            return resolve_reference(v, step_results)
        if isinstance(v, dict):
            return {k: _resolve_value(sub_v) for k, sub_v in v.items()}
        if isinstance(v, list):
            return [_resolve_value(item) for item in v]
        return v

    return {k: _resolve_value(v) for k, v in kwargs.items()}


__all__ = ["is_step_reference", "resolve_reference", "resolve_kwargs"]