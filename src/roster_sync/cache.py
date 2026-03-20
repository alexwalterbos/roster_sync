from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    query_pairs = sorted(parse_qsl(parts.query, keep_blank_values=True))
    normalized_query = urlencode(query_pairs)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, normalized_query, ""))


def cache_key_for_url(url: str) -> str:
    normalized = normalize_url(url)
    slug = _slugify(urlsplit(normalized).path.strip("/") or "root")
    if urlsplit(normalized).query:
        slug = f"{slug}_{_slugify(urlsplit(normalized).query)}"
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:10]
    return f"{slug}__{digest}"


def _slugify(value: str) -> str:
    value = value.replace("/", "_")
    value = re.sub(r"[^a-zA-Z0-9._=-]+", "-", value).strip("-")
    return value or "page"


@dataclass(slots=True)
class CachedPage:
    cache_key: str
    url: str
    html: str
    fetched_at: datetime
    page_debounce_until: datetime
    content_sha256: str
    status_code: int
    source: str


class PageCache:
    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.state_file = self.cache_dir.parent / "request-state.json"

    def get(self, url: str) -> CachedPage | None:
        cache_key = cache_key_for_url(url)
        page_dir = self.cache_dir / cache_key
        meta_path = page_dir / "meta.json"
        html_path = page_dir / "response.html"
        if not meta_path.exists() or not html_path.exists():
            return None

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return CachedPage(
            cache_key=meta["cache_key"],
            url=meta["url"],
            html=html_path.read_text(encoding="utf-8"),
            fetched_at=datetime.fromisoformat(meta["fetched_at"]),
            page_debounce_until=datetime.fromisoformat(meta["page_debounce_until"]),
            content_sha256=meta["content_sha256"],
            status_code=meta["status_code"],
            source="cache",
        )

    def set(
        self,
        *,
        url: str,
        html: str,
        status_code: int,
        page_min_interval_seconds: int,
    ) -> CachedPage:
        cache_key = cache_key_for_url(url)
        page_dir = self.cache_dir / cache_key
        page_dir.mkdir(parents=True, exist_ok=True)

        fetched_at = utc_now()
        page_debounce_until = fetched_at + timedelta(seconds=page_min_interval_seconds)
        content_sha256 = hashlib.sha256(html.encode("utf-8")).hexdigest()

        (page_dir / "response.html").write_text(html, encoding="utf-8")
        (page_dir / "meta.json").write_text(
            json.dumps(
                {
                    "cache_key": cache_key,
                    "url": normalize_url(url),
                    "fetched_at": fetched_at.isoformat(),
                    "page_debounce_until": page_debounce_until.isoformat(),
                    "content_sha256": content_sha256,
                    "status_code": status_code,
                    "source": "network",
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        return CachedPage(
            cache_key=cache_key,
            url=normalize_url(url),
            html=html,
            fetched_at=fetched_at,
            page_debounce_until=page_debounce_until,
            content_sha256=content_sha256,
            status_code=status_code,
            source="network",
        )

    def get_last_request_at(self) -> datetime | None:
        if not self.state_file.exists():
            return None
        data = json.loads(self.state_file.read_text(encoding="utf-8"))
        value = data.get("last_request_at")
        return datetime.fromisoformat(value) if value else None

    def set_last_request_at(self, value: datetime) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_request_at": value.isoformat(),
        }
        self.state_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

