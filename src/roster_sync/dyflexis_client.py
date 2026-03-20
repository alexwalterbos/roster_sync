from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin

import requests

from .cache import PageCache, utc_now
from .rate_limit import check_global_debounce, is_page_fetch_allowed, wait_for_global_debounce


@dataclass(slots=True)
class FetchResult:
    html: str
    url: str
    source: str
    fetched_at: datetime
    cache_key: str | None = None
    content_sha256: str | None = None
    status_code: int | None = None


class DyflexisClient:
    def __init__(
        self,
        session: requests.Session,
        base_url: str,
        cache: PageCache | None = None,
        global_min_interval_seconds: int = 15,
        page_min_interval_seconds: int = 900,
    ) -> None:
        self.session = session
        self.base_url = base_url.rstrip("/") + "/"
        self.cache = cache
        self.global_min_interval_seconds = global_min_interval_seconds
        self.page_min_interval_seconds = page_min_interval_seconds

    def fetch_roster_month_html(self, period: str) -> FetchResult:
        url = requests.Request(
            "GET",
            urljoin(self.base_url, "rooster2/index2"),
            params={"periode": period},
        ).prepare().url
        assert url is not None
        return self._fetch_with_cache(url)

    def fetch_current_roster_html(self) -> FetchResult:
        url = urljoin(self.base_url, "rooster2/index2")
        return self._fetch_with_cache(url)

    @staticmethod
    def looks_like_roster_html(html: str) -> bool:
        return 'table class="calender"' in html and 'id="rooster"' in html

    def _fetch_with_cache(self, url: str) -> FetchResult:
        now = utc_now()
        cached_page = self.cache.get(url) if self.cache else None

        if cached_page and not is_page_fetch_allowed(cached_page.page_debounce_until, now):
            return FetchResult(
                html=cached_page.html,
                url=cached_page.url,
                source="cache",
                fetched_at=cached_page.fetched_at,
                cache_key=cached_page.cache_key,
                content_sha256=cached_page.content_sha256,
                status_code=cached_page.status_code,
            )

        if self.cache:
            decision = check_global_debounce(
                self.cache.get_last_request_at(),
                now,
                self.global_min_interval_seconds,
            )
            if not decision.allowed_now:
                if cached_page is not None:
                    return FetchResult(
                        html=cached_page.html,
                        url=cached_page.url,
                        source="stale-cache",
                        fetched_at=cached_page.fetched_at,
                        cache_key=cached_page.cache_key,
                        content_sha256=cached_page.content_sha256,
                        status_code=cached_page.status_code,
                    )
                wait_for_global_debounce(decision.wait_seconds)

        response = self.session.get(url, timeout=30)
        response.raise_for_status()

        fetched_at = utc_now()
        if self.cache:
            stored = self.cache.set(
                url=url,
                html=response.text,
                status_code=response.status_code,
                page_min_interval_seconds=self.page_min_interval_seconds,
            )
            self.cache.set_last_request_at(fetched_at)
            return FetchResult(
                html=stored.html,
                url=stored.url,
                source=stored.source,
                fetched_at=stored.fetched_at,
                cache_key=stored.cache_key,
                content_sha256=stored.content_sha256,
                status_code=stored.status_code,
            )

        return FetchResult(
            html=response.text,
            url=url,
            source="network",
            fetched_at=fetched_at,
            status_code=response.status_code,
        )
