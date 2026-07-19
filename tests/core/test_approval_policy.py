"""
Regression tests for permission-based approval policy.

Locks in: READ tools auto-approve with no explicit handler; MODIFY/
DELETE/ADMIN tools MUST have an explicit approval_handler or call_tool
refuses rather than silently auto-approving a destructive action.
"""

import pytest

from app.core.registry import autodiscover_tools
from app.core.executor import call_tool
from app.core.approval import AutoApprovalHandler, DefaultSafeApprovalHandler


def test_read_tool_auto_approves_with_no_explicit_handler(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    # No approval_handler passed at all -> defaults to DefaultSafeApprovalHandler
    result = call_tool("ping", {})
    assert result.success is True


def test_delete_tool_refuses_without_explicit_handler(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    # No approval_handler passed -> must NOT silently succeed for DELETE
    with pytest.raises(RuntimeError, match="require an explicit approval_handler"):
        call_tool("delete_demo", {"target": "some_file.txt"})


def test_delete_tool_succeeds_with_explicit_auto_approve(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    # Caller explicitly opts in to auto-approval -> allowed
    result = call_tool("delete_demo", {"target": "some_file.txt"}, approval_handler=AutoApprovalHandler())
    assert result.success is True
    assert result.data == {"deleted": "some_file.txt"}


def test_delete_tool_respects_denial(isolated_db, monkeypatch):
    from app.core import database
    from app.core.exceptions import ApprovalDeniedError

    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    class _AlwaysDeny:
        def request_approval(self, tool_name, permission, tool_kwargs):
            return False

    with pytest.raises(ApprovalDeniedError):
        call_tool("delete_demo", {"target": "some_file.txt"}, approval_handler=_AlwaysDeny())