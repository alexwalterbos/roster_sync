from pathlib import Path

from roster_sync.filled_periods import scan_filled_periods_from_current
from roster_sync.dyflexis_client import FetchResult
from roster_sync.html_parser import RosterHtmlParser
from roster_sync.sync_service import SyncService
from roster_sync.state_store import StateStore
from zoneinfo import ZoneInfo


MARCH_HTML = Path("tests/fixtures/roster_march_2026.html").read_text(encoding="utf-8")

APRIL_HTML = """
<!DOCTYPE html>
<html>
  <body>
    <div flux="panel=none" id="rooster">
      <h1>
        <select>
          <option value="2026-03">maart 2026</option>
          <option selected="selected" value="2026-04">april 2026</option>
          <option value="2026-05">mei 2026</option>
        </select>
      </h1>
      <table class="calender">
        <thead>
          <tr>
            <th class="themeAccent" colspan="8">
              <div style="float:right;">
                <a href="https://example.invalid/example-customer/example-location/rooster2/index2?periode=2026-05">
                  Volgende maand
                </a>
              </div>
            </th>
          </tr>
        </thead>
        <tr>
          <td title="2026-04-04" class="activ-beschikbaar">
            <div uo="agenda://38185" class="agen agen-onbeschikbaar">Unavailable (pending)</div>
          </td>
        </tr>
      </table>
    </div>
  </body>
</html>
"""

MAY_EMPTY_HTML = """
<!DOCTYPE html>
<html>
  <body>
    <div flux="panel=none" id="rooster">
      <h1>
        <select>
          <option value="2026-04">april 2026</option>
          <option selected="selected" value="2026-05">mei 2026</option>
          <option value="2026-06">juni 2026</option>
        </select>
      </h1>
      <table class="calender">
        <tr><td title="2026-05-01"></td></tr>
      </table>
    </div>
  </body>
</html>
"""


class FakeClient:
    def fetch_current_roster_html(self) -> FetchResult:
        return FetchResult(
            html=MARCH_HTML,
            url="https://example.test/current",
            source="network",
            fetched_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )

    def fetch_roster_month_html(self, period: str) -> FetchResult:
        html = {
            "2026-04": APRIL_HTML,
            "2026-05": MAY_EMPTY_HTML,
        }[period]
        return FetchResult(
            html=html,
            url=f"https://example.test/{period}",
            source="network",
            fetched_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )

    @staticmethod
    def looks_like_roster_html(html: str) -> bool:
        return 'table class="calender"' in html and 'id="rooster"' in html


class FakeGoogleCalendarClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def upsert_event(self, event, google_event_id=None) -> str:
        self.calls.append(event.source_id)
        return google_event_id or f"google-{event.source_id}"


def test_filled_range_scan_can_drive_multi_month_sync(tmp_path):
    parser = RosterHtmlParser(timezone=ZoneInfo("Europe/Amsterdam"))
    client = FakeClient()
    google = FakeGoogleCalendarClient()
    state = StateStore(tmp_path / "state.sqlite3")
    service = SyncService(parser=parser, state_store=state, google_client=google)

    scan = scan_filled_periods_from_current(client=client, parser=parser)
    synced_counts = {}
    for period in scan.periods:
        if period.entry_count == 0:
            continue
        html = client.fetch_current_roster_html().html if period.period == scan.start_period else client.fetch_roster_month_html(period.period).html
        synced_counts[period.period] = len(service.sync_html(html))

    assert synced_counts == {"2026-03": 4, "2026-04": 1}
