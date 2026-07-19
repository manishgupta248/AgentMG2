"""
PDF text extraction tools using pdfplumber. Page-ranged extraction
avoids loading a whole large PDF's text into memory at once when the
caller only needs specific pages.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field
import pdfplumber

from app.core.registry import tool
from app.core.types import PermissionLevel
from app.core.exceptions import ToolExecutionError


def _validate_pdf_path(file_path: str) -> Path:
    path = Path(file_path)
    if not path.exists():
        raise ToolExecutionError(f"PDF file not found: {file_path}", context={"file_path": file_path})
    return path


class PdfInfoInput(BaseModel):
    file_path: str
    model_config = {"extra": "forbid"}


@tool(
    "pdf_info",
    permission=PermissionLevel.READ,
    description="Returns page count and basic metadata for a PDF file.",
    input_schema=PdfInfoInput,
    example_phrases=["how many pages in this pdf", "pdf metadata"],
)
def pdf_info(file_path: str) -> dict:
    path = _validate_pdf_path(file_path)
    try:
        with pdfplumber.open(str(path)) as pdf:
            return {
                "page_count": len(pdf.pages),
                "metadata": dict(pdf.metadata) if pdf.metadata else {},
            }
    except Exception as e:
        raise ToolExecutionError(f"Failed to read PDF info: {e}", context={"file_path": file_path}) from e


class PdfExtractTextInput(BaseModel):
    file_path: str
    start_page: int = Field(1, ge=1, description="1-indexed, inclusive")
    end_page: int | None = Field(None, description="1-indexed, inclusive. If omitted, reads to the last page")
    model_config = {"extra": "forbid"}


@tool(
    "pdf_extract_text",
    permission=PermissionLevel.READ,
    description="Extracts text from a page range in a PDF (page-ranged, does not load the whole document's text at once for large ranges).",
    input_schema=PdfExtractTextInput,
    example_phrases=["extract text from this pdf", "read pages 1 to 5 of the pdf"],
)
def pdf_extract_text(file_path: str, start_page: int = 1, end_page: int | None = None) -> dict:
    path = _validate_pdf_path(file_path)
    try:
        with pdfplumber.open(str(path)) as pdf:
            total_pages = len(pdf.pages)
            actual_end = end_page if end_page is not None else total_pages

            if start_page > total_pages:
                raise ToolExecutionError(
                    f"start_page {start_page} exceeds total page count {total_pages}",
                    context={"file_path": file_path},
                )

            actual_end = min(actual_end, total_pages)
            pages_text = []
            for page_num in range(start_page, actual_end + 1):
                page = pdf.pages[page_num - 1]
                text = page.extract_text() or ""
                pages_text.append({"page": page_num, "text": text})

            return {
                "total_pages": total_pages,
                "extracted_range": [start_page, actual_end],
                "pages": pages_text,
            }
    except ToolExecutionError:
        raise
    except Exception as e:
        raise ToolExecutionError(f"Failed to extract PDF text: {e}", context={"file_path": file_path}) from e


class PdfExtractTablesInput(BaseModel):
    file_path: str
    page: int = Field(..., ge=1, description="1-indexed page number to extract tables from")
    model_config = {"extra": "forbid"}


@tool(
    "pdf_extract_tables",
    permission=PermissionLevel.READ,
    description="Extracts tables (as lists of rows) from a single PDF page.",
    input_schema=PdfExtractTablesInput,
    example_phrases=["extract the table from this pdf", "get table data from page 2"],
)
def pdf_extract_tables(file_path: str, page: int) -> dict:
    path = _validate_pdf_path(file_path)
    try:
        with pdfplumber.open(str(path)) as pdf:
            if page > len(pdf.pages):
                raise ToolExecutionError(
                    f"page {page} exceeds total page count {len(pdf.pages)}",
                    context={"file_path": file_path},
                )
            tables = pdf.pages[page - 1].extract_tables()
            return {"page": page, "table_count": len(tables), "tables": tables}
    except ToolExecutionError:
        raise
    except Exception as e:
        raise ToolExecutionError(f"Failed to extract PDF tables: {e}", context={"file_path": file_path}) from e