"""Google Calendar tools — list events, create event, delete event."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.core.registry import tool
from app.core.types import PermissionLevel
from app.core.google_auth import get_google_service
from app.core.exceptions import GoogleAPIError


class CalendarListEventsInput(BaseModel):
    calendar_id: str = Field("primary", description="Use 'primary' for the main calendar")
    max_results: int = Field(10, ge=1, le=50)
    time_min: str | None = Field(None, description="RFC3339 timestamp; defaults to now")
    model_config = {"extra": "forbid"}


@tool(
    "calendar_list_events",
    permission=PermissionLevel.READ,
    description="Lists upcoming events on a Google Calendar.",
    input_schema=CalendarListEventsInput,
    example_phrases=["what's on my calendar", "list upcoming events"],
)
def calendar_list_events(calendar_id: str = "primary", max_results: int = 10, time_min: str | None = None) -> dict:
    try:
        service = get_google_service("calendar")
        actual_time_min = time_min or datetime.now(timezone.utc).isoformat()
        results = service.events().list(
            calendarId=calendar_id,
            timeMin=actual_time_min,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = []
        for e in results.get("items", []):
            start = e.get("start", {}).get("dateTime", e.get("start", {}).get("date"))
            events.append({
                "id": e["id"],
                "summary": e.get("summary", "(no title)"),
                "start": start,
                "location": e.get("location", ""),
            })

        return {"count": len(events), "events": events}
    except Exception as e:
        raise GoogleAPIError(f"Calendar list events failed: {e}", context={"calendar_id": calendar_id}) from e


class CalendarCreateEventInput(BaseModel):
    calendar_id: str = "primary"
    summary: str
    start_datetime: str = Field(..., description="RFC3339, e.g. '2026-08-01T10:00:00+05:30'")
    end_datetime: str = Field(..., description="RFC3339, e.g. '2026-08-01T11:00:00+05:30'")
    description: str | None = None
    location: str | None = None
    model_config = {"extra": "forbid"}


@tool(
    "calendar_create_event",
    permission=PermissionLevel.MODIFY,
    description="Creates a new event on a Google Calendar.",
    input_schema=CalendarCreateEventInput,
    example_phrases=["add an event to my calendar", "schedule a meeting"],
)
def calendar_create_event(
    summary: str,
    start_datetime: str,
    end_datetime: str,
    calendar_id: str = "primary",
    description: str | None = None,
    location: str | None = None,
) -> dict:
    try:
        service = get_google_service("calendar")
        event_body = {
            "summary": summary,
            "start": {"dateTime": start_datetime},
            "end": {"dateTime": end_datetime},
        }
        if description:
            event_body["description"] = description
        if location:
            event_body["location"] = location

        created = service.events().insert(calendarId=calendar_id, body=event_body).execute()
        return {"event_id": created["id"], "summary": created.get("summary"), "link": created.get("htmlLink")}
    except Exception as e:
        raise GoogleAPIError(f"Calendar create event failed: {e}", context={"summary": summary}) from e


class CalendarDeleteEventInput(BaseModel):
    calendar_id: str = "primary"
    event_id: str
    model_config = {"extra": "forbid"}


@tool(
    "calendar_delete_event",
    permission=PermissionLevel.DELETE,
    description="Deletes an event from a Google Calendar.",
    input_schema=CalendarDeleteEventInput,
    example_phrases=["delete this calendar event", "remove the meeting"],
)
def calendar_delete_event(event_id: str, calendar_id: str = "primary") -> dict:
    try:
        service = get_google_service("calendar")
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        return {"deleted_event_id": event_id}
    except Exception as e:
        raise GoogleAPIError(f"Calendar delete event failed: {e}", context={"event_id": event_id}) from e