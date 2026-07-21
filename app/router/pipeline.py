"""
Tier 1.5 — Fixed, hand-declared multi-step pipelines. Sits between
Tier 1 (single-tool regex) and Tier 4 (fully dynamic LangGraph
planning): the STEP SEQUENCE is fixed/hand-declared here, but
PARAMETERS can reference prior step results via $stepN.

CRITICAL: run_pipeline() is the SINGLE wrapping site for batch
approval (one approval per run, not one per step). A future
Workflow Template layer's run_workflow() must call THIS function
rather than re-implementing its own approval wrapping — double-wrapping
was a real prior-build bug.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.executor import call_tool
from app.core.types import ToolResult
from app.core.approval import ApprovalHandler, DefaultSafeApprovalHandler
from app.core.exceptions import WorkflowError
from app.core.logging_setup import logger
from app.router.reference_resolver import resolve_kwargs

_PIPELINES: dict[str, "Pipeline"] = {}


@dataclass
class PipelineStep:
    tool_name: str
    tool_kwargs: dict = field(default_factory=dict)  # may contain $stepN references


@dataclass
class Pipeline:
    name: str
    steps: list[PipelineStep]
    description: str = ""


def register_pipeline(pipeline: Pipeline) -> None:
    _PIPELINES[pipeline.name] = pipeline
    logger.debug("Registered pipeline '{}' with {} step(s)", pipeline.name, len(pipeline.steps))


def get_pipeline(name: str) -> Pipeline | None:
    return _PIPELINES.get(name)


def list_pipelines() -> dict[str, Pipeline]:
    return dict(_PIPELINES)


def run_pipeline(pipeline_name: str, *, approval_handler: ApprovalHandler | None = None) -> list[ToolResult]:
    """
    Executes a registered pipeline's steps in order. Each step's
    tool_kwargs are resolved against prior step results before
    execution. This is the SINGLE site where batch approval wrapping
    happens (currently: approval_handler is passed straight through
    to each call_tool(), meaning each MODIFY+ step still individually
    prompts — true one-approval-per-run batching is deferred to when
    BatchApprovalHandler is implemented, but this is the only place
    that will ever need to change to support it).
    """
    pipeline = get_pipeline(pipeline_name)
    if pipeline is None:
        raise WorkflowError(f"Pipeline '{pipeline_name}' is not registered.", context={"pipeline_name": pipeline_name})

    approval_handler = approval_handler or DefaultSafeApprovalHandler()
    step_results: dict[int, object] = {}
    tool_results: list[ToolResult] = []

    for i, step in enumerate(pipeline.steps):
        try:
            resolved_kwargs = resolve_kwargs(step.tool_kwargs, step_results)
        except WorkflowError:
            logger.exception("Pipeline '{}' step {} reference resolution failed.", pipeline_name, i)
            raise

        logger.info("Pipeline '{}' step {}: tool={} kwargs={}", pipeline_name, i, step.tool_name, resolved_kwargs)

        result = call_tool(step.tool_name, resolved_kwargs, approval_handler=approval_handler)
        step_results[i] = result.data
        tool_results.append(result)

    logger.info("Pipeline '{}' completed. {} step(s) executed.", pipeline_name, len(tool_results))
    return tool_results


__all__ = ["Pipeline", "PipelineStep", "register_pipeline", "get_pipeline", "list_pipelines", "run_pipeline"]