from __future__ import annotations

import json
from pathlib import Path
from http.cookiejar import MozillaCookieJar

import requests


def build_session(
    cookie_jar_path: Path | None = None,
    session_config_path: Path | None = None,
) -> requests.Session:
    """Create a requests session from a local JSON session config or cookie jar."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            )
        }
    )
    if session_config_path and session_config_path.exists():
        _load_session_config(session, session_config_path)
    if cookie_jar_path and cookie_jar_path.exists():
        jar = MozillaCookieJar(str(cookie_jar_path))
        jar.load(ignore_discard=True, ignore_expires=True)
        session.cookies.update(jar)
    return session


def _load_session_config(session: requests.Session, session_config_path: Path) -> None:
    data = json.loads(session_config_path.read_text(encoding="utf-8"))
    headers = data.get("headers", {})
    if headers:
        session.headers.update(headers)

    for cookie in data.get("cookies", []):
        if not cookie.get("name"):
            continue
        session.cookies.set(
            name=cookie["name"],
            value=cookie.get("value", ""),
            domain=cookie.get("domain"),
            path=cookie.get("path", "/"),
        )
