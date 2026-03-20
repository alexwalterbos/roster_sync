from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .auth import build_session
from .cache import PageCache
from .config import AppConfig
from .dyflexis_client import DyflexisClient
from .filled_periods import scan_filled_periods_from_current
from .google_calendar_client import ServiceAccountGoogleCalendarClient, StubGoogleCalendarClient
from .html_parser import RosterHtmlParser
from .sync_service import SyncService
from .state_store import StateStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="roster-sync")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preview = subparsers.add_parser("preview", help="Parse saved Dyflexis HTML.")
    preview.add_argument("--html", type=Path, required=True, help="Path to saved HTML")

    fetch = subparsers.add_parser(
        "fetch-month",
        help="Fetch a Dyflexis month page using an authenticated cookie jar.",
    )
    fetch.add_argument("period", help="Month in YYYY-MM format")
    fetch.add_argument(
        "--cookie-jar",
        type=Path,
        help="Path to a Netscape/Mozilla cookie jar exported from the browser",
    )
    fetch.add_argument(
        "--save-html",
        type=Path,
        help="Optional path to save the fetched month HTML",
    )
    fetch.add_argument(
        "--json",
        action="store_true",
        help="Print parsed JSON instead of only saving HTML",
    )

    fetch_current = subparsers.add_parser(
        "fetch-current",
        help="Fetch the current Dyflexis roster page using an authenticated cookie jar.",
    )
    fetch_current.add_argument(
        "--cookie-jar",
        type=Path,
        help="Path to a Netscape/Mozilla cookie jar exported from the browser",
    )
    fetch_current.add_argument(
        "--save-html",
        type=Path,
        help="Optional path to save the fetched HTML",
    )
    fetch_current.add_argument(
        "--json",
        action="store_true",
        help="Print parsed JSON instead of only saving HTML",
    )

    check_filled = subparsers.add_parser(
        "check-filled-range",
        help="Fetch month by month from the current period until the first empty month.",
    )
    check_filled.add_argument(
        "--cookie-jar",
        type=Path,
        help="Path to a Netscape/Mozilla cookie jar exported from the browser",
    )

    sync_filled = subparsers.add_parser(
        "sync-filled-range",
        help="Fetch from the current period through the first empty month and sync all filled months.",
    )
    sync_filled.add_argument(
        "--cookie-jar",
        type=Path,
        help="Path to a Netscape/Mozilla cookie jar exported from the browser",
    )

    sync = subparsers.add_parser(
        "sync", help="Run a full sync from saved HTML using the configured backend."
    )
    sync.add_argument("--html", type=Path, required=True, help="Path to saved HTML")

    sync_current = subparsers.add_parser(
        "sync-current",
        help="Fetch the current Dyflexis roster page and sync it to Google Calendar.",
    )
    sync_current.add_argument(
        "--cookie-jar",
        type=Path,
        help="Path to a Netscape/Mozilla cookie jar exported from the browser",
    )

    sync_month = subparsers.add_parser(
        "sync-month",
        help="Fetch a Dyflexis month page and sync it to Google Calendar.",
    )
    sync_month.add_argument("period", help="Month in YYYY-MM format")
    sync_month.add_argument(
        "--cookie-jar",
        type=Path,
        help="Path to a Netscape/Mozilla cookie jar exported from the browser",
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = AppConfig()
    parser = RosterHtmlParser(timezone=config.timezone)

    if args.command == "preview":
        html = args.html.read_text(encoding="utf-8")
        parsed = parser.parse_month(html)
        print(_to_json(parsed))
        return 0

    if args.command in {"fetch-month", "fetch-current"}:
        client = _build_dyflexis_client(config, getattr(args, "cookie_jar", None))
        if args.command == "fetch-month":
            result = client.fetch_roster_month_html(args.period)
        else:
            result = client.fetch_current_roster_html()
        html = result.html

        if not client.looks_like_roster_html(html):
            raise SystemExit(
                "Fetched HTML does not look like a Dyflexis roster page. "
                "The session may be expired or redirected to login."
            )

        if args.save_html:
            args.save_html.parent.mkdir(parents=True, exist_ok=True)
            args.save_html.write_text(html, encoding="utf-8")

        if args.json:
            parsed = parser.parse_month(html)
            payload = json.loads(_to_json(parsed))
            payload["_fetch"] = {
                "source": result.source,
                "url": result.url,
                "fetched_at": str(result.fetched_at),
                "cache_key": result.cache_key,
                "content_sha256": result.content_sha256,
                "status_code": result.status_code,
            }
            print(json.dumps(payload, indent=2, default=str))
        elif not args.save_html:
            print(html)
        return 0

    if args.command == "check-filled-range":
        client = _build_dyflexis_client(config, getattr(args, "cookie_jar", None))
        scan = scan_filled_periods_from_current(client=client, parser=parser)
        print(
            json.dumps(
                {
                    "start_period": scan.start_period,
                    "last_filled_period": scan.last_filled_period,
                    "stop_period": scan.stop_period,
                    "error_period": scan.error_period,
                    "error_message": scan.error_message,
                    "periods": [asdict(period) for period in scan.periods],
                },
                indent=2,
                default=str,
            )
        )
        return 0

    if args.command == "sync-filled-range":
        client = _build_dyflexis_client(config, getattr(args, "cookie_jar", None))
        scan = scan_filled_periods_from_current(client=client, parser=parser)
        service = SyncService(
            parser=parser,
            state_store=StateStore(config.state_db_path),
            google_client=_build_google_calendar_client(config),
        )

        synced_by_period: dict[str, list[str]] = {}
        for period in scan.periods:
            if period.entry_count == 0:
                continue
            if period.period == scan.start_period:
                result = client.fetch_current_roster_html()
            else:
                result = client.fetch_roster_month_html(period.period)
            synced_by_period[period.period] = service.sync_html(result.html)

        print(
            json.dumps(
                {
                    "start_period": scan.start_period,
                    "last_filled_period": scan.last_filled_period,
                    "stop_period": scan.stop_period,
                    "error_period": scan.error_period,
                    "error_message": scan.error_message,
                    "periods": [asdict(period) for period in scan.periods],
                    "synced_by_period": synced_by_period,
                },
                indent=2,
                default=str,
            )
        )
        return 0

    if args.command == "sync":
        html = args.html.read_text(encoding="utf-8")
        service = SyncService(
            parser=parser,
            state_store=StateStore(config.state_db_path),
            google_client=_build_google_calendar_client(config),
        )
        event_ids = service.sync_html(html)
        print(json.dumps({"synced_event_ids": event_ids}, indent=2))
        return 0

    if args.command in {"sync-current", "sync-month"}:
        client = _build_dyflexis_client(config, getattr(args, "cookie_jar", None))
        if args.command == "sync-month":
            result = client.fetch_roster_month_html(args.period)
        else:
            result = client.fetch_current_roster_html()

        if not client.looks_like_roster_html(result.html):
            raise SystemExit(
                "Fetched HTML does not look like a Dyflexis roster page. "
                "The session may be expired or redirected to login."
            )

        service = SyncService(
            parser=parser,
            state_store=StateStore(config.state_db_path),
            google_client=_build_google_calendar_client(config),
        )
        event_ids = service.sync_html(result.html)
        print(
            json.dumps(
                {
                    "synced_event_ids": event_ids,
                    "fetch": {
                        "source": result.source,
                        "url": result.url,
                        "fetched_at": str(result.fetched_at),
                        "cache_key": result.cache_key,
                    },
                },
                indent=2,
                default=str,
            )
        )
        return 0

    return 1


def _to_json(parsed) -> str:
    payload = {
        "navigation": asdict(parsed.navigation),
        "entries": [asdict(entry) for entry in parsed.entries],
    }
    return json.dumps(payload, indent=2, default=str)


def _build_dyflexis_client(config: AppConfig, cookie_jar_path: Path | None) -> DyflexisClient:
    has_session_config = config.session_config_path.exists()
    if cookie_jar_path is None and not has_session_config:
        raise SystemExit(
            "No local session found. Use --cookie-jar, set DYFLEXIS_COOKIE_JAR, "
            "or create .roster-sync/session.json."
        )

    session = build_session(
        cookie_jar_path=cookie_jar_path or config.cookie_jar_path,
        session_config_path=config.session_config_path,
    )
    return DyflexisClient(
        session=session,
        base_url=config.dyflexis_base_url,
        cache=PageCache(config.cache_dir),
        global_min_interval_seconds=config.global_min_interval_seconds,
        page_min_interval_seconds=config.page_min_interval_seconds,
    )


def _build_google_calendar_client(config: AppConfig):
    if not config.google_calendar_id:
        raise SystemExit(
            "No Google Calendar ID configured. Set GOOGLE_CALENDAR_ID or create "
            ".roster-sync/calendar_id.txt."
        )
    if not config.google_service_account_path.exists():
        raise SystemExit(
            "No Google service account JSON found. Set GOOGLE_SERVICE_ACCOUNT_JSON or "
            "place the file at .roster-sync/google-service-account.json."
        )

    return ServiceAccountGoogleCalendarClient(
        calendar_id=config.google_calendar_id,
        credentials_path=config.google_service_account_path,
    )
