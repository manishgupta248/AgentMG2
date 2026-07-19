"""
OCR-based PDF text extraction for scanned/image-only PDFs (e.g. PDFs
produced via "Print to PDF" that have no embedded text layer — see
M8 Step 1 verification, which surfaced exactly this case).

Uses PyMuPDF (fitz) to rasterize each page to an image, then
pytesseract (wrapping the real Tesseract-OCR install) to extract text.
Page-ranged, same discipline as pdf_extract_text — never OCRs an
entire large document at once unless explicitly asked to.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io

from app.core.registry import tool
from app.core.types import PermissionLevel
from app.core.config import settings
from app.core.exceptions import ToolExecutionError

pytesseract.pytesseract.tesseract_cmd = str(settings.tesseract_cmd_path)


def _validate_pdf_path(file_path: str) -> Path:
    path = Path(file_path)
    if not path.exists():
        raise ToolExecutionError(f"PDF file not found: {file_path}", context={"file_path": file_path})
    return path


class PdfOcrInput(BaseModel):
    file_path: str
    start_page: int = Field(1, ge=1, description="1-indexed, inclusive")
    end_page: int | None = Field(None, description="1-indexed, inclusive. If omitted, reads to the last page")
    dpi: int = Field(200, description="Rasterization resolution — higher is more accurate but slower")
    model_config = {"extra": "forbid"}


@tool(
    "pdf_ocr_extract_text",
    permission=PermissionLevel.READ,
    description="OCRs a page range of a scanned/image-only PDF (no embedded text layer) using Tesseract, returning extracted text.",
    input_schema=PdfOcrInput,
    example_phrases=["ocr this scanned pdf", "extract text from the scanned document"],
)
def pdf_ocr_extract_text(file_path: str, start_page: int = 1, end_page: int | None = None, dpi: int = 200) -> dict:
    path = _validate_pdf_path(file_path)
    try:
        doc = fitz.open(str(path))
        total_pages = len(doc)
        actual_end = end_page if end_page is not None else total_pages

        if start_page > total_pages:
            raise ToolExecutionError(
                f"start_page {start_page} exceeds total page count {total_pages}",
                context={"file_path": file_path},
            )

        actual_end = min(actual_end, total_pages)
        zoom = dpi / 72  # PyMuPDF's default is 72 dpi
        matrix = fitz.Matrix(zoom, zoom)

        pages_text = []
        for page_num in range(start_page, actual_end + 1):
            page = doc[page_num - 1]
            pix = page.get_pixmap(matrix=matrix)
            img_bytes = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_bytes))
            text = pytesseract.image_to_string(image)
            pages_text.append({"page": page_num, "text": text})

        doc.close()

        return {
            "total_pages": total_pages,
            "extracted_range": [start_page, actual_end],
            "dpi": dpi,
            "pages": pages_text,
        }
    except ToolExecutionError:
        raise
    except Exception as e:
        raise ToolExecutionError(f"Failed to OCR PDF: {e}", context={"file_path": file_path}) from e