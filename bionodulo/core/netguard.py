"""Network egress guard to mitigate SSRF.

Used by nodes/tools that fetch user-supplied URLs (HTTP request node, dataset
downloads). Resolves the target host and refuses to connect to loopback,
link-local (incl. the cloud metadata endpoint 169.254.169.254), multicast,
reserved, or — unless explicitly allowed — private addresses.

Private-network egress is allowed only when ``BIONODULO_ALLOW_PRIVATE_EGRESS``
is truthy, so internal bioinformatics resources can still be reached when the
operator opts in.
"""
from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlparse


def _private_egress_allowed() -> bool:
    return os.environ.get("BIONODULO_ALLOW_PRIVATE_EGRESS", "").strip().lower() in {"1", "true", "yes", "on"}


def _ip_is_blocked(ip: str, allow_private: bool) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    if (
        addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    ):
        return True
    if not allow_private and addr.is_private:
        return True
    return False


def assert_safe_url(url: str, *, allow_private: bool | None = None) -> None:
    """Raise ``ValueError`` if *url* resolves to a non-public address.

    Validates the URL's immediate host. (httpx-followed redirects are not
    re-validated here; callers that follow untrusted redirects should disable
    auto-redirects or re-check each hop.)
    """
    if allow_private is None:
        allow_private = _private_egress_allowed()

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Refusing non-http(s) URL: {url!r}")
    host = parsed.hostname
    if not host:
        raise ValueError(f"URL has no host: {url!r}")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        # A host that does not resolve cannot be an SSRF target — the real
        # connection would simply fail — so allow it through and let the actual
        # request surface the connection error.
        return

    for info in infos:
        ip = info[4][0]
        if _ip_is_blocked(ip, allow_private):
            raise ValueError(
                f"Refusing to connect to non-public address {ip} for host {host!r}. "
                "Set BIONODULO_ALLOW_PRIVATE_EGRESS=1 to allow private/internal hosts."
            )
