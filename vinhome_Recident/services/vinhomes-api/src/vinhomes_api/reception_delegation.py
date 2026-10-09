"""Short-lived Reception delegation, resolved against canonical authority on every call.

The backend opens one delegation for each resident message and hands the Reception runtime a
token for it. Every call re-reads the delegation, the client and the resident's own authority,
so the token stops working when the turn ends or anything behind it is revoked.
Only a resident acting for themselves is supported: a service never names the resident itself.
"""

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"
RECEPTION_CLIENT_ID = "reception"
TURN_SECONDS = 600


def _key() -> bytes:
    value = os.getenv("RECEPTION_DELEGATION_KEY", "")
    try:
        key = bytes.fromhex(value)
    except ValueError:
        key = b""
    if len(key) < 32:
        raise HTTPException(503, "RECEPTION_DELEGATION_KEY requires at least 32 random bytes as hex")
    return key


def mint(claims: dict) -> str:
    payload = base64.urlsafe_b64encode(json.dumps(claims, sort_keys=True, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(_key(), ("reception-v1." + payload).encode(), hashlib.sha256).hexdigest()
    return payload + "." + signature


def read(token: str) -> dict:
    key = _key()
    try:
        if len(token) > 4096:
            raise ValueError()
        payload, signature = token.split(".")
        expected = hmac.new(key, ("reception-v1." + payload).encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError()
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if claims["aud"] != "reception-v1" or not time.time() < claims["exp"] <= time.time() + TURN_SECONDS + 1:
            raise ValueError()
        UUID(claims["runId"])
        return claims
    except (ValueError, KeyError, TypeError):
        raise HTTPException(401, "Invalid or expired Reception delegation") from None


async def authority(db, run_id: UUID):
    row = (await db.execute(text(f"""
        select d.id as run_id,d.tenant_id,d.channel_id,d.client_id,d.user_id
        from delegations d
        join integration_clients c on c.tenant_id=d.tenant_id and c.id=d.client_id and c.kind='reception' and c.status='active'
        join users u on u.id=d.user_id and u.status='active'
        join tenant_memberships m on m.tenant_id=d.tenant_id and m.user_id=u.id and m.status='active'
        join channels ch on ch.tenant_id=d.tenant_id and ch.id=d.channel_id
        where d.tenant_id={TENANT} and d.id=:run_id and d.purpose='reception_turn'
          and d.status='active' and d.expires_at>now()
    """), {"run_id": run_id})).mappings().first()
    if row is None:
        raise HTTPException(403, "Reception delegation is inactive")
    # Reuse the resident channel ownership rule, including membership revocation.
    from .v3_resident import _owned_chat
    await _owned_chat((db, row["user_id"]), row["channel_id"])
    # The runtime keys a conversation by "binding" and names the resident its "principal": both are
    # stable values derived from the channel and the user, not rows of their own.
    return {**dict(row), "binding_id": "channel:" + row["channel_id"], "principal_id": row["user_id"]}


async def reception_client(db) -> str:
    """A tenant has one Reception client; register it the first time it is needed."""
    client = (await db.execute(text(f"select id from integration_clients where kind='reception' and status='active' and tenant_id={TENANT} limit 1"))).scalar_one_or_none()
    if client is None:
        client = (await db.execute(text(f"""
            insert into integration_clients(tenant_id,id,name,kind,status)
            values ({TENANT},:id,'Lễ tân','reception','active') returning id
        """), {"id": RECEPTION_CLIENT_ID})).scalar_one()
    return client


async def start_run(db, actor_id: str, channel_id: str, message_id: str, policy_version: str) -> dict:
    """Open the delegation for one resident message and return it.

    `db` is already scoped to the resident who sent the message. Each message gets its own
    delegation, so a token never outlives its turn.
    """
    await db.execute(text("select 1 from channels where id=:id for update"), {"id": channel_id})
    client = await reception_client(db)
    # A turn lasts seconds and its token ten minutes: anything still active after that was abandoned.
    await db.execute(text(f"""
        update delegations set status='failed',error_code='abandoned',finished_at=now()
        where tenant_id={TENANT} and channel_id=:channel and status='active' and created_at<now()-interval '15 minutes'
    """), {"channel": channel_id})
    run_id = (await db.execute(text(f"""
        insert into delegations(tenant_id,client_id,user_id,purpose,channel_id,idempotency_key,correlation_id,expires_at)
        values({TENANT},:client,:actor,'reception_turn',:channel,:key,:trace,now()+make_interval(secs=>:ttl))
        returning id
    """), {"client": client, "actor": actor_id, "channel": channel_id, "key": "reception-turn:" + message_id,
           "trace": str(uuid4()), "ttl": TURN_SECONDS})).scalar_one()
    # Fails here, before any token exists, when the resident is not in good standing.
    row = await authority(db, run_id)
    claims = {"aud": "reception-v1", "exp": int(time.time()) + TURN_SECONDS,
              "runId": str(row["run_id"]), "tenantId": str(row["tenant_id"]),
              "bindingId": row["binding_id"], "principalId": row["principal_id"]}
    from .v3_audit import audit
    await audit(db, actor_id, "reception.delegation_issued", "delegation", claims["runId"],
                {"bindingId": claims["bindingId"], "expiresAt": claims["exp"]})
    return {"token": mint(claims), "expiresAt": claims["exp"],
            "context": {k: claims[k] for k in ("tenantId", "runId", "bindingId", "principalId")}}


async def finish_run(db, run_id: str, succeeded: bool, usage: dict | None = None) -> None:
    """Ending the turn revokes its token. `usage` is what the runtime reports the turn cost."""
    usage = usage or {}
    await db.execute(text(f"""
        update delegations set status=:status,finished_at=now(),input_tokens=:input,output_tokens=:output
        where tenant_id={TENANT} and id=cast(:id as uuid) and status='active'
    """), {"id": run_id, "status": "finished" if succeeded else "failed",
           "input": int(usage.get("input_tokens") or 0), "output": int(usage.get("output_tokens") or 0)})


async def delegated_scope(request: Request):
    value = request.headers.get("authorization", "")
    if not value.startswith("Bearer "):
        raise HTTPException(401, "Reception delegation required")
    claims = read(value[7:])
    settings = request.app.state.settings
    if str(settings.tenant_id) != claims.get("tenantId"):
        raise HTTPException(403, "Wrong delegation tenant")
    engine = request.app.state.engine
    if engine is None:
        raise HTTPException(503, "Database unavailable")
    try:
        async with engine.begin() as db:
            await db.execute(text("select set_config('app.tenant_id',:tenant,true)"), {"tenant": str(settings.tenant_id)})
            row = await authority(db, UUID(claims["runId"]))
            expected = {"bindingId": row["binding_id"], "principalId": row["principal_id"]}
            if any(claims.get(k) != v for k, v in expected.items()):
                raise HTTPException(403, "Reception delegation revoked")
            await db.execute(text("select set_config('app.user_id',:actor,true)"), {"actor": row["user_id"]})
            yield db, row
    except IntegrityError as exc:
        raise HTTPException(409, "V3 constraint conflict; reload the resource and retry") from exc
    except (SQLAlchemyError, OSError) as exc:
        raise HTTPException(503, "V3 database is unavailable or missing required tables") from exc


DelegatedScope = Annotated[tuple, Depends(delegated_scope, scope="function")]
