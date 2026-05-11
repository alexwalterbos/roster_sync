from __future__ import annotations

from datetime import datetime, timezone

from .calendar_mapper import map_entries_to_events
from .google_calendar_client import GoogleCalendarClient, event_content_hash
from .html_parser import RosterHtmlParser
from .state_store import StateStore


class SyncService:
    def __init__(
        self,
        parser: RosterHtmlParser,
        state_store: StateStore,
        google_client: GoogleCalendarClient,
    ) -> None:
        self.parser = parser
        self.state_store = state_store
        self.google_client = google_client

    def preview_html(self, html: str):
        parsed = self.parser.parse_month(html)
        return map_entries_to_events(parsed.entries)

    def sync_html(self, html: str) -> list[str]:
        self.state_store.ensure_schema()
        parsed = self.parser.parse_month(html)
        events = map_entries_to_events(parsed.entries)
        source_ids = {event.source_id for event in events}
        event_ids: list[str] = []
        for event in events:
            content_hash = event_content_hash(event)
            mapping = self.state_store.get_mapping(event.source_id)
            if mapping is not None:
                existing_event_id, existing_hash = mapping
                if existing_hash == content_hash:
                    event_ids.append(existing_event_id)
                    continue
            else:
                existing_event_id = None

            google_event_id = self.google_client.upsert_event(event, existing_event_id)
            self.state_store.save_mapping(event.source_id, google_event_id, content_hash)
            event_ids.append(google_event_id)

        range_start, range_end = _month_range_utc(parsed.navigation.current_period)
        for item in self.google_client.list_managed_events_in_range(range_start, range_end):
            source_id = (
                item.get("extendedProperties", {})
                .get("private", {})
                .get("source_id")
            )
            google_event_id = item.get("id")
            if not source_id or not google_event_id:
                continue
            if source_id in source_ids:
                continue
            self.google_client.delete_event(google_event_id)

        return event_ids


def _month_range_utc(period: str | None) -> tuple[datetime, datetime]:
    if period is None:
        now = datetime.now(timezone.utc)
        start_at = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        year_str, month_str = period.split("-", 1)
        start_at = datetime(
            int(year_str),
            int(month_str),
            1,
            tzinfo=timezone.utc,
        )

    if start_at.month == 12:
        end_at = datetime(start_at.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end_at = datetime(start_at.year, start_at.month + 1, 1, tzinfo=timezone.utc)

    return start_at, end_at
