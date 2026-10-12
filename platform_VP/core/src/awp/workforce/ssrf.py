"""Where a route's MCP server may be: not on the platform's own network (SSRF).

A URL is checked when it is written (admin), and at every connection: the name is looked up ONCE there, every
address must be a public one, and the connection goes to the address that was checked (`pin`), so a name whose
DNS answers differently the second time cannot lead inward. Redirects are not followed off the server's origin
(the SDK refuses them), so a public server cannot bounce a call inward.

What is allowed is what is globally routable. The shared range 100.64.0.0/10 (carrier NAT, some clouds' metadata
service, overlay networks) and the IPv4 addresses embedded in IPv4-mapped, 6to4 and NAT64 IPv6 are judged by the
IPv4 address they carry.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

INTERNAL_SUFFIXES = (".local", ".internal", ".localhost", ".lan", ".home", ".corp")
RESOLVE_TIMEOUT = 3.0
NAT64 = ipaddress.ip_network("64:ff9b::/96")
NOT_PUBLIC = "the host name does not resolve to a public address"  # the same words whether it does not resolve or resolves inward


class Blocked(ValueError):
    """The address is not one a partner tool may call. The message is safe to show the admin."""


def _unwrap(ip: ipaddress._BaseAddress) -> ipaddress._BaseAddress:
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return ip.ipv4_mapped
        if ip.sixtofour is not None:
            return ip.sixtofour
        if ip in NAT64:
            return ipaddress.IPv4Address(ip.packed[-4:])
    return ip


def _private(ip: ipaddress._BaseAddress) -> bool:
    ip = _unwrap(ip)
    return (not ip.is_global or ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
            or ip.is_multicast or ip.is_unspecified)


def shape(url: str) -> str:
    """The host of an http(s) URL without credentials; raises when the URL is not one a tool may use."""
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise Blocked("the URL must be an http(s) URL with a host")
    if parts.username or parts.password:
        raise Blocked("the URL must not carry credentials; use headers")
    try:
        parts.port
    except ValueError:
        raise Blocked("the URL has an invalid port")
    return parts.hostname.lower()


async def pin(host: str, allow_private: bool) -> str | None:
    """Check `host` and return the address to connect to (None: connect as is, nothing to pin). The caller must use
    this address and not look the name up again."""
    if allow_private:
        return None
    if host == "localhost" or host.endswith(INTERNAL_SUFFIXES):
        raise Blocked("the URL points at an internal host")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if _private(literal):
            raise Blocked("the URL points at an internal address")
        return None
    try:
        found = await asyncio.wait_for(asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM),
                                       RESOLVE_TIMEOUT)
    except (OSError, TimeoutError):
        raise Blocked(NOT_PUBLIC)
    ips = [ipaddress.ip_address(sockaddr[0].split("%")[0]) for *_, sockaddr in found]
    if not ips or any(_private(ip) for ip in ips):
        raise Blocked(NOT_PUBLIC)
    return str(min(ips, key=lambda ip: ip.version))  # IPv4 first


async def check_host(host: str, allow_private: bool) -> None:
    await pin(host, allow_private)


async def check_url(url: str, allow_private: bool) -> None:
    await check_host(shape(url), allow_private)
