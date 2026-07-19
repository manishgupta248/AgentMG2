from app.core.registry import autodiscover_tools
from app.core.executor import call_tool

PDF_PATH = r"D:\Agent\data\test.pdf"  # same file as before — the scanned one

autodiscover_tools()

r = call_tool("pdf_ocr_extract_text", {"file_path": PDF_PATH, "start_page": 1, "end_page": 2})
print("Total pages:", r.data["total_pages"])
print("DPI used:", r.data["dpi"])
for page in r.data["pages"]:
    print(f"\n--- Page {page['page']} OCR text ---")
    print(page["text"][:1000])