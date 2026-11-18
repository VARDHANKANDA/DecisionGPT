"""Who is the caller? The address used to rate-limit and to attribute security events.

``X-Forwarded-For`` is written by whoever sent the request, so it is believed ONLY when the TCP peer is a proxy the operator listed in
``TRUSTED_PROXIES``. The header is then read from the right: each hop that is itself a trusted proxy is skipped and the first address that
is not one is the client. Everything to its left was supplied by the client or by earlier hops and is ignored, so a forged
``X-Forwarded-For: 1.2.3.4`` cannot choose the bucket. With no trusted proxies configured the header is never read.

IPv6 callers are grouped by /64: a single subscriber commonly controls a whole /64, so per-address buckets would be free to rotate.
"""
from __future__ import annotations

import ipaddress
from functools import lru_cache

from starlette.requests import Request

from app.core.config import get_settings


@lru_cache(maxsize=16)
def _networks(spec: str) -> tuple:
    nets = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            nets.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            continue                       # a malformed entry trusts nothing rather than everything
    return tuple(nets)


def _parse(value: str):
    try:
        return ipaddress.ip_address(value.strip().strip("[]"))
    except ValueError:
        return None


def _in(addr, nets) -> bool:
    return any(addr.version == n.version and addr in n for n in nets)


def _label(addr, raw: str) -> str:
    if addr is None:
        return raw[:64] or "unknown"       # a non-IP peer (e.g. an in-process test client) is used as is
    if addr.version == 6:
        return str(ipaddress.ip_network(f"{addr}/64", strict=False))
    return str(addr)


def client_address(request: Request) -> str:
    peer_raw = request.client.host if request.client else ""
    peer = _parse(peer_raw)
    trusted = _networks(get_settings().trusted_proxies)
    if peer is None or not trusted or not _in(peer, trusted):
        return _label(peer, peer_raw)
    hops = [h.strip() for line in request.headers.getlist("x-forwarded-for") for h in line.split(",") if h.strip()]
    for hop in reversed(hops):
        addr = _parse(hop)
        if addr is not None and _in(addr, trusted):
            continue
        return _label(addr, hop)           # the nearest hop that is not one of our proxies (malformed text is kept, hashed later)
    return _label(peer, peer_raw)
