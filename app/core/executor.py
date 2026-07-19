"""
call_tool() — the single execution path every tier (Tier 1 through 4,
Job Queue, Workflow Templates) must go through. Responsibilities:

1. Look up the tool in the registry (ToolNotFoundError if missing).
2. Validate input against the tool's Pydantic input_schema, if any.
3. Apply the approval policy based on the tool's PermissionLevel.
4. Execute the tool.
5. ALWAYS write a row to execution_history — success or failure —
   automatically. Individual tools never need to remember to log.
6. Return a ToolResult. NEVER silently return None on success — a
   prior build regression left this function returning None during
   a refactor; a test guards against that regression (see tests/).

CRITICAL: tool_kwargs is an explicit dict parameter, NOT **kwargs.
A prior build broke because a tool (job_enqueue) had its own
'tool_name' field in its schema, colliding with the framework's
**kwargs-style tool_name parameter. Keeping tool_kwargs as one
explicit dict avoids this entire class of collision permanently.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from app.core.registry import get_tool
from app.core.types import ToolResult, PermissionLevel
from app.core.approval import ApprovalHandler, AutoApprovalHandler
from app.core.exceptions import (
    ToolNotFoundError,
    ToolValidationError,
    ToolExecutionError,
    ApprovalDeniedError,
)
from app.core.database import db_cursor
from app.core.logging_setup import logger
from app.core.approval import ApprovalHandler, DefaultSafeApprovalHandler

# Permission levels that require explicit human approval by default.
# READ auto-approves; MODIFY/DELETE/ADMIN require it.
_REQUIRES_APPROVAL = {PermissionLevel.MODIFY, PermissionLevel.DELETE, PermissionLevel.ADMIN}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_execution(tool_name: str, tool_kwargs: dict, status: str, result, error, started_at: str, finished_at: str) -> None:
    """Writes one row to execution_history. Failure to log is itself logged, never raised further (audit logging must never crash the caller's real result)."""
    try:
        with db_cursor() as cur:
            cur.execute(
                """
                INSERT INTO execution_history
                    (tool_name, tool_kwargs, status, result, error, started_at, finished_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tool_name,
                    json.dumps(tool_kwargs, default=str),
                    status,
                    json.dumps(result, default=str) if result is not None else None,
                    error,
                    started_at,
                    finished_at,
                ),
            )
    except Exception:
        logger.exception("Failed to write execution_history row for tool '{}' (non-fatal).", tool_name)


def call_tool(
    tool_name: str,
    tool_kwargs: dict | None = None,
    *,
    approval_handler: ApprovalHandler | None = None,
) -> ToolResult:
    """
    The single execution path for every tool call in the system.
    tool_kwargs is an explicit dict — never **kwargs (see collision
    lesson in module docstring).
    """
    tool_kwargs = tool_kwargs or {}
    approval_handler = approval_handler or DefaultSafeApprovalHandler()
    started_at = _now_iso()

    registered = get_tool(tool_name)
    if registered is None:
        err = f"Tool '{tool_name}' is not registered"
        _log_execution(tool_name, tool_kwargs, "failure", None, err, started_at, _now_iso())
        raise ToolNotFoundError(err, context={"tool_name": tool_name})

    # Step 2: input validation (schema wiring completed in M2; tolerate
    # tools with no schema yet, since we're mid-milestone)
    validated_kwargs = tool_kwargs
    if registered.input_schema is not None:
        try:
            validated = registered.input_schema(**tool_kwargs)
            validated_kwargs = validated.model_dump()
        except Exception as e:
            err = f"Input validation failed for tool '{tool_name}': {e}"
            _log_execution(tool_name, tool_kwargs, "failure", None, err, started_at, _now_iso())
            raise ToolValidationError(err, context={"tool_name": tool_name}) from e

    # Step 3: approval gate
    if registered.permission in _REQUIRES_APPROVAL:
        approved = approval_handler.request_approval(tool_name, registered.permission, validated_kwargs)
        if not approved:
            err = f"Approval denied for tool '{tool_name}'"
            _log_execution(tool_name, validated_kwargs, "failure", None, err, started_at, _now_iso())
            raise ApprovalDeniedError(err, context={"tool_name": tool_name})

    # Step 4: execute
    try:
        raw_result = registered.func(**validated_kwargs)
    except Exception as e:
        finished_at = _now_iso()
        err = f"Execution failed for tool '{tool_name}': {e}"
        logger.exception("Tool '{}' raised during execution.", tool_name)
        _log_execution(tool_name, validated_kwargs, "failure", None, str(e), started_at, finished_at)
        raise ToolExecutionError(err, context={"tool_name": tool_name}) from e

    # Step 5: log success
    finished_at = _now_iso()
    _log_execution(tool_name, validated_kwargs, "success", raw_result, None, started_at, finished_at)

    # Step 6: never return None on success
    result = ToolResult(success=True, tool_name=tool_name, data=raw_result, error=None)
    assert result is not None  # regression guard, see module docstring
    return result


__all__ = ["call_tool"]