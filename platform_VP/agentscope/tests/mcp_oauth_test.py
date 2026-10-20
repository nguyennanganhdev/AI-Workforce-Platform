# -*- coding: utf-8 -*-
"""OAuth sign-in for a remote MCP, end to end against a fake provider:
discovery from the 401, client registration, authorize with PKCE, the
callback, tool sync with the token, and refresh before an agent turn."""
import base64
import hashlib
import os
import time
from typing import Any
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from agentscope.app._router._mcp import OAUTH_NEEDED, refresh_catalog
from agentscope.app._router._mcp_oauth import oauth_callback_router, oauth_start_router
from agentscope.app._service._toolkit import _with_fresh_oauth
from agentscope.app.deps import get_current_user_id
from agentscope.app.storage import MCPRecord
from agentscope.mcp import HttpMCPConfig, MCPClient
from openapi_bridge_test import _free_port, _serve, _Storage


class _ListStorage(_Storage):
    async def list_mcps(self, user_id: str) -> list:
        return [r for r in self.records.values() if r.user_id == user_id]


def _provider(base: str, *, with_registration: bool = True) -> tuple[FastAPI, dict]:
    """An MCP that wants a bearer token, plus its authorization server."""
    state: dict[str, Any] = {"codes": {}, "tokens": {"good-1"}, "grants": [], "next": 1}
    app = FastAPI()

    @app.post("/mcp")
    async def mcp(request: Request) -> Response:
        if request.headers.get("authorization", "")[7:] not in state["tokens"]:
            return Response(
                status_code=401,
                headers={"WWW-Authenticate": f'Bearer resource_metadata="{base}/.well-known/oauth-protected-resource/mcp"'},
            )
        message = await request.json()
        if "id" not in message:
            return Response(status_code=202)
        if message["method"] == "initialize":
            result = {
                "protocolVersion": message["params"]["protocolVersion"],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake", "version": "1"},
            }
        else:
            result = {"tools": [{"name": "list_pages", "description": "Pages", "inputSchema": {"type": "object"}}]}
        return JSONResponse({"jsonrpc": "2.0", "id": message["id"], "result": result})

    @app.get("/mcp")
    async def mcp_stream() -> Response:
        return Response(status_code=405)

    @app.get("/.well-known/oauth-protected-resource/mcp")
    async def resource() -> dict:
        return {"resource": f"{base}/mcp", "authorization_servers": [base], "scopes_supported": ["read"]}

    @app.get("/.well-known/oauth-authorization-server")
    async def server() -> dict:
        meta = {
            "issuer": base,
            "authorization_endpoint": f"{base}/authorize",
            "token_endpoint": f"{base}/token",
            "code_challenge_methods_supported": ["S256"],
        }
        if with_registration:
            meta["registration_endpoint"] = f"{base}/register"
        return meta

    @app.post("/register")
    async def register(request: Request) -> dict:
        state["registered"] = await request.json()
        return {"client_id": "client-123"}

    @app.get("/authorize")
    async def authorize(request: Request) -> RedirectResponse:
        q = request.query_params
        state["authorize"] = dict(q)
        state["codes"]["code-xyz"] = q["code_challenge"]
        return RedirectResponse(f"{q['redirect_uri']}?code=code-xyz&state={q['state']}", status_code=302)

    @app.post("/token")
    async def token(
        grant_type: str = Form(),
        code: str = Form(default=""),
        code_verifier: str = Form(default=""),
        refresh_token: str = Form(default=""),
        resource: str = Form(default=""),
    ) -> JSONResponse:
        state["grants"].append({"grant_type": grant_type, "resource": resource})
        if grant_type == "authorization_code":
            expected = state["codes"].pop(code, None)
            digest = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()
            if expected != digest:
                return JSONResponse({"error": "invalid_grant"}, status_code=400)
        elif refresh_token != "refresh-1":
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        if grant_type == "refresh_token":
            state["next"] += 1
        access = f"good-{state['next']}"
        state["tokens"].add(access)
        return JSONResponse({"access_token": access, "refresh_token": "refresh-1", "expires_in": 3600})

    return app, state


