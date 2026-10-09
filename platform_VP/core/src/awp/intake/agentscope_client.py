"""Talks to AgentScope through its public REST surface, in process.

Using the REST API (not its internals) keeps the core independent of how
AgentScope stores things. The owner of every platform agent and session is a
service user derived from the tenant, never an end user.
"""
from __future__ import annotations

import asyncio

import httpx
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from .. import db
from ..profiles import AgentProfile, system_prompt
from ..providers import ModelSpec
from ..runtime import Runtime


def owner_of(tenant: str) -> str:
    return f"awp:{tenant}"


class AgentScopeClient:
    def __init__(self, rt: Runtime, app, internal_secret: str) -> None:
        self.rt = rt
        self._secret = internal_secret
        self._create_lock = asyncio.Lock()  # first-use creation of credentials and agents
        self._http = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://agentscope.local",
            timeout=60.0)

    async def aclose(self) -> None:
        await self._http.aclose()

    def _h(self, tenant: str) -> dict:
        return {"X-User-ID": owner_of(tenant), "X-AWP-Internal": self._secret}

    async def _post(self, tenant: str, path: str, body: dict) -> dict:
        r = await self._http.post(path, headers=self._h(tenant), json=body)
        if r.status_code >= 300:
            raise RuntimeError(f"AgentScope {path} -> {r.status_code}: {r.text[:300]}")
        return r.json()

    async def credential_id(self, tenant: str, spec: ModelSpec) -> str:
        user = owner_of(tenant)
        t = db.credential_map.c
        async with self._create_lock:
            async with self.rt.db.engine.connect() as conn:
                row = (await conn.execute(select(t.credential_id).where(
                    t.user_id == user, t.spec_id == spec.id))).first()
            if row:
                return row[0]
            created = await self._post(tenant, "/credential/", self.rt.catalog.credential_payload(spec))
            cid = created["credential_id"]
            try:
                async with self.rt.db.engine.begin() as conn:
                    await conn.execute(insert(db.credential_map).values(
                        user_id=user, spec_id=spec.id, credential_id=cid))
            except IntegrityError:  # another process won; use its credential
                async with self.rt.db.engine.connect() as conn:
                    cid = (await conn.execute(select(t.credential_id).where(
                        t.user_id == user, t.spec_id == spec.id))).scalar_one()
            return cid

    async def agent_id(self, tenant: str, profile: AgentProfile, version: int) -> str:
        t = db.agent_map.c
        async with self._create_lock:
            async with self.rt.db.engine.connect() as conn:
                row = (await conn.execute(select(t.agent_id).where(
                    t.tenant == tenant, t.key == profile.key, t.version == version))).first()
            if row:
                return row[0]
            body = {"name": profile.name,
                    "system_prompt": system_prompt(profile, version, self.rt.settings),
                    "react_config": {"max_iters": profile.max_iters}}
            created = await self._post(tenant, "/agent/", body)
            aid = created["agent_id"]
            try:
                async with self.rt.db.engine.begin() as conn:
                    await conn.execute(insert(db.agent_map).values(
                        tenant=tenant, key=profile.key, version=version, agent_id=aid))
            except IntegrityError:
                async with self.rt.db.engine.connect() as conn:
                    aid = (await conn.execute(select(t.agent_id).where(
                        t.tenant == tenant, t.key == profile.key, t.version == version))).scalar_one()
            return aid

    async def new_session(self, tenant: str, agent_id: str, name: str, spec: ModelSpec) -> str:
        cid = await self.credential_id(tenant, spec)
        created = await self._post(tenant, "/sessions/", {
            "agent_id": agent_id, "name": name,
            "chat_model_config": self.rt.catalog.chat_config(spec, cid)})
        sid = created["session_id"]
        r = await self._http.patch(f"/sessions/{sid}", headers=self._h(tenant),
                                   params={"agent_id": agent_id},
                                   json={"permission_mode": "dont_ask"})
        if r.status_code >= 300:
            raise RuntimeError(f"AgentScope session mode -> {r.status_code}: {r.text[:200]}")
        return sid

    async def say(self, tenant: str, agent_id: str, session_id: str, text: str,
                  name: str = "intake", extra_content: list | None = None) -> None:
        r = await self._http.post("/chat/", headers=self._h(tenant), json={
            "agent_id": agent_id, "session_id": session_id,
            "input": {"name": name, "role": "user", "content": [{"type": "text", "text": text}, *(extra_content or [])]}})
        if r.status_code >= 300:
            raise RuntimeError(f"AgentScope /chat/ -> {r.status_code}: {r.text[:300]}")
