"""
Regression tests for input_schema enforcement in call_tool().

Locks in the prior-build bug: a tool defined a Pydantic input model
but forgot to attach it via input_schema=, so invalid input reached
a live external API instead of being rejected. Every tool with a
defined input model needs a test asserting invalid input IS rejected,
and every registered tool must actually declare a schema at all.
"""

import pytest
from pydantic import BaseModel

from app.core.registry import tool as tool_decorator, list_tools, autodiscover_tools
from app.core.types import PermissionLevel
from app.core.executor import call_tool
from app.core.exceptions import ToolValidationError
from app.core.approval import AutoApprovalHandler


def test_echo_rejects_missing_required_field(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    with pytest.raises(ToolValidationError):
        call_tool("echo", {}, approval_handler=AutoApprovalHandler())  # missing required 'text'


def test_echo_rejects_empty_string(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    with pytest.raises(ToolValidationError):
        call_tool("echo", {"text": ""}, approval_handler=AutoApprovalHandler())  # min_length=1


def test_echo_accepts_valid_input(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    result = call_tool("echo", {"text": "hi"}, approval_handler=AutoApprovalHandler())
    assert result.success is True


def test_ping_rejects_unexpected_extra_field(isolated_db, monkeypatch):
    """PingInput uses extra='forbid' — passing junk args must be rejected,
    not silently ignored (which would mask caller bugs upstream)."""
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    with pytest.raises(ToolValidationError):
        call_tool("ping", {"unexpected_field": "junk"}, approval_handler=AutoApprovalHandler())


def test_every_registered_tool_declares_an_input_schema(isolated_db, monkeypatch):
    """
    Locks in the exact prior-build gap at the registry level: a tool
    with NO input_schema at all means call_tool() skips validation
    entirely and unvalidated input reaches the tool function directly.
    Every PRODUCTION tool must declare one, even if it's an empty model.
    Tools prefixed '_test_' are ad-hoc fixtures from other test modules
    and are exempt from this check by convention.
    """
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    tools = list_tools()
    missing_schema = [
        name for name, t in tools.items()
        if t.input_schema is None and not name.startswith("_test_")
    ]
    assert not missing_schema, f"Tools missing input_schema (unvalidated input risk): {missing_schema}"