# Dyflexis Roster Sync

Small Python application for scraping roster data from the Dyflexis month view and preparing it for Google Calendar sync.

## Current scope

- Fetch or load Dyflexis month-view HTML
- Parse roster assignments from the calendar table
- Preview normalized shifts as JSON
- Provide a clean seam for future Google Calendar upserts

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
roster-sync preview --html tests/fixtures/roster_march_2026.html
```

## Fetch from Dyflexis

For now you can either use a local session file at `.roster-sync/session.json` or export browser cookies to a Netscape/Mozilla cookie jar.

Example local session file:

```json
{
  "headers": {
    "User-Agent": "Mozilla/5.0 ...",
    "Accept-Language": "en-US,en;q=0.9"
  },
  "cookies": [
    {
      "name": "PHPSESSID",
      "value": "your-session-id",
      "domain": "example.invalid",
      "path": "/"
    }
  ]
}
```

Then:

```bash
roster-sync fetch-month 2026-03 --json
```

Live fetches are cache-first and rate-limited:

- the same logical page is not refetched for 15 minutes by default
- any network request is spaced at least 15 seconds apart by default
- cached HTML is stored in `.roster-sync/cache/`
- if a page cache is stale but the global debounce is still active, the stale cache is returned instead of making a new request

These defaults can be overridden with:

```bash
export DYFLEXIS_PAGE_MIN_INTERVAL_SECONDS=900
export DYFLEXIS_GLOBAL_MIN_INTERVAL_SECONDS=15
export DYFLEXIS_CACHE_DIR=.roster-sync/cache
```

Or with a cookie jar:

```bash
export DYFLEXIS_COOKIE_JAR=/path/to/dyflexis-cookies.txt
roster-sync fetch-month 2026-03 --json
```

or:

```bash
roster-sync fetch-current --cookie-jar /path/to/dyflexis-cookies.txt --save-html tmp/current.html
```

If the command says the HTML does not look like a roster page, the cookies are likely expired or incomplete.

## Planned next steps

- Add deletion handling for removed Dyflexis entries
- Add richer CLI output formats
- Support broader sync windows across multiple months

## Google Calendar sync

With a service account key at `.roster-sync/google-service-account.json` and a calendar id
at `.roster-sync/calendar_id.txt`, you can sync directly:

```bash
roster-sync sync-current
roster-sync sync-month 2026-03
```

The sync is idempotent:

- existing Dyflexis items are updated instead of duplicated
- unchanged items are skipped using a local content hash
- `Onbeschikbaar` entries are synced as all-day events
