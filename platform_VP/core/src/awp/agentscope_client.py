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

from . import db
from .profiles import AgentProfile, system_prompt
from .providers import ModelSpec
from .runtime import Runtime


def owner_of(tenant: str) -> str:
    return f"awp:{tenant}"


class SessionBusy(RuntimeError):
    """/chat answered 409: a run holds the session. Nothing was stored, so sending again is safe."""


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
        """The AgentScope agent of a profile version (created on first use, then reused)."""
        t = db.agent_map.c
        key = profile.key
        async with self._create_lock:
            async with self.rt.db.engine.connect() as conn:
                row = (await conn.execute(select(t.agent_id).where(
                    t.tenant == tenant, t.key == key, t.version == version))).first()
            if row:
                return row[0]
            aid = await self.new_agent(tenant, profile, version)
            try:
                async with self.rt.db.engine.begin() as conn:
                    await conn.execute(insert(db.agent_map).values(
                        tenant=tenant, key=key, version=version, agent_id=aid))
            except IntegrityError:
                async with self.rt.db.engine.connect() as conn:
                    aid = (await conn.execute(select(t.agent_id).where(
                        t.tenant == tenant, t.key == key, t.version == version))).scalar_one()
            return aid

    async def new_agent(self, tenant: str, profile: AgentProfile, version: int) -> str:
        """An AgentScope agent made from the profile as it is now, kept nowhere: what an evaluation runs, because
        the agent of a draft version must not outlive an edit of the draft."""
        body = {"name": profile.name,
                "system_prompt": system_prompt(profile, version, self.rt.settings),
                "react_config": {"max_iters": profile.max_iters}}
        return (await self._post(tenant, "/agent/", body))["agent_id"]

    async def new_session(self, tenant: str, agent_id: str, name: str, spec: ModelSpec,
                          workspace_id: str | None = None) -> str:
        """`workspace_id` names the workspace explicitly. Without it AgentScope shares one per agent, which for a
        workflow would mean one directory for every resident of the partner."""
        cid = await self.credential_id(tenant, spec)
        body = {"agent_id": agent_id, "name": name, "chat_model_config": self.rt.catalog.chat_config(spec, cid)}
        if workspace_id:
            body["workspace_id"] = workspace_id
        created = await self._post(tenant, "/sessions/", body)
        sid = created["session_id"]
        r = await self._http.patch(f"/sessions/{sid}", headers=self._h(tenant),
                                   params={"agent_id": agent_id},
                                   json={"permission_mode": "dont_ask"})
        if r.status_code >= 300:
            raise RuntimeError(f"AgentScope session mode -> {r.status_code}: {r.text[:200]}")
        return sid

    async def say(self, tenant: str, agent_id: str, session_id: str, text: str,
                  name: str = "resident", msg_id: str | None = None) -> None:
        """One user message. With `msg_id` the turn it starts carries that id, which is how the
        engine knows the message arrived (a 200 alone does not say so)."""
        msg = {"name": name, "role": "user", "content": [{"type": "text", "text": text}]}
        if msg_id:
            msg["id"] = msg_id
        r = await self._http.post("/chat/", headers=self._h(tenant), json={
            "agent_id": agent_id, "session_id": session_id, "input": msg})
        if r.status_code == 409:
            raise SessionBusy(f"session {session_id} is running")
        if r.status_code >= 300:
            raise RuntimeError(f"AgentScope /chat/ -> {r.status_code}: {r.text[:300]}")

    async def confirm(self, tenant: str, agent_id: str, session_id: str, event) -> None:
        """Wake a session parked on a permission with the decision (a UserConfirmResultEvent built from stored data).
        Like `say`: 409 means a run holds the session and nothing was taken."""
        r = await self._http.post("/chat/", headers=self._h(tenant), json={
            "agent_id": agent_id, "session_id": session_id, "input": event.model_dump(mode="json")})
        if r.status_code == 409:
            raise SessionBusy(f"session {session_id} is running")
        if r.status_code >= 300:
            raise RuntimeError(f"AgentScope /chat/ -> {r.status_code}: {r.text[:300]}")

    async def abandon(self, tenant: str, agent_id: str, session_id: str, event) -> None:
        """Close a parked session's pending tool call with a UserInterruptEvent (P0: /chat cannot carry one, the
        wake-up queue can; AgentScope's own interrupt endpoint does the same). The run does not call the model."""
        from agentscope.app._bus_ops import enqueue_run_trigger  # internal to AgentScope: noted in the decisions doc

        await enqueue_run_trigger(self.rt.bus, user_id=owner_of(tenant), session_id=session_id,
                                  agent_id=agent_id, kind="resume", inputs=event)

    async def status(self, tenant: str, agent_id: str, session_id: str) -> str | None:
        """idle | running | awaiting_permission | awaiting_external_result; "gone" for a session that is not there, None
        when it could not be read."""
        r = await self._http.get(f"/sessions/{session_id}/status", headers=self._h(tenant), params={"agent_id": agent_id})
        if r.status_code == 404:
            return "gone"
        return r.json().get("status") if r.status_code < 300 else None

    async def interrupt(self, tenant: str, agent_id: str, session_id: str) -> None:
        """Stop what the session is running (a no-op when it is idle)."""
        r = await self._http.post(f"/sessions/{session_id}/interrupt", headers=self._h(tenant),
                                  params={"agent_id": agent_id})
        if r.status_code >= 300 and r.status_code != 404:
            raise RuntimeError(f"AgentScope interrupt -> {r.status_code}: {r.text[:200]}")
