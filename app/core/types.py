"""
Core shared types used across the tool framework:
- PermissionLevel: replaces the old binary requires_approval flag.
- ToolResult: the standard return shape every tool call produces,
  whether it succeeded or failed.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel


class PermissionLevel(str, Enum):
    """
    Ordered permission tiers a tool declares as its requirement.
    Approval policy can differ per level (e.g. READ auto-approves,
    DELETE always requires human YES/NO), and per user in future
    multi-user scenarios.
    """

    READ = "READ"
    MODIFY = "MODIFY"
    DELETE = "DELETE"
    ADMIN = "ADMIN"

    @property
    def rank(self) -> int:
        """Numeric ordering so policies can do rank comparisons (>=, etc.)."""
        return {"READ": 0, "MODIFY": 1, "DELETE": 2, "ADMIN": 3}[self.value]


class ToolResult(BaseModel):
    """
    Standard return type for every tool invocation via call_tool().
    Success and failure both produce this same shape, so callers
    (Intent Router tiers, Job Queue, Workflow Templates, LangGraph
    plans) never need to branch on exception vs. return value.
    """

    success: bool
    tool_name: str
    data: Any = None
    error: str | None = None

    model_config = {"arbitrary_types_allowed": True}


__all__ = ["PermissionLevel", "ToolResult"]