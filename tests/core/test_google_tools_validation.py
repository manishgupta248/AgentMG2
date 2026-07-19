"""
Regression tests for Google tool input validation and permission
gating. These do NOT hit live APIs — they test that call_tool()'s
validation and approval-gate logic correctly rejects bad input and
requires approval for MODIFY/DELETE tools, using autodiscover_tools()
to confirm the tools are registered with the right schemas/permissions.

Live API correctness (search returns real results, writes actually
land, etc.) was verified manually in M9 Steps 3, 5, 6, 7 against real
Gmail/Drive/Calendar/Sheets accounts, per the project's real-verification
rule for live external services.
"""

import pytest

from app.core.registry import autodiscover_tools, list_tools
from app.core.executor import call_tool
from app.core.types import PermissionLevel
from app.core.exceptions import ToolValidationError


GOOGLE_TOOLS_AND_EXPECTED_PERMISSIONS = {
    "gmail_search": PermissionLevel.READ,
    "gmail_read_message": PermissionLevel.READ,
    "gmail_send": PermissionLevel.MODIFY,
    "drive_search": PermissionLevel.READ,
    "drive_upload_file": PermissionLevel.MODIFY,
    "drive_download_file": PermissionLevel.READ,
    "drive_create_folder": PermissionLevel.MODIFY,
    "calendar_list_events": PermissionLevel.READ,
    "calendar_create_event": PermissionLevel.MODIFY,
    "calendar_delete_event": PermissionLevel.DELETE,
    "sheets_get_info": PermissionLevel.READ,
    "sheets_read_range": PermissionLevel.READ,
    "sheets_write_range": PermissionLevel.MODIFY,
    "sheets_delete_sheet": PermissionLevel.DELETE,
}


def test_all_google_tools_registered_with_correct_permissions():
    autodiscover_tools()
    tools = list_tools()
    for tool_name, expected_permission in GOOGLE_TOOLS_AND_EXPECTED_PERMISSIONS.items():
        assert tool_name in tools, f"Expected Google tool '{tool_name}' was not registered"
        actual = tools[tool_name].permission
        assert actual == expected_permission, f"'{tool_name}' has permission {actual}, expected {expected_permission}"


def test_all_google_tools_have_input_schemas():
    """Same framework-wide guarantee from M2 — every tool must declare
    a schema, including these newer Google tools."""
    autodiscover_tools()
    tools = list_tools()
    for tool_name in GOOGLE_TOOLS_AND_EXPECTED_PERMISSIONS:
        assert tools[tool_name].input_schema is not None, f"'{tool_name}' is missing an input_schema"


def test_gmail_send_rejects_missing_required_fields():
    autodiscover_tools()
    with pytest.raises(ToolValidationError):
        call_tool("gmail_send", {"to": "a@b.com"})  # missing subject, body


def test_gmail_send_requires_explicit_approval():
    autodiscover_tools()
    with pytest.raises(RuntimeError, match="require an explicit approval_handler"):
        call_tool("gmail_send", {"to": "a@b.com", "subject": "s", "body": "b"})


def test_calendar_create_event_rejects_missing_required_fields():
    autodiscover_tools()
    with pytest.raises(ToolValidationError):
        call_tool("calendar_create_event", {"summary": "test"})  # missing start/end datetime


def test_sheets_delete_sheet_rejects_non_integer_sheet_id():
    """Locks in the documented lesson: sheet_id must be numeric, not
    a title string — Pydantic should reject a string that isn't a
    valid int."""
    autodiscover_tools()
    with pytest.raises(ToolValidationError):
        call_tool(
            "sheets_delete_sheet",
            {"spreadsheet_id": "abc", "sheet_id": "Sheet1"},  # should be int, not the title string
            approval_handler=None,
        )


def test_drive_upload_file_rejects_missing_local_path():
    autodiscover_tools()
    with pytest.raises(ToolValidationError):
        call_tool("drive_upload_file", {"drive_filename": "test.txt"})  # missing local_file_path