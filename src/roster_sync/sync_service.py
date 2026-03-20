from __future__ import annotations

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
        event_ids: list[str] = []
        for event in self.preview_html(html):
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
        return event_ids
