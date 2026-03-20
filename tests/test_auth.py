from pathlib import Path

from roster_sync.auth import build_session


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
