# -*- coding: utf-8 -*-
"""Connect OpenRouter: the PKCE sign-in against a fake OpenRouter, the
stored credential, reconnecting, refusals, and the model list."""
import base64
import hashlib
import os
from typing import Any
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from agentscope.app._router import _openrouter_oauth as flow
from agentscope.app.deps import get_current_user_id
from agentscope.app.storage import CredentialRecord
from agentscope.credential import CredentialFactory
from agentscope.model import OpenRouterChatModel
from agentscope.model._openrouter import _model as openrouter_model
from openapi_bridge_test import _free_port, _serve


class _Storage:
    def __init__(self) -> None:
        self.records: dict[str, CredentialRecord] = {}

    async def list_credentials(self, user_id: str) -> list[CredentialRecord]:
        return [r for r in self.records.values() if r.user_id == user_id]

    async def upsert_credential(self, user_id: str, credential: Any) -> str:
        data = credential.model_dump(mode="json")
        data["api_key"] = credential.api_key.get_secret_value()
        self.records[credential.id] = CredentialRecord(id=credential.id, user_id=user_id, data=data)
        return credential.id


def _openrouter() -> tuple[FastAPI, dict]:
    """OpenRouter's key exchange: a code is good once, for its challenge."""
    state: dict[str, Any] = {"codes": {}, "issued": 0}
    app = FastAPI()

    @app.post("/api/v1/auth/keys")
    async def keys(request: Request) -> JSONResponse:
        body = await request.json()
        challenge = state["codes"].pop(body.get("code"), None)
        digest = base64.urlsafe_b64encode(
            hashlib.sha256(str(body.get("code_verifier")).encode()).digest(),
        ).rstrip(b"=").decode()
        if challenge is None or challenge != digest or body.get("code_challenge_method") != "S256":
            return JSONResponse({"error": {"message": "Invalid code or code_verifier"}}, status_code=403)
        state["issued"] += 1
        return JSONResponse({"key": f"sk-or-v1-{state['issued']}"})

    return app, state


