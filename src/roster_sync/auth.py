from __future__ import annotations

import json
from pathlib import Path
from http.cookiejar import MozillaCookieJar
import re
from urllib.parse import urlsplit, urlunsplit

import requests

CSRF_TOKEN_PATTERN = re.compile(
    r'<meta\s+name="authentication-csrf-token"\s+content="([^"]+)"',
    re.IGNORECASE,
)


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


def load_credentials(credentials_config_path: Path) -> dict[str, object]:
    data = json.loads(credentials_config_path.read_text(encoding="utf-8"))
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        raise ValueError("Dyflexis credentials file must contain username and password.")
    return {
        "username": username,
        "password": password,
        "authenticatorCode": data.get("authenticatorCode", ""),
        "rememberDevice": bool(data.get("rememberDevice", False)),
    }


def persist_session_config(session: requests.Session, session_config_path: Path) -> None:
    session_config_path.parent.mkdir(parents=True, exist_ok=True)
    cookies: list[dict[str, str]] = []
    for cookie in session.cookies:
        cookies.append(
            {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path,
            }
        )

    payload = {
        "headers": {
            "User-Agent": session.headers.get("User-Agent"),
            "Accept-Language": session.headers.get("Accept-Language"),
        },
        "cookies": cookies,
    }
    session_config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def refresh_dyflexis_session(
    *,
    session: requests.Session,
    base_url: str,
    credentials_config_path: Path,
    session_config_path: Path | None = None,
) -> bool:
    if not credentials_config_path.exists():
        return False

    credentials = load_credentials(credentials_config_path)
    _clear_cookie_name(session, name="PHPSESSID", domain=urlsplit(base_url).netloc)
    login_url = _system_base_url(base_url) + "login"
    login_page = session.get(login_url, timeout=30)
    login_page.raise_for_status()

    csrf_token = _extract_csrf_token(login_page.text)
    if not csrf_token:
        raise ValueError("Could not find Dyflexis authentication CSRF token on the login page.")

    response = session.post(
        _system_base_url(base_url) + "login/authenticate",
        json=credentials,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": _origin_from_url(base_url),
            "Referer": login_url,
            "X-Authentication-CSRF-Token": csrf_token,
        },
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    if not data.get("url"):
        return False

    if session_config_path is not None:
        persist_session_config(session, session_config_path)
    return True


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


def _system_base_url(base_url: str) -> str:
    parts = urlsplit(base_url)
    segments = [segment for segment in parts.path.split("/") if segment]
    if not segments:
        raise ValueError(f"Cannot derive Dyflexis system base URL from {base_url!r}")
    system_path = "/" + segments[0] + "/"
    return urlunsplit((parts.scheme, parts.netloc, system_path, "", ""))


def _origin_from_url(base_url: str) -> str:
    parts = urlsplit(base_url)
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


def _extract_csrf_token(html: str) -> str | None:
    match = CSRF_TOKEN_PATTERN.search(html)
    return match.group(1) if match else None


def _clear_cookie_name(session: requests.Session, *, name: str, domain: str) -> None:
    for cookie in list(session.cookies):
        if cookie.name != name:
            continue
        if cookie.domain.lstrip(".") != domain:
            continue
        session.cookies.clear(domain=cookie.domain, path=cookie.path, name=cookie.name)
