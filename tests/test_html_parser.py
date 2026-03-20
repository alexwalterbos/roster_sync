from roster_sync.html_parser import RosterHtmlParser
from roster_sync.models import RosterEntryType
from zoneinfo import ZoneInfo


def test_parse_navigation_and_entries():
    html = open("tests/fixtures/roster_march_2026.html", encoding="utf-8").read()
    parser = RosterHtmlParser(timezone=ZoneInfo("Europe/Amsterdam"))

    parsed = parser.parse_month(html)

    assert parsed.navigation.current_period == "2026-03"
    assert parsed.navigation.previous_period == "2026-02"
    assert parsed.navigation.next_period == "2026-04"
    assert parsed.navigation.available_periods == ("2026-02", "2026-03", "2026-04", "2026-05")
    assert len(parsed.entries) == 4

    first_assignment = parsed.entries[0]
    assert first_assignment.entry_type is RosterEntryType.ASSIGNMENT
    assert first_assignment.source_id == "assignment://58425"
    assert first_assignment.title == "Example Venue > Department > Shift Alpha"
    assert first_assignment.start_at.isoformat() == "2026-03-04T10:30:00+01:00"
    assert first_assignment.end_at.isoformat() == "2026-03-04T17:30:00+01:00"
    assert first_assignment.break_minutes == 0
