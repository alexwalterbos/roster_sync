import socket

import requests

from roster_sync.preflight import run_network_preflight


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class FakeSession:
    def __init__(self, *, response: FakeResponse | None = None, error: Exception | None = None):
        self.response = response
        self.error = error

    def get(self, *_args, **_kwargs):
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


def test_network_preflight_success(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.2.3.4", 443)),
        ],
    )
    session = FakeSession(response=FakeResponse(302))

    result = run_network_preflight(
        base_url="https://app.planning.nu/soldaatvanoranje/svo-de-musical/",
        session=session,
    )

    assert result.ok is True
    assert result.host == "app.planning.nu"
    assert result.resolved_ips == ("1.2.3.4",)
    assert result.status_code == 302
    assert result.error is None


def test_network_preflight_dns_failure(monkeypatch):
    def _raise_dns(*_args, **_kwargs):
        raise OSError("no such host")

    monkeypatch.setattr(socket, "getaddrinfo", _raise_dns)
    session = FakeSession(response=FakeResponse(200))

    result = run_network_preflight(
        base_url="https://app.planning.nu/soldaatvanoranje/svo-de-musical/",
        session=session,
    )

    assert result.ok is False
    assert "DNS lookup failed" in (result.error or "")


def test_network_preflight_http_probe_failure(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.2.3.4", 443)),
        ],
    )
    session = FakeSession(error=requests.ConnectionError("connection refused"))

    result = run_network_preflight(
        base_url="https://app.planning.nu/soldaatvanoranje/svo-de-musical/",
        session=session,
    )

    assert result.ok is False
    assert "Network probe failed" in (result.error or "")
