from pathlib import Path

from roster_sync.google_calendar_client import event_content_hash
from roster_sync.html_parser import RosterHtmlParser
from roster_sync.sync_service import SyncService
from roster_sync.state_store import StateStore
from zoneinfo import ZoneInfo


class FakeGoogleCalendarClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []
        self.deleted: list[str] = []

    def upsert_event(self, event, google_event_id: str | None = None) -> str:
        self.calls.append((event.source_id, google_event_id))
        return google_event_id or f"google-{event.source_id}"

    def list_managed_events_in_range(self, start_at, end_at) -> list[dict]:
        return []

    def delete_event(self, google_event_id: str) -> None:
        self.deleted.append(google_event_id)


def test_sync_html_skips_unchanged_items(tmp_path: Path):
    html = Path("tests/fixtures/roster_march_2026.html").read_text(encoding="utf-8")
    parser = RosterHtmlParser(timezone=ZoneInfo("Europe/Amsterdam"))
    state_store = StateStore(tmp_path / "state.sqlite3")
    fake_client = FakeGoogleCalendarClient()
    service = SyncService(parser=parser, state_store=state_store, google_client=fake_client)

    first_ids = service.sync_html(html)
    second_ids = service.sync_html(html)

    assert len(first_ids) == 4
    assert second_ids == first_ids
    assert len(fake_client.calls) == 4


def test_sync_html_updates_existing_event_when_hash_changes(tmp_path: Path):
    html = Path("tests/fixtures/roster_march_2026.html").read_text(encoding="utf-8")
    parser = RosterHtmlParser(timezone=ZoneInfo("Europe/Amsterdam"))
    state_store = StateStore(tmp_path / "state.sqlite3")
    fake_client = FakeGoogleCalendarClient()
    service = SyncService(parser=parser, state_store=state_store, google_client=fake_client)

    service.sync_html(html)

    parsed = parser.parse_month(html)
    changed_event = service.preview_html(html)[0]
    changed_event.title = f"{changed_event.title} UPDATED"
    state_store.save_mapping(
        changed_event.source_id,
        "google-existing-id",
        event_content_hash(service.preview_html(html)[0]),
    )

    fake_client.calls.clear()
    fake_client.upsert_event(changed_event, "google-existing-id")

    assert fake_client.calls == [(changed_event.source_id, "google-existing-id")]
