"""
Regression tests for Excel tools. Uses a real temp .xlsx file per test
(via isolated tmp_path from pytest) rather than mocking openpyxl, since
correctness here depends on actual file I/O behavior.
"""

import openpyxl
import pytest

from app.core.registry import autodiscover_tools
from app.core.executor import call_tool
from app.core.approval import AutoApprovalHandler
from app.core.exceptions import ToolExecutionError, ToolValidationError


@pytest.fixture()
def sample_workbook(tmp_path):
    file_path = tmp_path / "sample.xlsx"
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Sheet1"
    ws1.append(["Name", "Age"])
    ws1.append(["Manish", 30])
    ws2 = wb.create_sheet("Sheet2")
    ws2.append(["X", "Y"])
    wb.save(str(file_path))
    wb.close()
    return str(file_path)


def test_excel_list_sheets(sample_workbook):
    autodiscover_tools()
    result = call_tool("excel_list_sheets", {"file_path": sample_workbook})
    assert result.data["sheets"] == ["Sheet1", "Sheet2"]


def test_excel_read_sheet_returns_correct_rows(sample_workbook):
    autodiscover_tools()
    result = call_tool("excel_read_sheet", {"file_path": sample_workbook, "sheet_name": "Sheet1"})
    assert result.data["rows"] == [["Name", "Age"], ["Manish", 30]]
    assert result.data["row_count"] == 2
    assert result.data["truncated"] is False


def test_excel_read_sheet_respects_max_rows_truncation(sample_workbook):
    autodiscover_tools()
    result = call_tool("excel_read_sheet", {"file_path": sample_workbook, "sheet_name": "Sheet1", "max_rows": 1})
    assert result.data["row_count"] == 1
    assert result.data["truncated"] is True


def test_excel_read_range_returns_correct_subset(sample_workbook):
    autodiscover_tools()
    result = call_tool("excel_read_range", {"file_path": sample_workbook, "sheet_name": "Sheet1", "cell_range": "A1:A2"})
    assert result.data["rows"] == [["Name"], ["Manish"]]


def test_excel_read_nonexistent_file_raises(tmp_path):
    autodiscover_tools()
    fake_path = str(tmp_path / "does_not_exist.xlsx")
    with pytest.raises(ToolExecutionError):
        call_tool("excel_list_sheets", {"file_path": fake_path})


def test_excel_read_nonexistent_sheet_raises(sample_workbook):
    autodiscover_tools()
    with pytest.raises(ToolExecutionError):
        call_tool("excel_read_sheet", {"file_path": sample_workbook, "sheet_name": "NoSuchSheet"})


def test_excel_write_range_requires_explicit_approval(sample_workbook):
    autodiscover_tools()
    with pytest.raises(RuntimeError, match="require an explicit approval_handler"):
        call_tool("excel_write_range", {"file_path": sample_workbook, "start_cell": "A1", "rows": [[1]]})


def test_excel_write_range_writes_correctly(sample_workbook):
    autodiscover_tools()
    call_tool(
        "excel_write_range",
        {"file_path": sample_workbook, "sheet_name": "Sheet1", "start_cell": "C1", "rows": [["new_col"], ["val"]]},
        approval_handler=AutoApprovalHandler(),
    )
    result = call_tool("excel_read_sheet", {"file_path": sample_workbook, "sheet_name": "Sheet1"})
    assert result.data["rows"][0][2] == "new_col"
    assert result.data["rows"][1][2] == "val"


def test_excel_append_rows_adds_to_end(sample_workbook):
    autodiscover_tools()
    call_tool(
        "excel_append_rows",
        {"file_path": sample_workbook, "sheet_name": "Sheet1", "rows": [["NewPerson", 40]]},
        approval_handler=AutoApprovalHandler(),
    )
    result = call_tool("excel_read_sheet", {"file_path": sample_workbook, "sheet_name": "Sheet1"})
    assert result.data["rows"][-1] == ["NewPerson", 40]
    assert result.data["row_count"] == 3


def test_excel_write_range_rejects_missing_rows_field(sample_workbook):
    autodiscover_tools()
    with pytest.raises(ToolValidationError):
        call_tool(
            "excel_write_range",
            {"file_path": sample_workbook, "start_cell": "A1"},  # missing 'rows'
            approval_handler=AutoApprovalHandler(),
        )