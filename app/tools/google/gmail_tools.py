"""
Gmail tools. Body extraction requires recursive MIME-part walking and
urlsafe_b64decode — Gmail's API returns message bodies as base64url-
encoded parts, often nested (multipart/alternative, multipart/mixed,
attachments, etc.), so a naive single-level read misses most real
emails.
"""

from __future__ import annotations

import base64
from email.mime.text import MIMEText
import re

from pydantic import BaseModel, Field

from app.core.registry import tool
from app.core.types import PermissionLevel
from app.core.google_auth import get_google_service
from app.core.exceptions import GoogleAPIError


def _extract_body_from_payload(payload: dict) -> str:
    """
    Recursively walks MIME parts to find a text/plain body. Gmail
    message payloads can nest parts arbitrarily (multipart/alternative
    containing multipart/related containing the actual text/plain, etc.)
    — a single-level check on payload['parts'] misses these.
    """
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain" and payload.get("body", {}).get("data"):
        data = payload["body"]["data"]
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    if "parts" in payload:
        for part in payload["parts"]:
            result = _extract_body_from_payload(part)
            if result:
                return result

    # Fallback: text/html if no text/plain was found anywhere — strip
    # tags so the result is readable/summarizable rather than raw markup.
    if mime_type == "text/html" and payload.get("body", {}).get("data"):
        data = payload["body"]["data"]
        html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        return _strip_html(html)

    return ""

def _strip_html(html: str) -> str:
    """Crude but effective HTML-to-text: strips tags, collapses whitespace.
    Good enough for making email bodies readable/summarizable; not a
    full HTML renderer."""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def _get_header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


class GmailSearchInput(BaseModel):
    query: str = Field(..., description="Gmail search syntax, e.g. 'is:unread', 'from:someone@example.com'")
    max_results: int = Field(10, ge=1, le=50)
    model_config = {"extra": "forbid"}


@tool(
    "gmail_search",
    permission=PermissionLevel.READ,
    description="Searches Gmail messages using Gmail search syntax, returns message summaries.",
    input_schema=GmailSearchInput,
    example_phrases=["search my unread emails", "find emails from someone"],
)
def gmail_search(query: str, max_results: int = 10) -> dict:
    try:
        service = get_google_service("gmail")
        results = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
        message_ids = [m["id"] for m in results.get("messages", [])]

        summaries = []
        for msg_id in message_ids:
            msg = service.users().messages().get(userId="me", id=msg_id, format="metadata",
                                                    metadataHeaders=["Subject", "From", "Date"]).execute()
            headers = msg.get("payload", {}).get("headers", [])
            summaries.append({
                "id": msg_id,
                "subject": _get_header(headers, "Subject"),
                "from": _get_header(headers, "From"),
                "date": _get_header(headers, "Date"),
                "snippet": msg.get("snippet", ""),
            })

        return {"query": query, "count": len(summaries), "messages": summaries}
    except Exception as e:
        raise GoogleAPIError(f"Gmail search failed: {e}", context={"query": query}) from e


class GmailReadInput(BaseModel):
    message_id: str
    model_config = {"extra": "forbid"}


@tool(
    "gmail_read_message",
    permission=PermissionLevel.READ,
    description="Reads the full body of a specific Gmail message by ID.",
    input_schema=GmailReadInput,
    example_phrases=["read this email", "get the full email content"],
)
def gmail_read_message(message_id: str) -> dict:
    try:
        service = get_google_service("gmail")
        msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        headers = msg.get("payload", {}).get("headers", [])
        body = _extract_body_from_payload(msg.get("payload", {}))

        return {
            "id": message_id,
            "subject": _get_header(headers, "Subject"),
            "from": _get_header(headers, "From"),
            "to": _get_header(headers, "To"),
            "date": _get_header(headers, "Date"),
            "body": body,
        }
    except Exception as e:
        raise GoogleAPIError(f"Gmail read failed: {e}", context={"message_id": message_id}) from e


class GmailSendInput(BaseModel):
    to: str
    subject: str
    body: str
    model_config = {"extra": "forbid"}


@tool(
    "gmail_send",
    permission=PermissionLevel.MODIFY,
    description="Sends an email via Gmail.",
    input_schema=GmailSendInput,
    example_phrases=["send an email", "email someone"],
)
def gmail_send(to: str, subject: str, body: str) -> dict:
    try:
        service = get_google_service("gmail")
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return {"sent_message_id": sent.get("id"), "to": to, "subject": subject}
    except Exception as e:
        raise GoogleAPIError(f"Gmail send failed: {e}", context={"to": to, "subject": subject}) from e