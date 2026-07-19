"""
Unified Google OAuth client manager.

Design: ONE credentials.json + ONE token.json cover all four scopes
(Gmail, Drive, Calendar, Sheets) — confirmed present with correct
scopes in M9 Step 1. Service clients are cached per-process in a
module-level dict keyed by service name, so the OAuth flow and token
load happen only once per run, not once per tool call.

Token refresh: if the cached credentials are expired but have a
refresh_token, they're refreshed automatically and the refreshed
token is written back to token.json so future runs don't need to
re-refresh immediately.
"""

from __future__ import annotations

import json

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build, Resource

from app.core.config import settings
from app.core.logging_setup import logger
from app.core.exceptions import GoogleAPIError

REQUIRED_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets",
]

# Service name -> (api_name, api_version)
_SERVICE_SPECS: dict[str, tuple[str, str]] = {
    "gmail": ("gmail", "v1"),
    "drive": ("drive", "v3"),
    "calendar": ("calendar", "v3"),
    "sheets": ("sheets", "v4"),
}

# Process-wide cache: service name -> built Resource client
_SERVICE_CACHE: dict[str, Resource] = {}
_CREDENTIALS_CACHE: Credentials | None = None


def _load_credentials() -> Credentials:
    """Loads token.json, refreshing if expired. Caches the Credentials
    object in-process so this only runs once per process (subsequent
    calls reuse the cached object, refreshing again only if it expires
    mid-run)."""
    global _CREDENTIALS_CACHE

    if _CREDENTIALS_CACHE is not None and _CREDENTIALS_CACHE.valid:
        return _CREDENTIALS_CACHE

    token_path = settings.google_token_path
    if not token_path.exists():
        raise GoogleAPIError(
            "token.json not found — Google OAuth has not been set up.",
            context={"token_path": str(token_path)},
        )

    try:
        creds = Credentials.from_authorized_user_file(str(token_path), REQUIRED_SCOPES)
    except Exception as e:
        raise GoogleAPIError(f"Failed to load token.json: {e}", context={"token_path": str(token_path)}) from e

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            logger.info("Google OAuth token refreshed successfully.")
            with open(token_path, "w") as f:
                f.write(creds.to_json())
        except Exception as e:
            raise GoogleAPIError(f"Failed to refresh Google OAuth token: {e}") from e

    if not creds.valid:
        raise GoogleAPIError(
            "Google OAuth credentials are invalid and could not be refreshed. "
            "token.json may need to be regenerated via a fresh consent flow."
        )

    _CREDENTIALS_CACHE = creds
    return creds


def get_google_service(service_name: str) -> Resource:
    """
    Returns a cached, ready-to-use Google API client for the given
    service ('gmail' | 'drive' | 'calendar' | 'sheets'). Built once
    per process and reused thereafter.
    """
    if service_name not in _SERVICE_SPECS:
        raise GoogleAPIError(f"Unknown Google service: {service_name}", context={"service_name": service_name})

    if service_name in _SERVICE_CACHE:
        return _SERVICE_CACHE[service_name]

    creds = _load_credentials()
    api_name, api_version = _SERVICE_SPECS[service_name]

    try:
        client = build(api_name, api_version, credentials=creds)
    except Exception as e:
        raise GoogleAPIError(f"Failed to build {service_name} client: {e}") from e

    _SERVICE_CACHE[service_name] = client
    logger.info("Google service client built and cached: {}", service_name)
    return client


__all__ = ["get_google_service", "REQUIRED_SCOPES"]