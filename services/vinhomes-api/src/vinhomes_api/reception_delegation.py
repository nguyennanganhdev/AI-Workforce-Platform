"""Short-lived Reception delegation, resolved against canonical authority on every call.

The backend opens one run for each resident message and hands the Reception runtime a
token for that run. Every call re-reads the run, its binding and the resident's own
authority, so the token stops working when the run ends or anything behind it is revoked.
Only personal resident bindings are supported: a service never names the resident itself.
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
RECEPTION_AGENT_ID = "system-reception"
RUNTIME_BACKEND = "reception-langgraph"


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
        if claims["aud"] != "reception-v1" or not time.time() < claims["exp"] <= time.time() + 601:
            raise ValueError()
        UUID(claims["runId"])
        return claims
    except (ValueError, KeyError, TypeError):
        raise HTTPException(401, "Invalid or expired Reception delegation") from None


async def authority(db, run_id: UUID):
    row = (await db.execute(text(f"""
        select r.id as run_id,r.tenant_id,r.channel_id,r.agent_id,r.binding_id,
               r.authority_principal_id as principal_id,p.user_id,p.authz_version,
               b.generation,b.policy_version
        from agent_runs r
        join runtime_session_bindings b on b.tenant_id=r.tenant_id and b.id=r.binding_id
        join runtime_identities i on i.tenant_id=b.tenant_id and i.id=b.identity_id and i.backend_id=b.backend_id
        join runtime_backends rb on rb.id=b.backend_id and rb.enabled
        join execution_principals p on p.tenant_id=r.tenant_id and p.id=r.authority_principal_id and p.id=i.principal_id
        join users u on u.id=p.user_id and u.status='active'
        join tenant_memberships m on m.tenant_id=r.tenant_id and m.user_id=u.id and m.status='active'
        join agents a on a.tenant_id=r.tenant_id and a.id=r.agent_id and a.status='active' and a.purpose='reception'
        join channels c on c.tenant_id=r.tenant_id and c.id=r.channel_id
        where r.tenant_id={TENANT} and r.id=:run_id and r.status='running'
          and b.status='active' and i.status='active' and p.status='active' and p.kind='user'
          and b.audience_kind='personal' and b.customer_user_id=p.user_id
          and r.actor_user_id=p.user_id and (r.on_behalf_of_user_id is null or r.on_behalf_of_user_id=p.user_id)
          and r.authority_version=p.authz_version and r.policy_version=b.policy_version
          and r.channel_id=b.channel_id and r.agent_id=b.agent_id and r.version_id=b.agent_version_id
          and (b.expires_at is null or b.expires_at>now())
    """), {"run_id": run_id})).mappings().first()
    if row is None:
        raise HTTPException(403, "Reception run, binding or authority is inactive")
    # Reuse the resident channel ownership rule, including membership revocation.
    from .v3_resident import _owned_chat
    await _owned_chat((db, row["user_id"]), row["channel_id"])
    return dict(row)


async def reception_agent(db) -> str:
    """A tenant has one Reception agent; create the system one only when none exists."""
    agent = (await db.execute(text(f"select id from agents where purpose='reception' and tenant_id={TENANT} limit 1"))).scalar_one_or_none()
    if agent is None:
        agent = (await db.execute(text(f"""
            insert into agents(id,tenant_id,name,type,configuration,purpose,status)
            values (:id,{TENANT},'Lễ tân','built_in','{{}}','reception','active') returning id
        """), {"id": RECEPTION_AGENT_ID})).scalar_one()
    return agent


async def start_run(db, actor_id: str, channel_id: str, message_id: str, policy_version: str) -> dict:
    """Open the run for one resident message and return its delegation.

    `db` is already scoped to the resident who sent the message. The conversation keeps
    one binding; each message gets its own run, so a token never outlives its turn.
    """
    await db.execute(text("select 1 from channels where id=:id for update"), {"id": channel_id})
    agent = await reception_agent(db)
    backend = (await db.execute(text("select id from runtime_backends where code=:code and enabled"),
                                {"code": RUNTIME_BACKEND})).scalar_one_or_none()
    if backend is None:
        raise HTTPException(503, "Reception runtime backend is not registered")
    await db.execute(text(f"""
        insert into execution_principals(tenant_id,kind,user_id,status) values({TENANT},'user',:actor,'active')
        on conflict (tenant_id,user_id) where kind='user' do nothing
    """), {"actor": actor_id})
    principal = (await db.execute(text(f"""
        select id,authz_version from execution_principals where tenant_id={TENANT} and kind='user' and user_id=:actor
    """), {"actor": actor_id})).mappings().one()
    await db.execute(text(f"""
        insert into runtime_identities(tenant_id,backend_id,principal_id,runtime_user_key,status)
        values({TENANT},:backend,:principal,:actor,'active') on conflict (backend_id,principal_id) do nothing
    """), {"backend": backend, "principal": principal["id"], "actor": actor_id})
    binding = (await db.execute(text(f"""
        select id,agent_version_id,policy_version from runtime_session_bindings
        where tenant_id={TENANT} and channel_id=:channel and agent_id=:agent
          and audience_kind='personal' and status='active'
    """), {"channel": channel_id, "agent": agent})).mappings().first()
    if binding is None:
        await db.execute(text(f"""
            insert into agent_versions(tenant_id,agent_id,version_no,runtime,framework_version,instructions,config,config_hash,created_by)
            values({TENANT},:agent,1,'langgraph','langgraph','Reception graph (agent-reception/src/graph)','{{}}',:hash,:actor)
            on conflict (agent_id,version_no) do nothing
        """), {"agent": agent, "hash": hashlib.sha256(b"{}").hexdigest(), "actor": actor_id})
        binding = (await db.execute(text(f"""
            insert into runtime_session_bindings(tenant_id,identity_id,backend_id,channel_id,agent_id,agent_version_id,
                audience_kind,customer_user_id,started_by_user_id,runtime_session_key,checkpoint_namespace,status,policy_version)
            select {TENANT},i.id,i.backend_id,:channel,:agent,
                (select id from agent_versions where tenant_id={TENANT} and agent_id=:agent order by version_no desc limit 1),
                'personal',:actor,:actor,:session,'reception','active',:policy
            from runtime_identities i where i.backend_id=:backend and i.principal_id=:principal
            returning id,agent_version_id,policy_version
        """), {"channel": channel_id, "agent": agent, "actor": actor_id, "session": "reception:" + channel_id,
               "policy": policy_version, "backend": backend, "principal": principal["id"]})).mappings().one()
    run_id = (await db.execute(text(f"""
        insert into agent_runs(tenant_id,channel_id,agent_id,version_id,actor_user_id,idempotency_key,status,started_at,
            trace_id,binding_id,authority_principal_id,policy_version,authority_version)
        values({TENANT},:channel,:agent,:version,:actor,:key,'running',now(),:trace,:binding,:principal,:policy,:authz)
        returning id
    """), {"channel": channel_id, "agent": agent, "version": binding["agent_version_id"], "actor": actor_id,
           "key": "reception-turn:" + message_id, "trace": str(uuid4()), "binding": binding["id"],
           "principal": principal["id"], "policy": binding["policy_version"], "authz": principal["authz_version"]})).scalar_one()
    # Fails here, before any token exists, when the resident or the binding is not in good standing.
    row = await authority(db, run_id)
    claims = {"aud": "reception-v1", "exp": int(time.time()) + 600,
              "runId": str(row["run_id"]), "tenantId": str(row["tenant_id"]),
              "bindingId": str(row["binding_id"]), "principalId": str(row["principal_id"]),
              "authorityVersion": row["authz_version"], "generation": row["generation"]}
    from .v3_audit import audit
    await audit(db, actor_id, "reception.delegation_issued", "agent_run", claims["runId"],
                {"bindingId": claims["bindingId"], "expiresAt": claims["exp"]})
    return {"token": mint(claims), "expiresAt": claims["exp"],
            "context": {k: claims[k] for k in ("tenantId", "runId", "bindingId", "principalId")}}


async def finish_run(db, run_id: str, succeeded: bool) -> None:
    """Ending the run revokes its token."""
    await db.execute(text(f"""
        update agent_runs set status=:status,finished_at=now()
        where tenant_id={TENANT} and id=cast(:id as uuid) and status='running'
    """), {"id": run_id, "status": "succeeded" if succeeded else "failed"})


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
            expected = {"bindingId": str(row["binding_id"]), "principalId": str(row["principal_id"]),
                        "authorityVersion": row["authz_version"], "generation": row["generation"]}
            if any(claims.get(k) != v for k, v in expected.items()):
                raise HTTPException(403, "Reception delegation revoked")
            await db.execute(text("select set_config('app.user_id',:actor,true)"), {"actor": row["user_id"]})
            yield db, row
    except IntegrityError as exc:
        raise HTTPException(409, "V3 constraint conflict; reload the resource and retry") from exc
    except (SQLAlchemyError, OSError) as exc:
        raise HTTPException(503, "V3 database is unavailable or missing required tables") from exc


DelegatedScope = Annotated[tuple, Depends(delegated_scope, scope="function")]
