from roster_sync.calendar_mapper import map_entries_to_events
from roster_sync.html_parser import RosterHtmlParser
from zoneinfo import ZoneInfo


def test_map_entries_to_events_includes_assignments_and_unavailability():
    html = open("tests/fixtures/roster_march_2026.html", encoding="utf-8").read()
    parser = RosterHtmlParser(timezone=ZoneInfo("Europe/Amsterdam"))

    parsed = parser.parse_month(html)
    events = map_entries_to_events(parsed.entries)

    assert len(events) == 4
    assert events[0].source_id == "assignment://58425"
    assert events[0].title == "Example Venue > Department > Shift Alpha"
    assert events[-1].start_at.isoformat() == "2026-03-08T11:00:00+01:00"
