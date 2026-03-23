from datetime import datetime, timedelta, timezone
from pathlib import Path

from roster_sync.cache import PageCache
from roster_sync.dyflexis_client import DyflexisClient


class DummyResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None


class DummySession:
    def __init__(self, responses: list[DummyResponse]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str, timeout: int = 30):
        self.calls.append(url)
        return self.responses.pop(0)


ROSTER_HTML = '<div id="rooster"></div><table class="calender"></table>'


def test_returns_cached_page_when_page_debounce_is_active(tmp_path: Path):
    cache = PageCache(tmp_path / "cache")
    url = "https://example.invalid/example-customer/example-location/rooster2/index2?periode=2026-03"
    cache.set(url=url, html=ROSTER_HTML, status_code=200, page_min_interval_seconds=900)

    session = DummySession([DummyResponse("should-not-be-used")])
    client = DyflexisClient(
        session=session,
        base_url="https://example.invalid/example-customer/example-location/",
        cache=cache,
    )

    result = client.fetch_roster_month_html("2026-03")

    assert result.source == "cache"
    assert result.html == ROSTER_HTML
    assert session.calls == []


def test_returns_stale_cache_when_global_debounce_blocks_network(tmp_path: Path):
    cache = PageCache(tmp_path / "cache")
    url = "https://example.invalid/example-customer/example-location/rooster2/index2?periode=2026-03"
    cached = cache.set(url=url, html=ROSTER_HTML, status_code=200, page_min_interval_seconds=1)

    expired_meta = {
        "cache_key": cached.cache_key,
        "url": cached.url,
        "fetched_at": cached.fetched_at.isoformat(),
        "page_debounce_until": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
        "content_sha256": cached.content_sha256,
        "status_code": cached.status_code,
        "source": "network",
    }
    meta_path = (tmp_path / "cache" / cached.cache_key / "meta.json")
    meta_path.write_text(__import__("json").dumps(expired_meta, indent=2), encoding="utf-8")
    cache.set_last_request_at(datetime.now(timezone.utc))

    session = DummySession([DummyResponse("should-not-be-used")])
    client = DyflexisClient(
        session=session,
        base_url="https://example.invalid/example-customer/example-location/",
        cache=cache,
        global_min_interval_seconds=60,
        page_min_interval_seconds=1,
    )

    result = client.fetch_roster_month_html("2026-03")

    assert result.source == "stale-cache"
    assert result.html == ROSTER_HTML
    assert session.calls == []


def test_fetches_and_caches_when_no_cache_exists(tmp_path: Path):
    cache = PageCache(tmp_path / "cache")
    session = DummySession([DummyResponse(ROSTER_HTML)])
    client = DyflexisClient(
        session=session,
        base_url="https://example.invalid/example-customer/example-location/",
        cache=cache,
    )

    result = client.fetch_roster_month_html("2026-03")

    assert result.source == "network"
    assert len(session.calls) == 1
    assert cache.get(result.url) is not None


def test_reauthenticates_and_retries_when_first_response_is_login_page(tmp_path: Path):
    cache = PageCache(tmp_path / "cache")
    session = DummySession(
        [
            DummyResponse("<html><body><form id='login'></form></body></html>"),
            DummyResponse(ROSTER_HTML),
        ]
    )
    calls = {"reauth": 0}
    client = DyflexisClient(
        session=session,
        base_url="https://example.invalid/example-customer/example-location/",
        cache=cache,
        reauthenticate=lambda: calls.__setitem__("reauth", calls["reauth"] + 1) or True,
    )

    result = client.fetch_current_roster_html()

    assert result.source == "network"
    assert result.html == ROSTER_HTML
    assert calls["reauth"] == 1
    assert len(session.calls) == 2
