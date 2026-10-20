# -*- coding: utf-8 -*-
"""OAuth sign-in for remote MCPs, per the MCP authorization spec.

Hosted MCPs such as Notion, Linear, Sentry, Atlassian or Supabase take no
API key: the user signs in. The flow, split across two requests because
the user's browser goes to the provider in between:

1. :func:`discover` reads the protected-resource metadata the MCP points
   to (or its well-known URL), then the authorization server metadata.
2. :func:`register` registers this platform as a client (dynamic client
   registration) — once per MCP record.
3. :func:`begin` builds the authorize URL with PKCE and remembers the
   state; the callback calls :func:`complete` to trade the code for
   tokens.
4. :func:`ensure_fresh` refreshes an expiring token before a sync or an
   agent turn, and :func:`with_token` puts it on the MCP client.

Every metadata, registration and token URL is checked with
:func:`ensure_public_url`, since an MCP chooses them. Pending sign-ins
live in this process (one app worker); a restart means signing in again.
"""
import asyncio
import base64
import hashlib
import re
import secrets
import time
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx

from ...mcp import MCPClient
from ..storage import MCPRecord
from ..storage._model._mcp import MCPOAuth
from ._openapi import OpenAPIError, ensure_public_url

_PENDING_TTL = 15 * 60
_REFRESH_MARGIN = 120
_pending: dict[str, dict] = {}
_locks: dict[str, asyncio.Lock] = {}


class OAuthError(ValueError):
    """A sign-in step that failed, worded for the user."""


async def _get_json(client: httpx.AsyncClient, url: str) -> dict | None:
    try:
        await ensure_public_url(url)
        response = await client.get(url, headers={"Accept": "application/json"})
    except (OpenAPIError, httpx.HTTPError):
        return None
    if response.status_code != 200:
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _well_known(url: str, suffix: str) -> list[str]:
    """``/.well-known/{suffix}`` with the URL's path inserted, then bare."""
    parts = urlsplit(url)
    origin, path = f"{parts.scheme}://{parts.netloc}", parts.path.rstrip("/")
    urls = [f"{origin}/.well-known/{suffix}{path}"] if path else []
    return [*urls, f"{origin}/.well-known/{suffix}"]


async def _www_authenticate(client: httpx.AsyncClient, mcp_url: str) -> str:
    """The challenge an unauthenticated ``initialize`` gets back."""
    try:
        await ensure_public_url(mcp_url)
        response = await client.post(
            mcp_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "awp-oauth-probe", "version": "1"},
                },
            },
            headers={"Accept": "application/json, text/event-stream"},
        )
    except (OpenAPIError, httpx.HTTPError):
        return ""
    return response.headers.get("www-authenticate", "") if response.status_code == 401 else ""


async def discover(mcp_url: str) -> MCPOAuth | None:
    """Find the MCP's authorization server; ``None`` when it has none."""
    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
        challenge = await _www_authenticate(client, mcp_url)
        match = re.search(r'resource_metadata="([^"]+)"', challenge)
        candidates = [match.group(1)] if match else []
        resource_meta = None
        for url in [*candidates, *_well_known(mcp_url, "oauth-protected-resource")]:
            resource_meta = await _get_json(client, url)
            if resource_meta and resource_meta.get("authorization_servers"):
                break
            resource_meta = None

        if resource_meta:
            issuer = str(resource_meta["authorization_servers"][0]).rstrip("/")
            resource = str(resource_meta.get("resource") or mcp_url)
            scopes = [str(s) for s in resource_meta.get("scopes_supported") or []]
        else:
            # Older servers (2025-03-26) host the authorization server at
            # the MCP's own origin.
            parts = urlsplit(mcp_url)
            issuer, resource, scopes = f"{parts.scheme}://{parts.netloc}", mcp_url, []

        server = None
        for url in [
            *_well_known(issuer, "oauth-authorization-server"),
            *_well_known(issuer, "openid-configuration"),
            f"{issuer}/.well-known/openid-configuration",
        ]:
            server = await _get_json(client, url)
            if server and server.get("authorization_endpoint") and server.get("token_endpoint"):
                break
            server = None
    if server is None:
        return None
    methods = server.get("code_challenge_methods_supported")
    if methods and "S256" not in methods:
        return None
    return MCPOAuth(
        issuer=str(server.get("issuer") or issuer),
        authorization_endpoint=str(server["authorization_endpoint"]),
        token_endpoint=str(server["token_endpoint"]),
        registration_endpoint=server.get("registration_endpoint"),
        scopes=scopes,
        resource=resource,
    )


