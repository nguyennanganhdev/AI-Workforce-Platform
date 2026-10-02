"""Coordination session of a ticket: the Supervisor team in the management group chat.

The session is persistence only; no agent runs here. It is opened when the ticket
reaches a management unit that has one workspace, one group chat and one versioned
Supervisor, and it stays open after the resident confirms until management approves.
"""

import json
from typing import Annotated
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_audit import audit
from .v3_auth import scoped_connection
from .v3_mutations import management_access, visible_ticket

router = APIRouter(tags=["Vinhomes V3 coordination session"])
Scope = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection, scope="function")]
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"


async def session_destination(db: AsyncConnection, management_unit_id: object) -> dict[str, object]:
    """Same rule as the Reception handoff: exactly one workspace, group chat and Supervisor."""
    workspaces = (await db.execute(text(f"""
        select id from workspaces where management_unit_id=:unit and tenant_id={TENANT}
          and status='active' order by id limit 2
    """), {"unit": management_unit_id})).scalars().all()
    if len(workspaces) != 1:
        return {"missing": "workspace"}
    channels = (await db.execute(text(f"""
        select id,is_dispatch_default from channels where workspace_id=:workspace
          and tenant_id={TENANT} and kind='management' order by id limit 20
    """), {"workspace": workspaces[0]})).mappings().all()
    channels = [c for c in channels if c["is_dispatch_default"]] or channels
    if len(channels) != 1:
        return {"missing": "group_chat"}
    supervisors = (await db.execute(text(f"""
        select a.id,a.name,v.id as version_id from agents a
        join channel_agents ca on ca.agent_id=a.id and ca.tenant_id=a.tenant_id
        left join lateral (select id from agent_versions where agent_id=a.id and tenant_id=a.tenant_id
          order by version_no desc limit 1) v on true
        where a.workspace_id=:workspace and a.tenant_id={TENANT} and a.status='active'
          and a.purpose='supervisor' and ca.channel_id=:channel order by a.id limit 2
    """), {"workspace": workspaces[0], "channel": channels[0]["id"]})).mappings().all()
    if len(supervisors) != 1 or supervisors[0]["version_id"] is None:
        return {"missing": "supervisor"}
    return {"workspace_id": workspaces[0], "channel_id": channels[0]["id"],
            "supervisor_id": supervisors[0]["id"], "supervisor_version_id": supervisors[0]["version_id"]}


async def ensure_session(db: AsyncConnection, actor: str, ticket_id: UUID) -> None:
    """Open the session for a new ticket; an unconfigured management unit keeps the manual flow."""
    ticket = (await db.execute(text(
        "select management_unit_id,reopen_count from tickets where id=:id"), {"id": ticket_id})).mappings().one()
    destination = await session_destination(db, ticket["management_unit_id"])
    if "missing" in destination:
        return
    tenant = (await db.execute(text("select current_setting('app.tenant_id')"))).scalar_one()
    # Same identifier as the Reception handoff, so a later handoff joins this team.
    team_id = uuid5(NAMESPACE_URL, f"reception-supervisor-team:{tenant}:{destination['channel_id']}:{ticket_id}:{ticket['reopen_count']}")
    created = await db.execute(text(f"""
        insert into agent_teams(id,tenant_id,workspace_id,channel_id,ticket_id,ticket_generation,
          supervisor_agent_id,status,shared_state,requested_by_user_id)
        values (:id,{TENANT},:workspace,:channel,:ticket,:generation,:supervisor,'queued',cast(:state as jsonb),:actor)
        on conflict do nothing returning id
    """), {"id": team_id, "workspace": destination["workspace_id"], "channel": destination["channel_id"],
           "ticket": ticket_id, "generation": ticket["reopen_count"], "supervisor": destination["supervisor_id"],
           "actor": actor, "state": json.dumps({"request": {
               "ticketId": str(ticket_id), "supervisorVersionId": str(destination["supervisor_version_id"]),
               "source": "ticket_created"}})})
    if created.first() is None:
        return
    await db.execute(text(f"""
        insert into team_members(tenant_id,team_id,agent_id,version_id,member_kind,status)
        values ({TENANT},:team,:agent,:version,'supervisor','active') on conflict do nothing
    """), {"team": team_id, "agent": destination["supervisor_id"], "version": destination["supervisor_version_id"]})
    await audit(db, actor, "team.created", "agent_team", str(team_id),
                {"ticketId": str(ticket_id), "source": "ticket_created"})


async def _session(db: AsyncConnection, ticket_id: UUID, *, lock: bool = False):
    row = await db.execute(text(f"""
        select tm.id,tm.status,tm.state_version,tm.channel_id,tm.created_at,tm.finished_at,
          tm.shared_state->'closure' as closure,a.name as supervisor_name
        from agent_teams tm join agents a on a.id=tm.supervisor_agent_id and a.tenant_id=tm.tenant_id
        where tm.ticket_id=:ticket and tm.tenant_id={TENANT}
        order by tm.created_at desc limit 1 {"for update of tm" if lock else ""}
    """), {"ticket": ticket_id})
    return row.mappings().first()


@router.get("/tickets/{ticket_id}/session", summary="Coordination session of a ticket")
async def ticket_session(ticket_id: UUID, scope: Scope) -> dict[str, object]:
    ticket = await visible_ticket(scope, ticket_id)
    session = await _session(scope[0], ticket_id)
    if session is None:
        destination = await session_destination(scope[0], ticket["management_unit_id"])
        return {"session": None, "missing": destination.get("missing")}
    return {"session": dict(session),
            "awaitingManagementApproval": ticket["status"] == "closed" and session["status"] != "completed"}


class SessionClosure(BaseModel):
    version: int = Field(ge=0)
    note: str | None = Field(default=None, max_length=2000)


@router.post("/tickets/{ticket_id}/session/close-approval",
             summary="Management approves and closes the session after the resident confirmed")
async def approve_session_closure(ticket_id: UUID, body: SessionClosure, scope: Scope) -> dict[str, object]:
    ticket = await visible_ticket(scope, ticket_id, lock=True)
    if not await management_access(scope, ticket):
        raise HTTPException(403, "Management grant for this ticket is required")
    session = await _session(scope[0], ticket_id, lock=True)
    if session is None:
        raise HTTPException(404, "This ticket has no coordination session")
    if session["status"] == "completed":
        return {"session": dict(session), "awaitingManagementApproval": False}
    if ticket["status"] != "closed":
        raise HTTPException(409, "The resident must confirm the result before the session is closed")
    if session["state_version"] != body.version or session["status"] in {"failed", "cancelled"}:
        raise HTTPException(409, "Session state or version changed")
    await scope[0].execute(text("""
        update agent_teams set status='completed',state_version=state_version+1,finished_at=now(),
          shared_state=shared_state||jsonb_build_object('closure',cast(:closure as jsonb)) where id=:id
    """), {"id": session["id"], "closure": json.dumps({"approvedBy": scope[1], "note": body.note})})
    await audit(scope[0], scope[1], "team.closure_approved", "agent_team", str(session["id"]),
                {"ticketId": str(ticket_id)})
    return {"session": dict(await _session(scope[0], ticket_id)), "awaitingManagementApproval": False}
