"""Discord proof is exchanged on the server; fixtures never reach Discord."""

import base64
import hashlib
import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy import update

from vin_fixtures import authority as authority  # noqa: F401
from agentscope.app._service import _discord_identity as identity
from agentscope.app.vin_platform import PlatformError
from agentscope.app.vin_platform import _tables as t


@pytest.fixture
def oauth_config(monkeypatch):
    monkeypatch.setenv("DISCORD_OAUTH_CLIENT_ID", "fixture-client")
    monkeypatch.setenv("DISCORD_OAUTH_CLIENT_SECRET", "offline-discord-client-secret")
    monkeypatch.setenv("DISCORD_OAUTH_REDIRECT_URI", "https://platform.fixture.invalid/channel")


@pytest.mark.asyncio
async def test_server_proof_pkce_owner_replay_revoke_and_no_token_storage(authority, oauth_config):
    context = await authority.context("alice")
    started = await identity.start(authority, context)
    params = parse_qs(urlsplit(started["authorization_url"]).query)
    assert params["scope"] == ["identify"] and params["code_challenge_method"] == ["S256"]
    calls = []
    def discord(request):
        calls.append(request.url.path)
        if request.url.path.endswith("/token"):
            body = parse_qs(request.content.decode())
            challenge = base64.urlsafe_b64encode(hashlib.sha256(body["code_verifier"][0].encode()).digest()).decode().rstrip("=")
            assert challenge == params["code_challenge"][0]
            assert body["client_secret"] == ["offline-discord-client-secret"]
            return httpx.Response(200, json={"token_type": "Bearer", "scope": "identify", "access_token": "offline-access", "refresh_token": "offline-refresh"})
        if request.url.path.endswith("/@me"):
            assert request.headers["Authorization"] == "Bearer offline-access"
            return httpx.Response(200, json={"id": "100", "username": "fixture-not-used-as-identity"})
        assert request.url.path.endswith("/token/revoke")
        return httpx.Response(200, json={})
    async with httpx.AsyncClient(transport=httpx.MockTransport(discord)) as client:
        authority.http_client = client
        for user, state, issuer, code in (("bob", started["state"], "https://discord.com", "DISCORD_OAUTH_STATE_INVALID"),
                ("alice", started["state"] + "tampered", "https://discord.com", "DISCORD_OAUTH_STATE_INVALID"),
                ("alice", started["state"], "https://attacker.invalid", "DISCORD_ISSUER_MISMATCH")):
            with pytest.raises(PlatformError, match=code):
                await identity.complete(authority, await authority.context(user), state=state, code="fixture-code", issuer=issuer)
        assert calls == []
        result = await identity.complete(authority, context, state=started["state"], code="fixture-code", issuer="https://discord.com")
        assert result["verified"] and result["discord_user_id"] == "100"
        with pytest.raises(PlatformError, match="DISCORD_OAUTH_STATE_INVALID"):
            await identity.complete(authority, context, state=started["state"], code="fixture-code", issuer="https://discord.com")
        assert len(calls) == 3
    assert not (await identity.identity(authority, await authority.context("bob")))["verified"]
    stored = json.dumps(await authority.automation_list(context, "derived") + await authority.automation_list(context, "channel"), default=str)
    assert all(secret not in stored for secret in ("offline-access", "offline-refresh", "offline-discord-client-secret", "fixture-code", "verifier"))
    await identity.revoke(authority, context)
    with pytest.raises(PlatformError, match="DISCORD_IDENTITY_REQUIRED"):
        await identity.verified_owner(authority, context)


@pytest.mark.asyncio
async def test_expired_oauth_never_exchanges_or_accepts_client_identity(authority, oauth_config):
    context = await authority.context("alice")
    started = await identity.start(authority, context)
    async with authority.engine.begin() as db:
        await db.execute(update(t.automation).values(data={"type": "discord-oauth", "state": "pending", "expires_at": 1,
            "state_hash": hashlib.sha256(started["state"].encode()).hexdigest()}))
    with pytest.raises(PlatformError, match="DISCORD_OAUTH_STATE_INVALID"):
        await identity.complete(authority, context, state=started["state"], code="fixture-code", issuer="https://discord.com")
    assert not (await identity.identity(authority, context))["verified"]


@pytest.mark.asyncio
async def test_missing_server_oauth_configuration_fails_closed(authority, monkeypatch):
    monkeypatch.delenv("DISCORD_OAUTH_CLIENT_SECRET", raising=False)
    with pytest.raises(PlatformError, match="DISCORD_IDENTITY_NOT_CONFIGURED"):
        await identity.start(authority, await authority.context("alice"))
