# -*- coding: utf-8 -*-
"""Connect an OpenRouter account in one click (OpenRouter's OAuth PKCE).

``POST /credential/openrouter/oauth/start`` (signed-in user) returns the
OpenRouter sign-in URL. After the user approves, OpenRouter sends the
browser to ``GET /openrouter-oauth/callback?code=…&state=…``; the
one-time ``state`` says whose sign-in it is. The callback trades the code
for a key that belongs to the user's own OpenRouter account (billed to
their credits), stores it as their OpenRouter credential — replacing the
key of one they connected before, so agents using it keep working — and
sends the browser back to the credential page. Pending sign-ins live in
this process (one app worker), like the MCP sign-in.
"""
import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from pydantic import SecretStr

from ..deps import get_current_user_id, get_storage
from ..storage import StorageBase
from ...credential import CredentialFactory, OpenRouterCredential
from ...credential._openrouter import OPENROUTER_BASE_URL
from ..._logging import logger
from ._mcp_oauth import _web_origin, redirect_uri as _mcp_redirect_uri

openrouter_start_router = APIRouter(prefix="/credential", tags=["credential"])
openrouter_callback_router = APIRouter(prefix="/openrouter-oauth", tags=["credential"])

AUTHORIZE_URL = "https://openrouter.ai/auth"
# OpenRouter's codes live ten minutes; a little slack for the round trip.
_PENDING_TTL = 15 * 60
_pending: dict[str, dict] = {}


def callback_url() -> str:
    """Where OpenRouter sends the browser back: the API as the web sees it."""
    return _mcp_redirect_uri().removesuffix("/mcp-oauth/callback") + "/openrouter-oauth/callback"


def _back(**params: str) -> RedirectResponse:
    return RedirectResponse(f"{_web_origin()}/credential?{urlencode(params)}", status_code=302)


def _take_pending(state: str) -> dict | None:
    entry = _pending.pop(state, None)
    if entry is None or time.time() - entry["at"] > _PENDING_TTL:
        return None
    return entry


@openrouter_start_router.post("/openrouter/oauth/start")
async def start_openrouter_oauth(user_id: str = Depends(get_current_user_id)) -> dict:
    """Return the OpenRouter sign-in URL."""
    now = time.time()
    for state, entry in list(_pending.items()):
        if now - entry["at"] > _PENDING_TTL:
            del _pending[state]
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    _pending[state] = {"user_id": user_id, "verifier": verifier, "at": now}
    params = {
        "callback_url": callback_url(),
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "key_label": "AI Workforce Platform",
    }
    return {"authorize_url": f"{AUTHORIZE_URL}?{urlencode(params)}"}


async def _exchange(code: str, verifier: str) -> str:
    """The key OpenRouter issues for ``code``; ``ValueError`` worded for the user."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{OPENROUTER_BASE_URL}/auth/keys",
                json={"code": code, "code_verifier": verifier, "code_challenge_method": "S256"},
            )
    except httpx.HTTPError as exc:
        raise ValueError(f"Không kết nối được OpenRouter: {exc}") from exc
    try:
        data = response.json()
    except ValueError:
        data = {}
    key = data.get("key") if isinstance(data, dict) else None
    if response.status_code >= 400 or not key:
        reason = ""
        if isinstance(data, dict):
            error = data.get("error")
            reason = str(error.get("message") if isinstance(error, dict) else error or "")
        raise ValueError(f"OpenRouter từ chối cấp key: {reason or f'HTTP {response.status_code}'}")
    return str(key)


@openrouter_callback_router.get("/callback")
async def openrouter_oauth_callback(
    state: str = Query(default=""),
    code: str = Query(default=""),
    storage: StorageBase = Depends(get_storage),
) -> RedirectResponse:
    """Finish a sign-in started by :func:`start_openrouter_oauth`."""
    pending = _take_pending(state) if state else None
    if pending is None:
        return _back(oauth="error", message="Phiên kết nối đã hết hạn. Hãy bấm Kết nối OpenRouter lại.")
    if not code:
        return _back(oauth="error", message="OpenRouter không trả về mã kết nối (có thể bạn đã bấm Huỷ).")
    try:
        key = await _exchange(code, pending["verifier"])
    except ValueError as exc:
        logger.warning("OpenRouter sign-in failed: %s", exc)
        return _back(oauth="error", message=str(exc))
    user_id = pending["user_id"]
    credential = OpenRouterCredential(name="OpenRouter", api_key=SecretStr(key))
    for record in await storage.list_credentials(user_id):
        if record.data.get("type") == "openrouter_credential":
            previous = CredentialFactory.from_dict(record.data)
            credential = previous.model_copy(update={"api_key": SecretStr(key)})
            break
    await storage.upsert_credential(user_id, credential)
    return _back(oauth="ok", provider="OpenRouter")
