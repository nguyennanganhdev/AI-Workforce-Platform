"""Endpoints a customer types in must be public internet hosts.

The server makes the request, so a provider ``base_url``/``host`` or an MCP
URL pointing at loopback, the private network, link-local (cloud metadata)
or the compose network would let any account probe the platform's inside.
"""

import asyncio
import ipaddress
from urllib.parse import urlsplit

from ._contracts import PlatformError

# Credential fields that name the host the server connects to.
ENDPOINT_FIELDS = ("base_url", "host", "api_host")


async def assert_public_endpoint(value: str) -> None:
    parts = urlsplit(value if "://" in value else "https://" + value)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise PlatformError("ENDPOINT_NOT_ALLOWED", 422)
    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
        infos = await asyncio.get_running_loop().getaddrinfo(parts.hostname, port)
    except (OSError, ValueError) as exc:
        raise PlatformError("ENDPOINT_UNRESOLVABLE", 422) from exc
    for *_, sockaddr in infos:
        address = ipaddress.ip_address(str(sockaddr[0]).split("%", 1)[0])
        if not address.is_global or address.is_multicast:
            raise PlatformError("ENDPOINT_NOT_ALLOWED", 422)


async def assert_public_credential(data: dict) -> None:
    for field in ENDPOINT_FIELDS:
        value = data.get(field)
        if isinstance(value, str) and value.strip():
            await assert_public_endpoint(value.strip())
