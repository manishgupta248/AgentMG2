"""
Regression tests for Gmail body extraction — the recursive MIME-part
walk and HTML-stripping fallback. Uses synthetic payloads matching
Gmail API's real response shape, no live API calls needed for this
part (pure data transformation logic).
"""

import base64

from app.tools.google.gmail_tools import _extract_body_from_payload, _strip_html, _get_header


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8")


def test_extracts_simple_text_plain_body():
    payload = {"mimeType": "text/plain", "body": {"data": _b64("Hello world")}}
    assert _extract_body_from_payload(payload) == "Hello world"


def test_extracts_text_plain_from_single_level_nested_parts():
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": _b64("Nested plain text")}},
        ],
    }
    assert _extract_body_from_payload(payload) == "Nested plain text"


def test_extracts_text_plain_from_deeply_nested_parts():
    """The exact scenario the recursive walk exists for: multipart/mixed
    containing multipart/alternative containing the actual text/plain part."""
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "multipart/alternative",
                "parts": [
                    {"mimeType": "text/plain", "body": {"data": _b64("Deeply nested text")}},
                    {"mimeType": "text/html", "body": {"data": _b64("<p>Deeply nested html</p>")}},
                ],
            }
        ],
    }
    # Should prefer text/plain even though it's nested deeper than html
    assert _extract_body_from_payload(payload) == "Deeply nested text"


def test_falls_back_to_html_when_no_plain_text_exists():
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/html", "body": {"data": _b64("<p>Only <b>html</b> here</p>")}},
        ],
    }
    result = _extract_body_from_payload(payload)
    assert "Only" in result and "html" in result and "here" in result
    assert "<" not in result  # tags stripped


def test_returns_empty_string_for_payload_with_no_body_data():
    payload = {"mimeType": "multipart/mixed", "parts": []}
    assert _extract_body_from_payload(payload) == ""


def test_strip_html_removes_script_and_style_content():
    html = "<html><head><style>body{color:red}</style></head><body><script>alert(1)</script><p>Real text</p></body></html>"
    result = _strip_html(html)
    assert "Real text" in result
    assert "color:red" not in result
    assert "alert" not in result


def test_strip_html_decodes_common_entities():
    html = "<p>Tom &amp; Jerry&nbsp;forever</p>"
    result = _strip_html(html)
    assert "Tom & Jerry forever" in result


def test_get_header_finds_matching_header_case_insensitive():
    headers = [{"name": "Subject", "value": "Test Subject"}, {"name": "From", "value": "a@b.com"}]
    assert _get_header(headers, "subject") == "Test Subject"
    assert _get_header(headers, "FROM") == "a@b.com"


def test_get_header_returns_empty_string_when_not_found():
    headers = [{"name": "Subject", "value": "Test"}]
    assert _get_header(headers, "To") == ""