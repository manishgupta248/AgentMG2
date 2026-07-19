"""
Regression tests for the Knowledge Base — both the core CRUD layer
and the @tool-wrapped versions (permission gating included).
"""

import pytest

from app.core.knowledge_base import kb_add, kb_get, kb_update, kb_delete, kb_search, kb_list_by_kind
from app.core.registry import autodiscover_tools
from app.core.executor import call_tool
from app.core.approval import AutoApprovalHandler
from app.core.exceptions import ToolValidationError


def test_kb_add_and_get_roundtrip(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    new_id = kb_add("note", "test content", title="test title")
    entry = kb_get(new_id)

    assert entry is not None
    assert entry["kind"] == "note"
    assert entry["content"] == "test content"
    assert entry["title"] == "test title"


def test_kb_get_nonexistent_returns_none(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    assert kb_get(99999) is None


def test_kb_update_changes_only_provided_fields(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    new_id = kb_add("note", "original content", title="original title")
    kb_update(new_id, content="new content")  # title NOT provided
    entry = kb_get(new_id)

    assert entry["content"] == "new content"
    assert entry["title"] == "original title"  # unchanged


def test_kb_delete_removes_entry(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    new_id = kb_add("note", "to be deleted")
    assert kb_delete(new_id) is True
    assert kb_get(new_id) is None
    assert kb_delete(new_id) is False  # already gone


def test_kb_search_matches_content_and_title(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    kb_add("note", "unrelated content", title="renew SSL certificate")
    kb_add("note", "renew the domain soon", title="unrelated title")
    kb_add("note", "totally different", title="also different")

    results = kb_search("renew")
    assert len(results) == 2


def test_kb_list_by_kind_filters_correctly(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    kb_add("note", "a note")
    kb_add("contact", "a contact")
    kb_add("contact", "another contact")

    contacts = kb_list_by_kind("contact")
    assert len(contacts) == 2
    assert all(c["kind"] == "contact" for c in contacts)


# --- Tool-level tests (via call_tool, permission-gated) ---

def test_kb_add_tool_requires_explicit_approval_handler(isolated_db, monkeypatch):
    """kb_add is MODIFY permission — must not silently auto-approve."""
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    with pytest.raises(RuntimeError, match="require an explicit approval_handler"):
        call_tool("kb_add", {"kind": "note", "content": "test"})


def test_kb_add_tool_succeeds_with_explicit_approval(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    result = call_tool("kb_add", {"kind": "note", "content": "test"}, approval_handler=AutoApprovalHandler())
    assert result.success is True
    assert "id" in result.data


def test_kb_get_tool_is_read_and_auto_approves(isolated_db, monkeypatch):
    """kb_get is READ permission — no explicit handler needed."""
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    add_result = call_tool("kb_add", {"kind": "note", "content": "test"}, approval_handler=AutoApprovalHandler())
    entry_id = add_result.data["id"]

    get_result = call_tool("kb_get", {"entry_id": entry_id})  # no approval_handler passed
    assert get_result.success is True
    assert get_result.data["content"] == "test"


def test_kb_add_tool_rejects_invalid_kind_type(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    with pytest.raises(ToolValidationError):
        call_tool("kb_add", {"kind": "note"}, approval_handler=AutoApprovalHandler())  # missing required 'content'