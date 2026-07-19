"""
Regression tests for call_tool() — locks in two historical bugs:
1. tool_kwargs collision when a tool has its own 'tool_name'-like param.
2. call_tool() must never return None on success.
"""

from app.core.registry import tool as tool_decorator, get_tool
from app.core.types import PermissionLevel, ToolResult
from app.core.executor import call_tool
from app.core.approval import AutoApprovalHandler
from pydantic import BaseModel


class _TestPingInput(BaseModel):
    model_config = {"extra": "forbid"}


class _TestJobEnqueueInput(BaseModel):
    tool_name: str
    payload: str = ""


def test_call_tool_never_returns_none_on_success(isolated_db, monkeypatch):
    """Regression: a prior refactor silently dropped the success-path return."""
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    @tool_decorator("_test_ping", permission=PermissionLevel.READ, description="test", input_schema=_TestPingInput)
    def _test_ping():
        return {"ok": True}

    result = call_tool("_test_ping", {}, approval_handler=AutoApprovalHandler())
    assert result is not None
    assert isinstance(result, ToolResult)
    assert result.success is True
    assert result.data == {"ok": True}


def test_tool_kwargs_no_collision_with_tool_name_param(isolated_db, monkeypatch):
    """
    Regression: a tool with its own 'tool_name' field in its params
    (e.g. job_enqueue(tool_name=...)) used to collide with the
    framework's own tool_name/**kwargs parameter. tool_kwargs is now
    an explicit dict, so this must never collide.
    """
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    @tool_decorator("_test_job_enqueue", permission=PermissionLevel.READ, description="test", input_schema=_TestJobEnqueueInput)
    def _test_job_enqueue(tool_name: str, payload: str = ""):
        return {"enqueued_tool": tool_name, "payload": payload}

    result = call_tool(
        "_test_job_enqueue",
        {"tool_name": "some_downstream_tool", "payload": "data"},
        approval_handler=AutoApprovalHandler(),
    )
    assert result.success is True
    assert result.data == {"enqueued_tool": "some_downstream_tool", "payload": "data"}


def test_call_tool_raises_for_unregistered_tool(isolated_db, monkeypatch):
    from app.core import database
    from app.core.exceptions import ToolNotFoundError
    import pytest as _pytest

    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    with _pytest.raises(ToolNotFoundError):
        call_tool("_definitely_not_a_real_tool", {})