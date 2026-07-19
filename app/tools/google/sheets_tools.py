"""
Google Sheets tools. Two documented lessons baked in:
1. Delete operations require the numeric sheetId (a tab's internal
   ID), NOT the sheet title string — obtainable via spreadsheets.get().
2. Write operations use valueInputOption="USER_ENTERED" so Sheets
   interprets values (formulas, dates, numbers) rather than storing
   everything as literal text.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.registry import tool
from app.core.types import PermissionLevel
from app.core.google_auth import get_google_service
from app.core.exceptions import GoogleAPIError


class SheetsInfoInput(BaseModel):
    spreadsheet_id: str
    model_config = {"extra": "forbid"}


@tool(
    "sheets_get_info",
    permission=PermissionLevel.READ,
    description="Gets metadata about a spreadsheet, including sheet names and their numeric sheetId values (needed for delete operations).",
    input_schema=SheetsInfoInput,
    example_phrases=["get info about this spreadsheet", "list tabs in the sheet"],
)
def sheets_get_info(spreadsheet_id: str) -> dict:
    try:
        service = get_google_service("sheets")
        info = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = [
            {"sheetId": s["properties"]["sheetId"], "title": s["properties"]["title"]}
            for s in info.get("sheets", [])
        ]
        return {"title": info.get("properties", {}).get("title"), "sheets": sheets}
    except Exception as e:
        raise GoogleAPIError(f"Sheets get_info failed: {e}", context={"spreadsheet_id": spreadsheet_id}) from e


class SheetsReadRangeInput(BaseModel):
    spreadsheet_id: str
    range_a1: str = Field(..., description="A1 notation, e.g. 'Sheet1!A1:C10'")
    model_config = {"extra": "forbid"}


@tool(
    "sheets_read_range",
    permission=PermissionLevel.READ,
    description="Reads a cell range from a Google Sheet using A1 notation.",
    input_schema=SheetsReadRangeInput,
    example_phrases=["read this google sheet", "get data from the spreadsheet"],
)
def sheets_read_range(spreadsheet_id: str, range_a1: str) -> dict:
    try:
        service = get_google_service("sheets")
        result = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_a1).execute()
        return {"range": range_a1, "values": result.get("values", [])}
    except Exception as e:
        raise GoogleAPIError(f"Sheets read_range failed: {e}", context={"range_a1": range_a1}) from e


class SheetsWriteRangeInput(BaseModel):
    spreadsheet_id: str
    range_a1: str = Field(..., description="A1 notation, e.g. 'Sheet1!A1'")
    values: list[list] = Field(..., description="2D list of values to write, starting at the top-left of range_a1")
    model_config = {"extra": "forbid"}


@tool(
    "sheets_write_range",
    permission=PermissionLevel.MODIFY,
    description="Writes values into a Google Sheet range. Values are interpreted (USER_ENTERED) so formulas/dates work.",
    input_schema=SheetsWriteRangeInput,
    example_phrases=["write to this google sheet", "update the spreadsheet"],
)
def sheets_write_range(spreadsheet_id: str, range_a1: str, values: list) -> dict:
    try:
        service = get_google_service("sheets")
        result = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_a1,
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()
        return {"updated_range": result.get("updatedRange"), "updated_cells": result.get("updatedCells")}
    except Exception as e:
        raise GoogleAPIError(f"Sheets write_range failed: {e}", context={"range_a1": range_a1}) from e


class SheetsDeleteSheetInput(BaseModel):
    spreadsheet_id: str
    sheet_id: int = Field(..., description="Numeric sheetId (NOT the title) — get this via sheets_get_info first")
    model_config = {"extra": "forbid"}


@tool(
    "sheets_delete_sheet",
    permission=PermissionLevel.DELETE,
    description="Deletes a sheet/tab from a spreadsheet by its numeric sheetId (use sheets_get_info to find it).",
    input_schema=SheetsDeleteSheetInput,
    example_phrases=["delete this sheet tab", "remove a tab from the spreadsheet"],
)
def sheets_delete_sheet(spreadsheet_id: str, sheet_id: int) -> dict:
    try:
        service = get_google_service("sheets")
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"deleteSheet": {"sheetId": sheet_id}}]},
        ).execute()
        return {"deleted_sheet_id": sheet_id}
    except Exception as e:
        raise GoogleAPIError(f"Sheets delete_sheet failed: {e}", context={"sheet_id": sheet_id}) from e