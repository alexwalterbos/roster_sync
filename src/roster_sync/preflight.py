from __future__ import annotations

import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import requests


@dataclass(slots=True)
class NetworkPreflightResult:
    ok: bool
    host: str
    probe_url: str
    resolved_ips: tuple[str, ...]
    status_code: int | None = None
    error: str | None = None


def run_network_preflight(
    *,
    base_url: str,
    session: requests.Session,
    timeout_seconds: float = 10.0,
) -> NetworkPreflightResult:
    parsed = urlparse(base_url)
    host = parsed.hostname or ""
    if not host:
        return NetworkPreflightResult(
            ok=False,
            host="",
            probe_url=base_url,
            resolved_ips=tuple(),
            error="Could not parse hostname from Dyflexis base URL.",
        )

    probe_url = f"{base_url.rstrip('/')}/rooster2/index2"
    try:
        addr_infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        return NetworkPreflightResult(
            ok=False,
            host=host,
            probe_url=probe_url,
            resolved_ips=tuple(),
            error=f"DNS lookup failed for {host}: {exc}",
        )

    resolved_ips = tuple(sorted({info[4][0] for info in addr_infos}))
    try:
        response = session.get(probe_url, timeout=timeout_seconds, allow_redirects=False)
    except requests.RequestException as exc:
        return NetworkPreflightResult(
            ok=False,
            host=host,
            probe_url=probe_url,
            resolved_ips=resolved_ips,
            error=f"Network probe failed for {probe_url}: {exc}",
        )

    return NetworkPreflightResult(
        ok=True,
        host=host,
        probe_url=probe_url,
        resolved_ips=resolved_ips,
        status_code=response.status_code,
        error=None,
    )
