from __future__ import annotations

import time

import requests

from .calendar_mapper import map_entries_to_events
from .dyflexis_client import DyflexisClient, FetchResult
from .html_parser import RosterHtmlParser
from .models import FilledPeriodCheck, FilledPeriodScan


def scan_filled_periods_from_current(
    *,
    client: DyflexisClient,
    parser: RosterHtmlParser,
    max_fetch_attempts: int = 3,
    initial_backoff_seconds: float = 1.0,
) -> FilledPeriodScan:
    current_result = client.fetch_current_roster_html()
    if not client.looks_like_roster_html(current_result.html):
        raise ValueError("Fetched HTML does not look like a Dyflexis roster page.")
    parsed = parser.parse_month(current_result.html)
    if not parsed.navigation.current_period:
        raise ValueError("Could not determine the current roster period from the HTML.")

    periods: list[FilledPeriodCheck] = []
    last_filled_period: str | None = None
    stop_period: str | None = None

    period = parsed.navigation.current_period
    result = current_result
    while True:
        parsed = parser.parse_month(result.html)
        entry_count = len(parsed.entries)
        syncable_event_count = len(map_entries_to_events(parsed.entries))
        periods.append(
            FilledPeriodCheck(
                period=period,
                entry_count=entry_count,
                syncable_event_count=syncable_event_count,
                fetch_source=result.source,
                fetch_url=result.url,
            )
        )

        if entry_count == 0:
            stop_period = period
            break

        last_filled_period = period
        next_period = parsed.navigation.next_period
        if next_period is None:
            break

        period = next_period
        try:
            result = _fetch_month_html_with_retry(
                client=client,
                period=period,
                max_fetch_attempts=max_fetch_attempts,
                initial_backoff_seconds=initial_backoff_seconds,
            )
        except requests.RequestException as exc:
            return FilledPeriodScan(
                start_period=periods[0].period,
                last_filled_period=last_filled_period,
                stop_period=None,
                periods=periods,
                error_period=period,
                error_message=(
                    f"{exc} (after {max_fetch_attempts} attempt"
                    f"{'' if max_fetch_attempts == 1 else 's'})"
                ),
            )
        if not client.looks_like_roster_html(result.html):
            raise ValueError(
                f"Fetched HTML for period {period} does not look like a Dyflexis roster page."
            )

    return FilledPeriodScan(
        start_period=periods[0].period,
        last_filled_period=last_filled_period,
        stop_period=stop_period,
        periods=periods,
        error_period=None,
        error_message=None,
    )


def _fetch_month_html_with_retry(
    *,
    client: DyflexisClient,
    period: str,
    max_fetch_attempts: int,
    initial_backoff_seconds: float,
) -> FetchResult:
    if max_fetch_attempts < 1:
        raise ValueError("max_fetch_attempts must be at least 1.")

    last_error: requests.RequestException | None = None
    for attempt_index in range(max_fetch_attempts):
        try:
            return client.fetch_roster_month_html(period)
        except requests.RequestException as exc:
            last_error = exc
            is_last_attempt = attempt_index + 1 >= max_fetch_attempts
            if is_last_attempt:
                break
            backoff_seconds = initial_backoff_seconds * (2**attempt_index)
            time.sleep(backoff_seconds)

    assert last_error is not None
    raise last_error
