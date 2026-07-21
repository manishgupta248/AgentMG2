"""
Workflow Templates — named, parameterized, user-invocable multi-step
automations. Sits between Tier 1.5 fixed pipelines (code-declared,
no user-facing parameterization) and Tier 4 LangGraph plans (fully
dynamic step sequences).

A WorkflowTemplate defines steps using {{param}} placeholders in
tool_kwargs values (resolved from user-supplied params BEFORE the
pipeline runs) alongside $stepN references (resolved DURING pipeline
execution, from prior step results) — the two substitution mechanisms
operate at different times and are kept distinct rather than merged,
since {{param}} values are known upfront and $stepN values are not.

CRITICAL: run_workflow() calls run_pipeline() — it does NOT
independently wrap approval. run_pipeline() (M12 Step 3b) is the
single site where batch-approval wrapping happens; double-wrapping
here was a documented prior-build bug.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.approval import ApprovalHandler
from app.core.exceptions import WorkflowError
from app.core.logging_setup import logger
from app.router.pipeline import Pipeline, PipelineStep, register_pipeline, run_pipeline

_TEMPLATES: dict[str, "WorkflowTemplate"] = {}
_PARAM_PATTERN = re.compile(r"\{\{(\w+)\}\}")


@dataclass
class WorkflowTemplate:
    name: str
    description: str
    step_definitions: list[dict]  # each: {"tool_name": str, "tool_kwargs": dict}  (values may contain {{param}} or $stepN)
    required_params: list[str] = field(default_factory=list)


def register_template(template: WorkflowTemplate) -> None:
    _TEMPLATES[template.name] = template
    logger.debug("Registered workflow template '{}' ({} step(s), params={})",
                 template.name, len(template.step_definitions), template.required_params)


def get_template(name: str) -> WorkflowTemplate | None:
    return _TEMPLATES.get(name)


def list_templates() -> dict[str, WorkflowTemplate]:
    return dict(_TEMPLATES)


def _substitute_params(value, params: dict):
    """Recursively substitutes {{param}} placeholders with values from
    params. Raises WorkflowError naming the exact missing param if a
    placeholder has no corresponding value — same loud-failure
    discipline as the $stepN resolver, applied here too."""
    if isinstance(value, str):
        def _replace(match):
            param_name = match.group(1)
            if param_name not in params:
                raise WorkflowError(
                    f"Workflow template references undefined parameter '{{{{{param_name}}}}}' "
                    f"(available params: {list(params.keys())}).",
                    context={"param_name": param_name},
                )
            return str(params[param_name])

        # If the ENTIRE string is a single {{param}}, preserve the
        # param's original type (e.g. int, dict) rather than stringifying.
        full_match = _PARAM_PATTERN.fullmatch(value)
        if full_match:
            param_name = full_match.group(1)
            if param_name not in params:
                raise WorkflowError(
                    f"Workflow template references undefined parameter '{{{{{param_name}}}}}' "
                    f"(available params: {list(params.keys())}).",
                    context={"param_name": param_name},
                )
            return params[param_name]

        return _PARAM_PATTERN.sub(_replace, value)

    if isinstance(value, dict):
        return {k: _substitute_params(v, params) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_params(item, params) for item in value]
    return value


def run_workflow(template_name: str, params: dict, *, approval_handler: ApprovalHandler | None = None):
    """
    Instantiates a WorkflowTemplate with concrete params, builds a
    one-off Pipeline from it, and executes via run_pipeline() —
    the single approval-wrapping site. Does NOT wrap approval itself.
    """
    template = get_template(template_name)
    if template is None:
        raise WorkflowError(f"Workflow template '{template_name}' is not registered.", context={"template_name": template_name})

    missing = [p for p in template.required_params if p not in params]
    if missing:
        raise WorkflowError(
            f"Missing required parameter(s) for workflow '{template_name}': {missing}",
            context={"template_name": template_name, "missing_params": missing},
        )

    steps = []
    for step_def in template.step_definitions:
        substituted_kwargs = _substitute_params(step_def["tool_kwargs"], params)
        steps.append(PipelineStep(tool_name=step_def["tool_name"], tool_kwargs=substituted_kwargs))

    # Register a uniquely-named ephemeral pipeline for this run, then
    # delegate to run_pipeline() — the single wrapping site.
    ephemeral_pipeline_name = f"__workflow__{template_name}"
    register_pipeline(Pipeline(name=ephemeral_pipeline_name, steps=steps, description=template.description))

    logger.info("Running workflow '{}' with params={}", template_name, params)
    return run_pipeline(ephemeral_pipeline_name, approval_handler=approval_handler)


__all__ = ["WorkflowTemplate", "register_template", "get_template", "list_templates", "run_workflow"]