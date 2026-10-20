# -*- coding: utf-8 -*-
"""OpenAPI import: spec reading, address guard, and the bridge end to end
(the platform's real MCP client → bridge → a partner API)."""
import asyncio
import json
import os
import socket
import threading
import time
from typing import Any
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

import uvicorn
from fastapi import FastAPI, Header, Request

from agentscope.app._router._openapi import bridge_router, openapi_router
from agentscope.app._service._openapi import (
    OpenAPIError,
    ensure_public_url,
    parse_spec,
)
from agentscope.app.deps import get_current_user_id

SPEC_V3 = {
    "openapi": "3.0.3",
    "info": {"title": "Hotel API", "description": "Rooms and bookings"},
    "servers": [{"url": "https://{env}.hotel.example/v1", "variables": {"env": {"default": "api"}}}],
    "paths": {
        "/rooms/{roomId}": {
            "parameters": [{"name": "roomId", "in": "path", "schema": {"type": "string"}}],
            "get": {
                "operationId": "getRoom",
                "summary": "One room",
                "parameters": [
                    {"name": "lang", "in": "query", "schema": {"type": "string"}},
                    {"name": "X-Trace", "in": "header", "schema": {"type": "string"}},
                ],
            },
        },
        "/bookings": {
            "post": {
                "operationId": "create booking!",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Booking"}}},
                },
            },
            "put": {
                "requestBody": {"content": {"multipart/form-data": {"schema": {"type": "object"}}}},
            },
        },
    },
    "components": {
        "schemas": {
            "Booking": {
                "type": "object",
                "properties": {"guest": {"type": "string"}, "next": {"$ref": "#/components/schemas/Booking"}},
            },
        },
    },
}


class ParseSpecTest(TestCase):
    """Reading a spec into tools."""

    def test_openapi3_operations_become_tools(self) -> None:
        parsed = parse_spec(SPEC_V3)

        self.assertEqual(parsed["base_urls"], ["https://api.hotel.example/v1"])
        ops = {op.name: op for op in parsed["operations"]}
        self.assertEqual(set(ops), {"getRoom", "create_booking"})
        room = ops["getRoom"]
        self.assertEqual(room.method, "GET")
        self.assertEqual(room.input_schema["required"], ["roomId"])
        self.assertEqual(
            {(p["in"], p["arg"]) for p in room.params},
            {("path", "roomId"), ("query", "lang"), ("header", "X-Trace")},
        )
        booking = ops["create_booking"]
        self.assertEqual(booking.body, "json")
        self.assertEqual(booking.input_schema["required"], ["body"])
        body = booking.input_schema["properties"]["body"]
        self.assertEqual(body["properties"]["guest"], {"type": "string"})
        # A self-reference is cut, not followed forever.
        self.assertEqual(body["properties"]["next"], {"type": "object"})
        self.assertEqual(parsed["skipped"], ["PUT /bookings (body multipart/form-data)"])

    def test_swagger2_body_form_and_host(self) -> None:
        spec = {
            "swagger": "2.0",
            "info": {"title": "Old"},
            "host": "old.example",
            "basePath": "/api",
            "schemes": ["https"],
            "paths": {
                "/pets": {
                    "post": {"parameters": [{"in": "body", "name": "pet", "required": True, "schema": {"type": "object"}}]},
                    "put": {"parameters": [{"in": "formData", "name": "name", "type": "string"}]},
                },
            },
        }
        parsed = parse_spec(spec)

        self.assertEqual(parsed["base_urls"], ["https://old.example/api"])
        ops = {op.method: op for op in parsed["operations"]}
        self.assertEqual(ops["POST"].body, "json")
        self.assertEqual(ops["PUT"].body, "form")
        self.assertEqual(ops["POST"].name, "post_pets")

    def test_other_documents_are_refused(self) -> None:
        with self.assertRaises(OpenAPIError):
            parse_spec({"asyncapi": "2.0"})


class AddressGuardTest(IsolatedAsyncioTestCase):
    """The bridge only reaches public addresses."""

    async def test_private_and_loopback_are_refused(self) -> None:
        with patch.dict(os.environ, {"MCP_ALLOW_PRIVATE_URLS": ""}):
            for url in ("http://127.0.0.1/x", "http://10.1.2.3/x", "http://localhost/x", "file:///etc/passwd"):
                with self.subTest(url=url), self.assertRaises(OpenAPIError):
                    await ensure_public_url(url)

    async def test_opt_in_allows_private(self) -> None:
        with patch.dict(os.environ, {"MCP_ALLOW_PRIVATE_URLS": "true"}):
            await ensure_public_url("http://127.0.0.1:9/x")


