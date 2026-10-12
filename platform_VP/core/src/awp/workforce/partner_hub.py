"""The MCP clients of the routes, one per (route, server), each with its own tool-list cache.

A client is rebuilt when the route's server row changes (url, sealed headers, timeout), so a changed
address or key takes effect at once and an old tool list is never served for a new server. The sealed
headers are opened here and nowhere else.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select

from . import tables as t
from .crypto import SecretKeyMissing
from .partner_mcp import PartnerListError, PartnerMCP

log = logging.getLogger("awp.workforce")


class McpHub:
    def __init__(self, db: Any, sealer: Any, settings: Any) -> None:
        self.db, self.sealer, self.settings = db, sealer, settings
        self._clients: dict[tuple[str, str], tuple[tuple, PartnerMCP]] = {}

    def client(self, route_id: str, server: Any) -> PartnerMCP:
        """The client for a `wf_mcp_servers` row; raises PartnerListError when its headers cannot be opened."""
        key = (route_id, server["name"])
        fingerprint = (server["url"], server["transport"], server["headers_enc"], server["timeout"])
        held = self._clients.get(key)
        if held is not None and held[0] == fingerprint:
            return held[1]
        headers: dict[str, str] = {}
        if server["headers_enc"]:
            try:
                headers = json.loads(self.sealer.open(server["headers_enc"]))
            except (SecretKeyMissing, ValueError):
                log.error("the headers of server %s of route %s cannot be opened", server["name"], route_id)
                raise PartnerListError("the server's headers cannot be opened")
        s = self.settings
        made = PartnerMCP(server["url"], headers, allow_private=s.mcp_allow_private,
                          connect_timeout=min(max(float(server["timeout"]), 1.0), 10.0),
                          max_bytes=s.mcp_max_response_bytes, list_ttl=s.mcp_list_ttl_seconds)
        self._clients[key] = (fingerprint, made)
        return made

    async def servers(self, route_id: str) -> dict[str, Any]:
        async with self.db.engine.connect() as conn:
            rows = (await conn.execute(select(t.mcp_servers).where(t.mcp_servers.c.route_id == route_id))).mappings().all()
        return {r["name"]: dict(r) for r in rows}

    def forget(self, route_id: str) -> None:
        for key in [k for k in self._clients if k[0] == route_id]:
            del self._clients[key]
