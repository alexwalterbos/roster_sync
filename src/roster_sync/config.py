from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from zoneinfo import ZoneInfo


DEFAULT_BASE_URL = "https://example.invalid/example-customer/example-location/"
LOCAL_BASE_URL_PATH = Path(".roster-sync/dyflexis_base_url.txt")


@dataclass(slots=True)
class AppConfig:
    dyflexis_base_url: str = field(
        default_factory=lambda: os.getenv("DYFLEXIS_BASE_URL")
        or _read_text_if_exists(LOCAL_BASE_URL_PATH)
        or _infer_base_url_from_cache(Path(".roster-sync/cache"))
        or DEFAULT_BASE_URL
    )
    timezone_name: str = field(
        default_factory=lambda: os.getenv("ROSTER_TIMEZONE", "Europe/Amsterdam")
    )
    state_db_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("ROSTER_STATE_DB", ".roster-sync/state.sqlite3")
        )
    )
    cache_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("DYFLEXIS_CACHE_DIR", ".roster-sync/cache")
        )
    )
    global_min_interval_seconds: int = field(
        default_factory=lambda: int(
            os.getenv("DYFLEXIS_GLOBAL_MIN_INTERVAL_SECONDS", "15")
        )
    )
    page_min_interval_seconds: int = field(
        default_factory=lambda: int(
            os.getenv("DYFLEXIS_PAGE_MIN_INTERVAL_SECONDS", "900")
        )
    )
    google_calendar_id: str | None = field(
        default_factory=lambda: os.getenv("GOOGLE_CALENDAR_ID")
        or _read_text_if_exists(Path(".roster-sync/calendar_id.txt"))
    )
    google_service_account_path: Path = field(
        default_factory=lambda: Path(
            os.getenv(
                "GOOGLE_SERVICE_ACCOUNT_JSON",
                ".roster-sync/google-service-account.json",
            )
        )
    )
    session_config_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("DYFLEXIS_SESSION_CONFIG", ".roster-sync/session.json")
        )
    )
    credentials_config_path: Path = field(
        default_factory=lambda: Path(
            os.getenv(
                "DYFLEXIS_CREDENTIALS_CONFIG",
                ".roster-sync/dyflexis_credentials.json",
            )
        )
    )
    cookie_jar_path: Path | None = field(
        default_factory=lambda: _optional_path(os.getenv("DYFLEXIS_COOKIE_JAR"))
    )

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)


def _optional_path(value: str | None) -> Path | None:
    if not value:
        return None
    return Path(value)


def _read_text_if_exists(path: Path) -> str | None:
    if not path.exists():
        return None
    value = path.read_text(encoding="utf-8").strip()
    return value or None


def _infer_base_url_from_cache(cache_dir: Path) -> str | None:
    if not cache_dir.exists():
        return None

    for meta_path in sorted(cache_dir.glob("*/meta.json")):
        meta_text = _read_text_if_exists(meta_path)
        if not meta_text:
            continue
        try:
            import json

            url = json.loads(meta_text).get("url")
        except Exception:
            continue
        if not url:
            continue
        if "/rooster2/index2" not in url:
            continue

        prefix = url.split("/rooster2/index2", 1)[0]
        return prefix.rstrip("/") + "/"

    return None