# ── end to end ───────────────────────────────────────────────────────


class _Storage:
    """The two calls the import and the bridge make."""

    def __init__(self) -> None:
        self.records: dict[str, Any] = {}

    async def get_mcp(self, user_id: str, mcp_id: str) -> Any:
        record = self.records.get(mcp_id)
        return record if record is not None and record.user_id == user_id else None

    async def upsert_mcp(self, user_id: str, record: Any) -> str:
        if any(r.name == record.name and r.id != record.id for r in self.records.values()):
            raise ValueError("taken")
        self.records[record.id] = record.model_copy(deep=True)
        return record.id


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _serve(app: FastAPI, port: int) -> uvicorn.Server:
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            return server
        time.sleep(0.05)
    raise RuntimeError("server did not start")


class BridgeEndToEndTest(IsolatedAsyncioTestCase):
    """Import a spec and call its tool the way an agent run does."""

    def setUp(self) -> None:
        partner = FastAPI()
        self.seen: list[dict] = []

        @partner.get("/v1/rooms/{room_id}")
        async def room(room_id: str, lang: str = "", x_api_key: str = Header(default="")) -> dict:
            self.seen.append({"room": room_id, "lang": lang, "key": x_api_key})
            return {"room": room_id, "lang": lang, "free": True}

        @partner.post("/v1/bookings")
        async def book(request: Request) -> Any:
            return {"booked": (await request.json())["guest"]}

        self.partner_port, self.app_port = _free_port(), _free_port()
        spec = json.loads(json.dumps(SPEC_V3))
        spec["servers"] = [{"url": f"http://127.0.0.1:{self.partner_port}/v1"}]
        self.spec = spec

        app = FastAPI()
        app.include_router(openapi_router)
        app.include_router(bridge_router)
        app.state.storage = self.storage = _Storage()
        app.dependency_overrides[get_current_user_id] = lambda: "alice"

        env = patch.dict(
            os.environ,
            {
                "MCP_ALLOW_PRIVATE_URLS": "true",
                "MCP_BRIDGE_BASE_URL": f"http://127.0.0.1:{self.app_port}",
            },
        )
        env.start()
        self.addCleanup(env.stop)
        self.servers = [_serve(partner, self.partner_port), _serve(app, self.app_port)]

    def tearDown(self) -> None:
        for server in self.servers:
            server.should_exit = True

    async def _post(self, path: str, body: dict) -> Any:
        import httpx

        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{self.app_port}", timeout=60) as client:
            return await client.post(path, json=body)

    async def test_import_then_call_like_an_agent(self) -> None:
        preview = await self._post("/mcp/openapi/preview", {"spec_text": json.dumps(self.spec)})
        self.assertEqual(preview.status_code, 200)
        self.assertEqual([op["name"] for op in preview.json()["operations"]], ["getRoom", "create_booking"])

        created = await self._post(
            "/mcp/openapi",
            {
                "name": "hotel",
                "spec_text": json.dumps(self.spec),
                "base_url": f"http://127.0.0.1:{self.partner_port}/v1",
                "operations": ["getRoom", "create_booking"],
                "auth_type": "header",
                "auth_name": "X-Api-Key",
                "auth_value": "partner-secret",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        view = created.json()
        # The sync on import went through the real MCP client and bridge.
        self.assertIsNone(view["last_sync_error"])
        self.assertEqual({tool["name"] for tool in view["tools"]}, {"getRoom", "create_booking"})
        self.assertNotIn("partner-secret", created.text)

        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        record = self.storage.records[view["id"]]
        config = record.client.mcp_config
        async with streamablehttp_client(config.url, headers=config.headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("getRoom", {"roomId": "A 1", "lang": "vi"})
                booked = await session.call_tool("create_booking", {"body": {"guest": "Lan"}})

        self.assertFalse(result.isError)
        self.assertIn('"free":true', result.content[0].text)
        self.assertEqual(self.seen, [{"room": "A 1", "lang": "vi", "key": "partner-secret"}])
        self.assertIn('"booked":"Lan"', booked.content[0].text)

    async def test_bridge_refuses_a_wrong_token(self) -> None:
        import httpx

        created = await self._post(
            "/mcp/openapi",
            {
                "name": "hotel",
                "spec_text": json.dumps(self.spec),
                "base_url": f"http://127.0.0.1:{self.partner_port}/v1",
                "operations": ["getRoom"],
            },
        )
        mcp_id = created.json()["id"]
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"http://127.0.0.1:{self.app_port}/mcp-bridge/openapi/alice/{mcp_id}",
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                headers={"X-AWP-Bridge-Token": "guess"},
            )
        self.assertEqual(response.status_code, 404)