class OpenRouterConnectTest(IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        port = _free_port()
        provider, self.provider = _openrouter()
        self.server = _serve(provider, port)
        self.addCleanup(setattr, self.server, "should_exit", True)
        for patcher in (
            patch.dict(os.environ, {"PUBLIC_ORIGIN": "https://web.example", "PUBLIC_API_URL": ""}),
            patch.object(flow, "OPENROUTER_BASE_URL", f"http://127.0.0.1:{port}/api/v1"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        app = FastAPI()
        app.include_router(flow.openrouter_start_router)
        app.include_router(flow.openrouter_callback_router)
        app.state.storage = self.storage = _Storage()
        app.dependency_overrides[get_current_user_id] = lambda: "alice"
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://app")
        self.addAsyncCleanup(self.client.aclose)

    async def _sign_in(self, *, approve: bool = True) -> httpx.Response:
        started = await self.client.post("/credential/openrouter/oauth/start")
        self.assertEqual(started.status_code, 200, started.text)
        url = urlsplit(started.json()["authorize_url"])
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        self.assertEqual(f"{url.scheme}://{url.netloc}{url.path}", "https://openrouter.ai/auth")
        self.assertEqual(query["callback_url"], "https://web.example/api/openrouter-oauth/callback")
        self.assertEqual(query["code_challenge_method"], "S256")
        # The user approves on OpenRouter, which sends the browser back.
        code = f"code-{len(self.provider['codes'])}"
        self.provider["codes"][code] = query["code_challenge"]
        callback = urlsplit(query["callback_url"]).path.removeprefix("/api")
        params = {"state": query["state"], **({"code": code} if approve else {})}
        return await self.client.get(callback, params=params)

    def _landing(self, response: httpx.Response) -> dict:
        self.assertEqual(response.status_code, 302)
        landing = urlsplit(response.headers["location"])
        self.assertEqual(f"{landing.scheme}://{landing.netloc}{landing.path}", "https://web.example/credential")
        return {k: v[0] for k, v in parse_qs(landing.query).items()}

    async def test_connect_stores_the_key_as_an_openrouter_credential(self) -> None:
        self.assertEqual(self._landing(await self._sign_in())["oauth"], "ok")
        [record] = await self.storage.list_credentials("alice")
        credential = CredentialFactory.from_dict(record.data)
        self.assertEqual(record.data["type"], "openrouter_credential")
        self.assertEqual(credential.api_key.get_secret_value(), "sk-or-v1-1")
        self.assertEqual(credential.base_url, "https://openrouter.ai/api/v1")
        self.assertIs(credential.get_chat_model_class(), OpenRouterChatModel)

    async def test_reconnecting_replaces_the_key_and_keeps_the_credential(self) -> None:
        await self._sign_in()
        [first] = await self.storage.list_credentials("alice")
        await self._sign_in()
        [second] = await self.storage.list_credentials("alice")
        self.assertEqual(second.id, first.id)
        self.assertEqual(second.data["api_key"], "sk-or-v1-2")

    async def test_a_state_is_good_once(self) -> None:
        started = await self.client.post("/credential/openrouter/oauth/start")
        state = parse_qs(urlsplit(started.json()["authorize_url"]).query)["state"][0]
        flow._pending.pop(state)
        response = await self.client.get("/openrouter-oauth/callback", params={"state": state, "code": "x"})
        self.assertEqual(self._landing(response)["oauth"], "error")
        forged = await self.client.get("/openrouter-oauth/callback", params={"state": "forged", "code": "x"})
        self.assertEqual(self._landing(forged)["oauth"], "error")
        self.assertEqual(await self.storage.list_credentials("alice"), [])

    async def test_cancel_and_a_refused_code_store_nothing(self) -> None:
        self.assertEqual(self._landing(await self._sign_in(approve=False))["oauth"], "error")
        started = await self.client.post("/credential/openrouter/oauth/start")
        state = parse_qs(urlsplit(started.json()["authorize_url"]).query)["state"][0]
        refused = await self.client.get("/openrouter-oauth/callback", params={"state": state, "code": "never-issued"})
        landing = self._landing(refused)
        self.assertEqual(landing["oauth"], "error")
        self.assertIn("Invalid code", landing["message"])
        self.assertEqual(await self.storage.list_credentials("alice"), [])


class OpenRouterModelListTest(TestCase):

    def test_newest_tool_models_per_vendor_without_batch_or_expiring(self) -> None:
        def entry(model_id: str, created: int, **extra: Any) -> dict:
            return {
                "id": model_id,
                "name": model_id,
                "created": created,
                "context_length": 200000,
                "top_provider": {"max_completion_tokens": 32000},
                "architecture": {"input_modalities": ["text", "image"]},
                "supported_parameters": ["tools", "max_tokens"],
                **extra,
            }

        entries = [entry(f"qwen/q-{i}", i) for i in range(12)] + [
            entry("openai/a:batch", 99),
            entry("openai/old", 1, expiration_date="2026-11-01"),
            entry("openai/no-tools", 5, supported_parameters=["max_tokens"]),
            entry("unknown/x", 5),
            entry("openai/good", 5),
        ]
        cards = openrouter_model._pick(entries)
        names = [c.name for c in cards]
        self.assertEqual(names[0], "openai/good")
        self.assertEqual(names[1:], [f"qwen/q-{i}" for i in range(11, 3, -1)])
        self.assertEqual(cards[0].context_size, 200000)
        self.assertEqual(cards[0].output_size, 32000)
        self.assertIn("image/png", cards[0].input_types)
        self.assertNotIn("reasoning_effort", cards[0].parameter_schema["properties"])

    def test_before_the_first_fetch_a_short_list_is_shown(self) -> None:
        with patch.object(openrouter_model, "_cards", []):
            names = [c.name for c in OpenRouterChatModel.list_models()]
        self.assertIn("anthropic/claude-sonnet-5.5", names)
