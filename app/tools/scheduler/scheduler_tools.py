"""Scheduler tools — create/list/enable/disable/delete scheduled jobs."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.registry import tool
from app.core.types import PermissionLevel
from app.scheduler.scheduler import (
    create_scheduled_job,
    get_scheduled_job,
    list_scheduled_jobs,
    set_scheduled_job_enabled,
    delete_scheduled_job,
)


class ScheduleCreateInput(BaseModel):
    name: str
    tool_name: str = Field(..., description="Tool to run on this schedule")
    tool_kwargs: dict = Field(default_factory=dict)
    schedule_expr: str = Field(..., description="e.g. 'every:3600' for hourly")
    enabled: bool = True
    model_config = {"extra": "forbid"}


@tool(
    "schedule_create",
    permission=PermissionLevel.MODIFY,
    description="Creates a new recurring scheduled job.",
    input_schema=ScheduleCreateInput,
    example_phrases=["schedule this to run daily", "set up a recurring task"],
)
def schedule_create_tool(name: str, tool_name: str, schedule_expr: str, tool_kwargs: dict | None = None, enabled: bool = True) -> dict:
    scheduled_id = create_scheduled_job(
        name=name,
        job_type="tool_call",
        payload={"tool_name": tool_name, "tool_kwargs": tool_kwargs or {}},
        schedule_expr=schedule_expr,
        enabled=enabled,
    )
    return {"scheduled_id": scheduled_id}


class ScheduleListInput(BaseModel):
    enabled_only: bool = False
    model_config = {"extra": "forbid"}


@tool(
    "schedule_list",
    permission=PermissionLevel.READ,
    description="Lists all scheduled jobs.",
    input_schema=ScheduleListInput,
    example_phrases=["show my scheduled tasks", "list recurring jobs"],
)
def schedule_list_tool(enabled_only: bool = False) -> list:
    return list_scheduled_jobs(enabled_only=enabled_only)


class ScheduleSetEnabledInput(BaseModel):
    scheduled_id: int
    enabled: bool
    model_config = {"extra": "forbid"}


@tool(
    "schedule_set_enabled",
    permission=PermissionLevel.MODIFY,
    description="Enables or disables a scheduled job without deleting it.",
    input_schema=ScheduleSetEnabledInput,
    example_phrases=["pause this scheduled task", "turn off the recurring job"],
)
def schedule_set_enabled_tool(scheduled_id: int, enabled: bool) -> dict:
    updated = set_scheduled_job_enabled(scheduled_id, enabled)
    return {"updated": updated, "scheduled_id": scheduled_id, "enabled": enabled}


class ScheduleDeleteInput(BaseModel):
    scheduled_id: int
    model_config = {"extra": "forbid"}


@tool(
    "schedule_delete",
    permission=PermissionLevel.DELETE,
    description="Permanently deletes a scheduled job.",
    input_schema=ScheduleDeleteInput,
    example_phrases=["delete this scheduled task", "remove the recurring job"],
)
def schedule_delete_tool(scheduled_id: int) -> dict:
    deleted = delete_scheduled_job(scheduled_id)
    return {"deleted": deleted}