class MCPOAuthFlowTest(IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        self.provider_port, self.app_port = _free_port(), _free_port()
        self.base = f"http://127.0.0.1:{self.provider_port}"
        env = patch.dict(
            os.environ,
            {
                "MCP_ALLOW_PRIVATE_URLS": "true",
                "PUBLIC_ORIGIN": "https://web.example",
                "PUBLIC_API_URL": f"http://127.0.0.1:{self.app_port}",
            },
        )
        env.start()
        self.addCleanup(env.stop)
        self.servers: list = []

    def tearDown(self) -> None:
        for server in self.servers:
            server.should_exit = True

    def _start(self, *, with_registration: bool = True) -> None:
        provider, self.provider = _provider(self.base, with_registration=with_registration)
        app = FastAPI()
        app.include_router(oauth_start_router)
        app.include_router(oauth_callback_router)
        app.state.storage = self.storage = _ListStorage()
        app.dependency_overrides[get_current_user_id] = lambda: "alice"
        self.servers += [_serve(provider, self.provider_port), _serve(app, self.app_port)]

    async def _record(self) -> MCPRecord:
        record = MCPRecord(
            user_id="alice",
            client=MCPClient(name="notes", is_stateful=False, mcp_config=HttpMCPConfig(url=f"{self.base}/mcp")),
        )
        await self.storage.upsert_mcp("alice", record)
        return record

    async def test_sign_in_sync_and_refresh(self) -> None:
        self._start()
        record = await self._record()

        # A refused sync finds the sign-in and says so.
        self.assertFalse(await refresh_catalog(record, timeout=10))
        self.assertEqual(record.last_sync_error, OAUTH_NEEDED)
        self.assertEqual(record.oauth.authorization_endpoint, f"{self.base}/authorize")
        await self.storage.upsert_mcp("alice", record)

        async with httpx.AsyncClient(timeout=30) as client:
            started = await client.post(f"http://127.0.0.1:{self.app_port}/mcp/{record.id}/oauth/start")
            self.assertEqual(started.status_code, 200, started.text)
            authorize_url = started.json()["authorize_url"]
            query = {k: v[0] for k, v in parse_qs(urlsplit(authorize_url).query).items()}
            self.assertEqual(query["client_id"], "client-123")
            self.assertEqual(query["code_challenge_method"], "S256")
            self.assertEqual(query["resource"], f"{self.base}/mcp")
            self.assertEqual(query["redirect_uri"], f"http://127.0.0.1:{self.app_port}/mcp-oauth/callback")
            self.assertEqual(self.provider["registered"]["redirect_uris"], [query["redirect_uri"]])

            # The browser: provider → our callback → back to the MCP page.
            to_callback = await client.get(authorize_url)
            back = await client.get(to_callback.headers["location"])

        self.assertEqual(back.status_code, 302)
        landing = urlsplit(back.headers["location"])
        self.assertEqual(f"{landing.scheme}://{landing.netloc}{landing.path}", "https://web.example/mcp")
        self.assertEqual(parse_qs(landing.query)["oauth"], ["ok"])

        stored = self.storage.records[record.id]
        self.assertEqual(stored.oauth.access_token, "good-1")
        self.assertEqual([t["name"] for t in stored.discovered_tools], ["list_pages"])
        self.assertIsNone(stored.last_sync_error)

        # An agent turn with a stale workspace copy gets a refreshed token.
        stored.oauth.expires_at = time.time() + 10
        await self.storage.upsert_mcp("alice", stored)
        stale = MCPClient(
            name="notes",
            is_stateful=False,
            mcp_config=HttpMCPConfig(url=f"{self.base}/mcp", headers={"Authorization": "Bearer good-1"}),
            enable_tools=["list_pages"],
        )
        [fresh] = await _with_fresh_oauth(self.storage, "alice", [stale])

        self.assertEqual(fresh.mcp_config.headers["Authorization"], "Bearer good-2")
        self.assertEqual(fresh.enable_tools, ["list_pages"])
        self.assertEqual(self.storage.records[record.id].oauth.access_token, "good-2")
        self.assertEqual(
            [g["grant_type"] for g in self.provider["grants"]],
            ["authorization_code", "refresh_token"],
        )
        self.assertTrue(all(g["resource"] == f"{self.base}/mcp" for g in self.provider["grants"]))

    async def test_unknown_state_is_refused(self) -> None:
        self._start()
        async with httpx.AsyncClient(timeout=30) as client:
            back = await client.get(f"http://127.0.0.1:{self.app_port}/mcp-oauth/callback?state=forged&code=x")
        self.assertEqual(back.status_code, 302)
        self.assertEqual(parse_qs(urlsplit(back.headers["location"]).query)["oauth"], ["error"])

    async def test_provider_without_registration_is_explained(self) -> None:
        self._start(with_registration=False)
        record = await self._record()
        async with httpx.AsyncClient(timeout=30) as client:
            started = await client.post(f"http://127.0.0.1:{self.app_port}/mcp/{record.id}/oauth/start")
        self.assertEqual(started.status_code, 422)
        self.assertIn("tự đăng ký", started.json()["detail"])
