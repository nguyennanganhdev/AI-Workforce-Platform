"""The long-lived leader of a workflow: one AgentScope agent and ONE session for the whole workflow.

Created the first time a job runs (AgentScopeClient: agent per profile version, credential per
model, session with a name so AgentScope does not spend a model call naming it), bound to the workflow's
case as its leader, and remembered on the case row. Every later job and every report from the team goes
to the same session, so the context is the workflow's context.
"""
from __future__ import annotations

from typing import Any, NamedTuple

from sqlalchemy import select

from ..agentscope_client import AgentScopeClient
from ..evals import sandbox
from . import tables as t


class LeaderUnavailable(Exception):
    """The route's leader cannot be started (no such published leader profile, no model). Retrying the
    same job cannot help; an operator has to fix the route or the profile."""


class Leader(NamedTuple):
    tenant: str
    agent_id: str
    session_id: str


async def leader_of(rt, case_id: str) -> Leader | None:
    case = await rt.cases.get_case(case_id)
    if case and case["leader_agent_id"] and case["leader_session_id"]:
        return Leader(case["tenant"], case["leader_agent_id"], case["leader_session_id"])
    return None


async def ensure_leader(rt, client: AgentScopeClient, wf: Any) -> Leader:
    """The leader of `wf`, created on first use. Callers of one workflow take turns (the engine's
    dispatcher is one task per workflow), so two creations cannot race."""
    case = await rt.cases.get_case(wf["case_id"])
    pin = sandbox.pin_of(case)
    if pin is not None and not (rt.evals is not None and rt.evals.live(pin.get("run"))):
        # left by a process that died, or another process's: giving it a turn would spend the tenant's money on an
        # evaluation nobody reads (and the draft's template is in the memory of the process that runs it)
        raise LeaderUnavailable("the evaluation this sandbox workflow belongs to is not running in this process")
    if case and case["leader_agent_id"] and case["leader_session_id"]:
        return Leader(case["tenant"], case["leader_agent_id"], case["leader_session_id"])
    async with rt.db.engine.connect() as conn:
        profile_key = (await conn.execute(select(t.routes.c.leader_profile).where(
            t.routes.c.id == wf["route_id"]))).scalar_one()
    tenant = case["tenant"]
    if pin is not None:  # an evaluation: the exact version under test, in an agent of its own (a draft may still change)
        pinned = await sandbox.leader_for(rt, tenant, pin)
        if pinned is None:
            raise LeaderUnavailable("the version under evaluation is not a leader profile")
        profile, version = pinned
    else:
        rec = await rt.profiles.get_published(tenant, profile_key)
        if rec is None or rec.profile.role != "leader":
            raise LeaderUnavailable(f"no published leader profile {profile_key!r}")
        profile, version = rec.profile, rec.version
    spec = rt.catalog.pick(profile.model_tier)
    if spec is None:
        raise LeaderUnavailable("no model is configured")
    agent_id = await (client.new_agent(tenant, profile, version) if pin is not None
                      else client.agent_id(tenant, profile, version))
    session_id = await client.new_session(tenant, agent_id, f"workflow {wf['id']}", spec, workspace_id=wf["id"])
    await rt.cases.bind_session(wf["case_id"], session_id, agent_id, profile.name, "leader")
    await rt.cases.update_case(wf["case_id"], leader_agent_id=agent_id, leader_session_id=session_id)
    return Leader(tenant, agent_id, session_id)