async def register(oauth: MCPOAuth, redirect_uri: str) -> None:
    """Register this platform as an OAuth client of the MCP (RFC 7591)."""
    if not oauth.registration_endpoint:
        raise OAuthError(
            "Nhà cung cấp này không cho ứng dụng tự đăng ký (không có dynamic "
            "client registration), nên platform chưa đăng nhập được.",
        )
    body: dict[str, Any] = {
        "client_name": "AI Workforce Platform",
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }
    if oauth.scopes:
        body["scope"] = " ".join(oauth.scopes)
    try:
        await ensure_public_url(oauth.registration_endpoint)
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(oauth.registration_endpoint, json=body)
    except (OpenAPIError, httpx.HTTPError) as exc:
        raise OAuthError(f"Không đăng ký được ứng dụng với nhà cung cấp: {exc}") from exc
    if response.status_code >= 400:
        raise OAuthError(f"Nhà cung cấp từ chối đăng ký ứng dụng (HTTP {response.status_code}).")
    data = response.json()
    oauth.client_id = str(data.get("client_id") or "")
    if not oauth.client_id:
        raise OAuthError("Nhà cung cấp không trả về client_id.")
    oauth.client_secret = str(data.get("client_secret") or "")
    method = str(data.get("token_endpoint_auth_method") or "")
    if oauth.client_secret:
        oauth.token_auth = "client_secret_basic" if method == "client_secret_basic" else "client_secret_post"
    else:
        oauth.token_auth = "none"
    oauth.redirect_uri = redirect_uri


def begin(oauth: MCPOAuth, user_id: str, mcp_id: str) -> str:
    """Remember a sign-in and return the URL to send the browser to."""
    now = time.time()
    for state, entry in list(_pending.items()):
        if now - entry["at"] > _PENDING_TTL:
            del _pending[state]
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    _pending[state] = {"user_id": user_id, "mcp_id": mcp_id, "verifier": verifier, "at": now}
    params = {
        "response_type": "code",
        "client_id": oauth.client_id,
        "redirect_uri": oauth.redirect_uri,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    if oauth.scopes:
        params["scope"] = " ".join(oauth.scopes)
    if oauth.resource:
        params["resource"] = oauth.resource
    joiner = "&" if "?" in oauth.authorization_endpoint else "?"
    return f"{oauth.authorization_endpoint}{joiner}{urlencode(params)}"


def take_pending(state: str) -> dict | None:
    """The sign-in ``state`` belongs to, once; ``None`` if unknown/expired."""
    entry = _pending.pop(state, None)
    if entry is None or time.time() - entry["at"] > _PENDING_TTL:
        return None
    return entry


async def _token_request(oauth: MCPOAuth, form: dict) -> None:
    form = {**form, "client_id": oauth.client_id}
    if oauth.resource:
        form["resource"] = oauth.resource
    auth = None
    if oauth.token_auth == "client_secret_basic":
        auth = (oauth.client_id, oauth.client_secret)
    elif oauth.token_auth == "client_secret_post":
        form["client_secret"] = oauth.client_secret
    try:
        await ensure_public_url(oauth.token_endpoint)
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                oauth.token_endpoint,
                data=form,
                auth=auth,
                headers={"Accept": "application/json"},
            )
    except (OpenAPIError, httpx.HTTPError) as exc:
        raise OAuthError(f"Không lấy được token từ nhà cung cấp: {exc}") from exc
    try:
        data = response.json()
    except ValueError:
        data = {}
    if response.status_code >= 400 or not data.get("access_token"):
        reason = data.get("error_description") or data.get("error") or f"HTTP {response.status_code}"
        raise OAuthError(f"Nhà cung cấp từ chối cấp token: {reason}")
    oauth.access_token = str(data["access_token"])
    oauth.refresh_token = str(data.get("refresh_token") or oauth.refresh_token)
    expires_in = data.get("expires_in")
    oauth.expires_at = time.time() + float(expires_in) if expires_in else None


async def complete(oauth: MCPOAuth, code: str, verifier: str) -> None:
    """Trade the authorization code for tokens."""
    await _token_request(
        oauth,
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": oauth.redirect_uri,
            "code_verifier": verifier,
        },
    )


def with_token(client: MCPClient, oauth: MCPOAuth) -> MCPClient:
    """``client`` carrying the current access token."""
    headers = dict(getattr(client.mcp_config, "headers", None) or {})
    headers["Authorization"] = f"Bearer {oauth.access_token}"
    return MCPClient.model_validate(
        {
            **client.model_dump(mode="json"),
            "mcp_config": {**client.mcp_config.model_dump(mode="json"), "headers": headers},
        },
    )


async def ensure_fresh(record: MCPRecord) -> bool:
    """Refresh ``record``'s token when it is about to expire.

    Returns:
        `bool`: Whether the record changed (and so should be saved).
    """
    oauth = record.oauth
    if (
        oauth is None
        or not oauth.access_token
        or not oauth.refresh_token
        or oauth.expires_at is None
        or oauth.expires_at - time.time() > _REFRESH_MARGIN
    ):
        return False
    async with _locks.setdefault(record.id, asyncio.Lock()):
        if oauth.expires_at is not None and oauth.expires_at - time.time() > _REFRESH_MARGIN:
            return False
        await _token_request(
            oauth,
            {"grant_type": "refresh_token", "refresh_token": oauth.refresh_token},
        )
    record.client = with_token(record.client, oauth)
    return True
