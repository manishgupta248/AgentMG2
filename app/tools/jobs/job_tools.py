"""
Job Queue tools.

NOTE: job_enqueue's input schema has its own 'tool_name' field — this
is EXACTLY the parameter collision scenario documented in M1 (a tool
with its own tool_name param colliding with call_tool()'s framework-
level tool_name param). This works correctly here because call_tool()
takes tool_kwargs as an explicit dict, not **kwargs — see the M1
regression test (test_tool_kwargs_no_collision_with_tool_name_param)
for the synthetic reproduction; this is the real-world instance of it.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.registry import tool
from app.core.types import PermissionLevel
from app.jobs.queue import enqueue_job, get_job, list_jobs


class JobEnqueueInput(BaseModel):
    tool_name: str = Field(..., description="The tool to run as a background job")
    tool_kwargs: dict = Field(default_factory=dict, description="Arguments to pass to the tool")
    model_config = {"extra": "forbid"}


@tool(
    "job_enqueue",
    permission=PermissionLevel.MODIFY,
    description="Enqueues a tool call to run asynchronously as a background job.",
    input_schema=JobEnqueueInput,
    example_phrases=["run this in the background", "queue this task"],
)
def job_enqueue_tool(tool_name: str, tool_kwargs: dict | None = None) -> dict:
    job_id = enqueue_job("tool_call", {"tool_name": tool_name, "tool_kwargs": tool_kwargs or {}})
    return {"job_id": job_id}


class JobGetStatusInput(BaseModel):
    job_id: int
    model_config = {"extra": "forbid"}


@tool(
    "job_get_status",
    permission=PermissionLevel.READ,
    description="Gets the current status and result of a background job.",
    input_schema=JobGetStatusInput,
    example_phrases=["check job status", "is the background task done"],
)
def job_get_status_tool(job_id: int) -> dict | None:
    return get_job(job_id)


class JobListInput(BaseModel):
    status: str | None = Field(None, description="Filter by: queued | running | succeeded | failed")
    limit: int = Field(20, ge=1, le=100)
    model_config = {"extra": "forbid"}


@tool(
    "job_list",
    permission=PermissionLevel.READ,
    description="Lists background jobs, optionally filtered by status.",
    input_schema=JobListInput,
    example_phrases=["list background jobs", "show queued tasks"],
)
def job_list_tool(status: str | None = None, limit: int = 20) -> list:
    return list_jobs(status=status, limit=limit)