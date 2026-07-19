"""
Regression tests for PDF tools.

Text-extraction and table tests use a real synthetic PDF built with
pypdf (simple, fast, no OCR needed). OCR tests are lighter-weight —
they verify the tool runs end-to-end without crashing and handles
errors correctly; the substantive OCR accuracy was already verified
live against a real scanned document (see M8 Step 2 verification).
"""

from pathlib import Path

import pytest
from pypdf import PdfWriter

from app.core.registry import autodiscover_tools
from app.core.executor import call_tool
from app.core.exceptions import ToolExecutionError


@pytest.fixture()
def sample_pdf(tmp_path):
    """A minimal real 2-page PDF (blank pages, no text layer — pypdf's
    writer doesn't easily embed text without reportlab). Good enough to
    test page-count, page-ranging, and error paths."""
    file_path = tmp_path / "sample.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    with open(file_path, "wb") as f:
        writer.write(f)
    return str(file_path)


def test_pdf_info_returns_correct_page_count(sample_pdf):
    autodiscover_tools()
    result = call_tool("pdf_info", {"file_path": sample_pdf})
    assert result.data["page_count"] == 2


def test_pdf_info_nonexistent_file_raises(tmp_path):
    autodiscover_tools()
    fake_path = str(tmp_path / "nope.pdf")
    with pytest.raises(ToolExecutionError):
        call_tool("pdf_info", {"file_path": fake_path})


def test_pdf_extract_text_respects_page_range(sample_pdf):
    autodiscover_tools()
    result = call_tool("pdf_extract_text", {"file_path": sample_pdf, "start_page": 1, "end_page": 1})
    assert result.data["total_pages"] == 2
    assert result.data["extracted_range"] == [1, 1]
    assert len(result.data["pages"]) == 1


def test_pdf_extract_text_defaults_to_full_document(sample_pdf):
    autodiscover_tools()
    result = call_tool("pdf_extract_text", {"file_path": sample_pdf})
    assert result.data["extracted_range"] == [1, 2]
    assert len(result.data["pages"]) == 2


def test_pdf_extract_text_start_page_beyond_total_raises(sample_pdf):
    autodiscover_tools()
    with pytest.raises(ToolExecutionError):
        call_tool("pdf_extract_text", {"file_path": sample_pdf, "start_page": 99})


def test_pdf_extract_text_end_page_beyond_total_is_clamped(sample_pdf):
    """Requesting more pages than exist should clamp, not error."""
    autodiscover_tools()
    result = call_tool("pdf_extract_text", {"file_path": sample_pdf, "start_page": 1, "end_page": 999})
    assert result.data["extracted_range"] == [1, 2]


def test_pdf_extract_tables_on_blank_page_returns_empty(sample_pdf):
    autodiscover_tools()
    result = call_tool("pdf_extract_tables", {"file_path": sample_pdf, "page": 1})
    assert result.data["table_count"] == 0
    assert result.data["tables"] == []


def test_pdf_extract_tables_page_beyond_total_raises(sample_pdf):
    autodiscover_tools()
    with pytest.raises(ToolExecutionError):
        call_tool("pdf_extract_tables", {"file_path": sample_pdf, "page": 99})


def test_pdf_ocr_runs_without_crashing_on_blank_page(sample_pdf):
    """Not testing OCR accuracy here (a blank page has no text to find) —
    just that the tool runs end-to-end without error on a real PDF.
    Real OCR accuracy was verified live in M8 Step 2 against a real
    scanned document."""
    autodiscover_tools()
    result = call_tool("pdf_ocr_extract_text", {"file_path": sample_pdf, "start_page": 1, "end_page": 1})
    assert result.data["total_pages"] == 2
    assert len(result.data["pages"]) == 1
    assert result.data["pages"][0]["text"].strip() == ""  # blank page -> no text found


def test_pdf_ocr_nonexistent_file_raises(tmp_path):
    autodiscover_tools()
    fake_path = str(tmp_path / "nope.pdf")
    with pytest.raises(ToolExecutionError):
        call_tool("pdf_ocr_extract_text", {"file_path": fake_path})


def test_pdf_ocr_start_page_beyond_total_raises(sample_pdf):
    autodiscover_tools()
    with pytest.raises(ToolExecutionError):
        call_tool("pdf_ocr_extract_text", {"file_path": sample_pdf, "start_page": 99})