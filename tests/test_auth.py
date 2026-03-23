from pathlib import Path

from roster_sync.auth import (
    _clear_cookie_name,
    _extract_csrf_token,
    build_session,
    load_credentials,
    persist_session_config,
)


def test_build_session_loads_local_session_config(tmp_path: Path):
    session_file = tmp_path / "session.json"
    session_file.write_text(
        """
        {
          "headers": {
            "User-Agent": "TestAgent/1.0",
            "Accept-Language": "nl-NL"
          },
          "cookies": [
            {
              "name": "PHPSESSID",
              "value": "abc123",
              "domain": "example.invalid",
              "path": "/"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    session = build_session(session_config_path=session_file)

    assert session.headers["User-Agent"] == "TestAgent/1.0"
    assert session.headers["Accept-Language"] == "nl-NL"
    assert session.cookies.get("PHPSESSID") == "abc123"


def test_load_credentials_requires_username_and_password(tmp_path: Path):
    credentials_file = tmp_path / "creds.json"
    credentials_file.write_text(
        '{"username":"user@example.com","password":"secret"}',
        encoding="utf-8",
    )

    credentials = load_credentials(credentials_file)

    assert credentials["username"] == "user@example.com"
    assert credentials["password"] == "secret"
    assert credentials["authenticatorCode"] == ""
    assert credentials["rememberDevice"] is False


def test_persist_session_config_writes_headers_and_cookies(tmp_path: Path):
    session_file = tmp_path / "session.json"
    session = build_session()
    session.headers["Accept-Language"] = "en-US"
    session.cookies.set("PHPSESSID", "fresh", domain="example.invalid", path="/")

    persist_session_config(session, session_file)

    content = session_file.read_text(encoding="utf-8")
    assert '"PHPSESSID"' in content
    assert '"fresh"' in content
    assert '"Accept-Language": "en-US"' in content


def test_extract_csrf_token_reads_meta_tag():
    html = '<meta name="authentication-csrf-token" content="csrf-token-123">'

    assert _extract_csrf_token(html) == "csrf-token-123"


def test_clear_cookie_name_removes_matching_domain_cookies_only():
    session = build_session()
    session.cookies.set("PHPSESSID", "root", domain="example.invalid", path="/")
    session.cookies.set(
        "PHPSESSID", "scoped", domain="example.invalid", path="/example-customer/"
    )
    session.cookies.set("other", "keep", domain="example.invalid", path="/")
    session.cookies.set("PHPSESSID", "elsewhere", domain="other.invalid", path="/")

    _clear_cookie_name(session, name="PHPSESSID", domain="example.invalid")

    remaining = {
        (cookie.name, cookie.domain, cookie.path, cookie.value) for cookie in session.cookies
    }
    assert ("other", "example.invalid", "/", "keep") in remaining
    assert ("PHPSESSID", "other.invalid", "/", "elsewhere") in remaining
    assert ("PHPSESSID", "example.invalid", "/", "root") not in remaining
    assert ("PHPSESSID", "example.invalid", "/example-customer/", "scoped") not in remaining
