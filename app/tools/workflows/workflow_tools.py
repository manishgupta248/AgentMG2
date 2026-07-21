"""Workflow Template tools — run and list registered templates."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.registry import tool
from app.core.types import PermissionLevel
from app.workflows.templates import run_workflow, list_templates


class WorkflowRunInput(BaseModel):
    template_name: str
    params: dict = Field(default_factory=dict)
    model_config = {"extra": "forbid"}


@tool(
    "workflow_run",
    permission=PermissionLevel.MODIFY,
    description="Runs a named, parameterized workflow template.",
    input_schema=WorkflowRunInput,
    example_phrases=["run the workflow", "execute this automation"],
)
def workflow_run_tool(template_name: str, params: dict | None = None) -> dict:
    results = run_workflow(template_name, params or {})
    return {
        "template_name": template_name,
        "step_count": len(results),
        "results": [r.data for r in results],
    }


class WorkflowListInput(BaseModel):
    model_config = {"extra": "forbid"}


@tool(
    "workflow_list",
    permission=PermissionLevel.READ,
    description="Lists all registered workflow templates.",
    input_schema=WorkflowListInput,
    example_phrases=["list workflows", "show available automations"],
)
def workflow_list_tool() -> list:
    templates = list_templates()
    return [
        {"name": t.name, "description": t.description, "required_params": t.required_params}
        for t in templates.values()
    ]