"""Server-verified Discord identity, independent of a customer's bot token."""

import base64
import hashlib
import hmac
import os
import secrets
import time
from urllib.parse import urlencode, urlsplit
from uuid import NAMESPACE_URL, uuid4, uuid5

import httpx

from ._catalog_resources import catalog_authority
from ..vin_platform import PlatformError


async def scope(storage, user_id):
    authority = catalog_authority(storage)
    if authority is None:
        raise PlatformError("VIN_PLATFORM_DISABLED", 503)
    context = await authority.context(user_id, purpose="channel")
    if context.role != "VIN_USER":
        raise PlatformError("PERSONAL_WORKSPACE_REQUIRED", 403)
    return authority, context


def _identity_id(context):
    return str(uuid5(NAMESPACE_URL, f"discord-identity:{context.tenant_id}:{context.initiator_user_id}"))


async def identity(authority, context):
    rows = await authority.automation_list(context, "channel")
    row = next((item for item in rows if item["id"] == _identity_id(context)), None)
    if row is None or row["data"].get("state") != "verified":
        return {"verified": False}
    return {"verified": True, "discord_user_id": row["data"]["discord_user_id"],
        "verified_at": row["data"]["verified_at"], "revision": row["revision"]}


async def verified_owner(authority, context):
    result = await identity(authority, context)
    if not result["verified"]:
        raise PlatformError("DISCORD_IDENTITY_REQUIRED", 403)
    return result


async def bot_owner(authority, credentials):
    """Verify a customer-supplied bot without requiring Platform OAuth setup."""
    from ..channel import DiscordChannel
    from pydantic import ValidationError
    try:
        parsed = DiscordChannel.Credentials.model_validate(credentials)
    except ValidationError:
        raise PlatformError("DISCORD_BOT_CREDENTIALS_INVALID", 400) from None
    token = parsed.bot_token
    if hasattr(token, "get_secret_value"):
        token = token.get_secret_value()

    async def verify(client):
        response = await client.get("https://discord.com/api/v10/applications/@me",
                                    headers={"Authorization": "Bot " + token})
        response.raise_for_status()
        data = response.json()
        owner = (data.get("team") or {}).get("owner_user_id") or (data.get("owner") or {}).get("id")
        if str(data.get("id", "")) != str(parsed.application_id):
            raise PlatformError("DISCORD_APPLICATION_MISMATCH", 403)
        if not isinstance(owner, str) or not owner.isascii() or not owner.isdigit() or not 1 <= len(owner) <= 20 or int(owner) == 0:
            raise PlatformError("DISCORD_BOT_OWNER_UNAVAILABLE", 403)
        return owner

    try:
        if authority.http_client is not None:
            return await verify(authority.http_client)
        async with httpx.AsyncClient(timeout=20, trust_env=False, follow_redirects=False) as client:
            return await verify(client)
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise PlatformError("DISCORD_BOT_VERIFICATION_FAILED", 400) from None


def _config():
    client_id = os.getenv("DISCORD_OAUTH_CLIENT_ID", "")
    secret = os.getenv("DISCORD_OAUTH_CLIENT_SECRET", "")
    redirect = os.getenv("DISCORD_OAUTH_REDIRECT_URI", "")
    parsed = urlsplit(redirect)
    if (not client_id or not secret or not parsed.netloc or parsed.username or parsed.password or parsed.fragment
            or (parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}))):
        raise PlatformError("DISCORD_IDENTITY_NOT_CONFIGURED", 503)
    return client_id, secret, redirect


async def start(authority, context):
    client_id, _, redirect = _config()
    ident, nonce, verifier = str(uuid4()), secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    state = ident + "." + nonce
    await authority.automation_put(context, ident, "derived", {"type": "discord-oauth", "state": "pending",
        "state_hash": hashlib.sha256(state.encode()).hexdigest(), "expires_at": int(time.time()) + 300,
        "verifier": authority.cipher().encrypt(verifier.encode()).decode()})
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return {"authorization_url": "https://discord.com/oauth2/authorize?" + urlencode({"client_id": client_id,
        "redirect_uri": redirect, "response_type": "code", "scope": "identify", "prompt": "consent",
        "state": state, "code_challenge": challenge, "code_challenge_method": "S256"}), "state": state}


async def complete(authority, context, *, state, code, issuer):
    client_id, secret, redirect = _config()
    if issuer != "https://discord.com":
        raise PlatformError("DISCORD_ISSUER_MISMATCH", 403)
    ident = state.split(".", 1)[0]
    rows = await authority.automation_list(context, "derived")
    row = next((item for item in rows if item["id"] == ident and item["data"].get("type") == "discord-oauth"), None)
    if (row is None or row["data"].get("state") != "pending" or row["data"]["expires_at"] <= time.time()
            or not hmac.compare_digest(row["data"]["state_hash"], hashlib.sha256(state.encode()).hexdigest())):
        raise PlatformError("DISCORD_OAUTH_STATE_INVALID", 409)
    lease = await authority.claim(context, ident)
    verifier = authority.cipher().decrypt(row["data"]["verifier"].encode()).decode()

    async def exchange(client):
        token = await client.post("https://discord.com/api/oauth2/token", data={"grant_type": "authorization_code",
            "client_id": client_id, "client_secret": secret, "redirect_uri": redirect, "code": code, "code_verifier": verifier})
        token.raise_for_status()
        access = token.json()
        try:
            if access.get("token_type", "").lower() != "bearer" or "identify" not in access.get("scope", "").split():
                raise PlatformError("DISCORD_IDENTITY_INVALID", 403)
            response = await client.get("https://discord.com/api/v10/users/@me", headers={"Authorization": "Bearer " + access["access_token"]})
            response.raise_for_status()
            user = response.json()
            user_id = user.get("id", "")
            if not isinstance(user_id, str) or not user_id.isascii() or not user_id.isdigit() or not 1 <= len(user_id) <= 20 or int(user_id) == 0 or user.get("bot"):
                raise PlatformError("DISCORD_IDENTITY_INVALID", 403)
            return user_id
        finally:
            # Identify only: neither access nor refresh tokens are persisted.
            revoke = await client.post("https://discord.com/api/oauth2/token/revoke", data={"token": access["access_token"],
                "token_type_hint": "access_token", "client_id": client_id, "client_secret": secret})
            revoke.raise_for_status()

    try:
        if authority.http_client is not None:
            user_id = await exchange(authority.http_client)
        else:
            async with httpx.AsyncClient(timeout=20, trust_env=False, follow_redirects=False) as client:
                user_id = await exchange(client)
    except PlatformError:
        await authority.complete_claim(context, ident, lease, {"type": "discord-oauth", "state": "failed"})
        raise
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        await authority.complete_claim(context, ident, lease, {"type": "discord-oauth", "state": "failed"})
        raise PlatformError("DISCORD_IDENTITY_EXCHANGE_FAILED", 503) from exc
    current = next((item for item in await authority.automation_list(context, "channel") if item["id"] == _identity_id(context)), None)
    await authority.automation_put(context, _identity_id(context), "channel", {"type": "discord-identity", "state": "verified",
        "discord_user_id": user_id, "verified_at": int(time.time())}, current["revision"] if current else 0)
    await authority.complete_claim(context, ident, lease, {"type": "discord-oauth", "state": "succeeded"})
    return await identity(authority, context)


async def revoke(authority, context):
    row = next((item for item in await authority.automation_list(context, "channel") if item["id"] == _identity_id(context)), None)
    if row is not None:
        await authority.automation_put(context, row["id"], "channel", {"type": "discord-identity", "state": "revoked"}, row["revision"])
