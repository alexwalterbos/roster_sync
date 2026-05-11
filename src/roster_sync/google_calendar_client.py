from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from .models import CalendarEventDraft


class GoogleCalendarClient(Protocol):
    def upsert_event(self, event: CalendarEventDraft, google_event_id: str | None = None) -> str:
        """Create or update an event and return its Google event id."""

    def list_managed_events_in_range(self, start_at: datetime, end_at: datetime) -> list[dict]:
        """List Google events in the range that have a managed source id."""

    def delete_event(self, google_event_id: str) -> None:
        """Delete a Google event by id."""


class StubGoogleCalendarClient:
    def upsert_event(self, event: CalendarEventDraft, google_event_id: str | None = None) -> str:
        raise NotImplementedError(
            "Google Calendar sync is not implemented yet. Use the preview CLI first."
        )

    def list_managed_events_in_range(self, start_at: datetime, end_at: datetime) -> list[dict]:
        raise NotImplementedError(
            "Google Calendar sync is not implemented yet. Use the preview CLI first."
        )

    def delete_event(self, google_event_id: str) -> None:
        raise NotImplementedError(
            "Google Calendar sync is not implemented yet. Use the preview CLI first."
        )


class ServiceAccountGoogleCalendarClient:
    def __init__(self, calendar_id: str, credentials_path: Path) -> None:
        self.calendar_id = calendar_id
        self.credentials_path = credentials_path
        self._service = None

    def upsert_event(self, event: CalendarEventDraft, google_event_id: str | None = None) -> str:
        body = _event_to_google_payload(event)
        service = self._get_service()
        events_resource = service.events()

        if google_event_id:
            result = (
                events_resource.update(
                    calendarId=self.calendar_id,
                    eventId=google_event_id,
                    body=body,
                )
                .execute()
            )
        else:
            result = events_resource.insert(calendarId=self.calendar_id, body=body).execute()
        return result["id"]

    def list_managed_events_in_range(self, start_at: datetime, end_at: datetime) -> list[dict]:
        service = self._get_service()
        events_resource = service.events()
        page_token = None
        managed_events: list[dict] = []

        while True:
            response = (
                events_resource.list(
                    calendarId=self.calendar_id,
                    timeMin=start_at.isoformat(),
                    timeMax=end_at.isoformat(),
                    singleEvents=True,
                    showDeleted=False,
                    maxResults=2500,
                    pageToken=page_token,
                ).execute()
            )
            for item in response.get("items", []):
                source_id = (
                    item.get("extendedProperties", {})
                    .get("private", {})
                    .get("source_id")
                )
                if source_id:
                    managed_events.append(item)

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return managed_events

    def delete_event(self, google_event_id: str) -> None:
        service = self._get_service()
        service.events().delete(
            calendarId=self.calendar_id,
            eventId=google_event_id,
        ).execute()

    def _get_service(self):
        if self._service is not None:
            return self._service

        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        credentials = Credentials.from_service_account_file(
            str(self.credentials_path),
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        self._service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        return self._service


def event_content_hash(event: CalendarEventDraft) -> str:
    payload = {
        "source_id": event.source_id,
        "title": event.title,
        "start_at": event.start_at.isoformat(),
        "end_at": event.end_at.isoformat(),
        "all_day": event.all_day,
        "description": event.description,
        "location": event.location,
    }
    return sha256(repr(payload).encode("utf-8")).hexdigest()


def _event_to_google_payload(event: CalendarEventDraft) -> dict:
    body = {
        "summary": event.title,
        "description": event.description,
        "extendedProperties": {
            "private": {
                "source_id": event.source_id,
            }
        },
    }
    if event.location:
        body["location"] = event.location

    if event.all_day:
        body["start"] = {"date": event.start_at.date().isoformat()}
        body["end"] = {"date": event.end_at.date().isoformat()}
    else:
        timezone_name = getattr(event.start_at.tzinfo, "key", None)
        body["start"] = {
            "dateTime": event.start_at.isoformat(),
            "timeZone": timezone_name,
        }
        body["end"] = {
            "dateTime": event.end_at.isoformat(),
            "timeZone": timezone_name,
        }

    return body
