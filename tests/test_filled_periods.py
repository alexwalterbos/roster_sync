from pathlib import Path

import requests

from roster_sync.dyflexis_client import FetchResult
from roster_sync.filled_periods import scan_filled_periods_from_current
from roster_sync.html_parser import RosterHtmlParser
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
        <thead>
          <tr>
            <th class="themeAccent" colspan="8"></th>
          </tr>
        </thead>
        <tr>
          <td title="2026-05-01"></td>
        </tr>
      </table>
    </div>
  </body>
</html>
"""


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_current_roster_html(self) -> FetchResult:
        self.calls.append("current")
        return FetchResult(
            html=MARCH_HTML,
            url="https://example.test/current",
            source="network",
            fetched_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )

    def fetch_roster_month_html(self, period: str) -> FetchResult:
        self.calls.append(period)
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


class FailingNextMonthClient(FakeClient):
    def fetch_roster_month_html(self, period: str) -> FetchResult:
        if period == "2026-04":
            raise requests.ConnectionError("DNS resolution failed for example.invalid")
        return super().fetch_roster_month_html(period)


def test_scan_filled_periods_stops_at_first_empty_month():
    parser = RosterHtmlParser(timezone=ZoneInfo("Europe/Amsterdam"))
    client = FakeClient()

    scan = scan_filled_periods_from_current(client=client, parser=parser)

    assert scan.start_period == "2026-03"
    assert scan.last_filled_period == "2026-04"
    assert scan.stop_period == "2026-05"
    assert [
        (period.period, period.entry_count, period.syncable_event_count)
        for period in scan.periods
    ] == [
        ("2026-03", 4, 4),
        ("2026-04", 1, 1),
        ("2026-05", 0, 0),
    ]


def test_scan_filled_periods_returns_partial_result_on_network_failure():
    parser = RosterHtmlParser(timezone=ZoneInfo("Europe/Amsterdam"))
    client = FailingNextMonthClient()

    scan = scan_filled_periods_from_current(client=client, parser=parser)

    assert scan.start_period == "2026-03"
    assert scan.last_filled_period == "2026-03"
    assert scan.stop_period is None
    assert scan.error_period == "2026-04"
    assert "DNS resolution failed" in (scan.error_message or "")
    assert [
        (period.period, period.entry_count, period.syncable_event_count)
        for period in scan.periods
    ] == [
        ("2026-03", 4, 4),
    ]
