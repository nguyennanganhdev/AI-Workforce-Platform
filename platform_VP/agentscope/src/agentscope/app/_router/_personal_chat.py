"""Persist manual personal groups without model calls or invitability changes."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from ..._utils._common import _generate_id
from .._personal_chat import context_key, group_root
from .._shared_context import SharedContextService
from ..deps import (
    get_current_user_id, get_message_bus, get_resource_access_service,
    get_session_service, get_shared_context_storage, get_storage,
)
from ..access import ResourceKind
from ..storage import ChatModelConfig, ContextDelta, SessionConfig, SessionNaming
from ..storage._model._session import PersonalChatConfig, PersonalChatMember


personal_chat_router = APIRouter(prefix="/personal", tags=["personal-chat"])


class CreateGroup(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    goal: str = Field(default="", max_length=4000)
    agent_ids: list[str] = Field(min_length=2, max_length=20)
    chat_model_config: ChatModelConfig | None = None
    fallback_chat_model_config: ChatModelConfig | None = None

    @model_validator(mode="after")
    def unique_members(self):
        if not self.name.strip() or len(set(self.agent_ids)) != len(self.agent_ids):
            raise ValueError("A group needs a name and distinct agents")
        return self


class ContextChange(BaseModel):
    context_mode: Literal["shared", "isolated"] | None = None
    note: str | None = Field(default=None, min_length=1, max_length=4000)


def group_view(root):
    config = root.config.personal_chat
    return {
        "sessionId": root.id, "agentId": root.agent_id,
        "name": root.config.name, "createdAt": root.created_at,
        "memberIds": [m.agent_id for m in config.members if m.session_id != root.id],
        "members": [m.model_dump() for m in config.members], "goal": config.goal,
    }


async def owned_session(storage, user_id, agent_id, session_id):
    session = await storage.get_session(user_id, agent_id, session_id)
    if session is None or session.user_id != user_id or session.agent_id != agent_id:
        raise HTTPException(404, "Personal conversation not found")
    return session


@personal_chat_router.get("/groups")
async def list_groups(
    user_id=Depends(get_current_user_id), storage=Depends(get_storage),
    access=Depends(get_resource_access_service),
):
    groups = []
    # Include shared definitions, but only sessions owned by this user.
    for agent in await access.list_resource(user_id, ResourceKind.AGENT):
        for session in await storage.list_sessions(user_id, agent.id):
            config = session.config.personal_chat
            if config and config.kind == "group" and config.root_session_id == session.id:
                groups.append(group_view(session))
    return groups


@personal_chat_router.post("/groups", status_code=201)
async def create_group(
    body: CreateGroup, user_id=Depends(get_current_user_id),
    storage=Depends(get_storage), access=Depends(get_resource_access_service),
):
    # Resolve every grant before writing anything. Group membership does not
    # change the agent definition, publication or AgentInvite permissions.
    agents = [await access.resolve_agent(user_id, id_) for id_ in body.agent_ids]
    for model in (body.chat_model_config, body.fallback_chat_model_config):
        if model:
            await access.get_resource(user_id, ResourceKind.CREDENTIAL, model.credential_id)
    members = [PersonalChatMember(agent_id=a.id, session_id=_generate_id(), name=a.data.name) for a in agents]
    root_id = members[0].session_id
    created = []
    try:
        # Publish the root last: a listing cannot see a half-created group.
        for member in [*members[1:], members[0]]:
            await storage.upsert_session(
                user_id=user_id, agent_id=member.agent_id, session_id=member.session_id,
                config=SessionConfig(
                    workspace_id=f"personal-{member.session_id}",
                    name=body.name.strip(), naming=SessionNaming(auto=False),
                    chat_model_config=body.chat_model_config,
                    fallback_chat_model_config=body.fallback_chat_model_config,
                    personal_chat=PersonalChatConfig(
                        kind="group", root_session_id=root_id, members=members,
                        goal=body.goal.strip(),
                    ),
                ),
            )
            created.append(member)
    except BaseException:
        for member in created:
            await storage.delete_session(user_id, member.agent_id, member.session_id)
        raise
    return group_view(await storage.get_session(user_id, members[0].agent_id, root_id))


@personal_chat_router.get("/{session_id}/context")
async def get_context(
    session_id: str, agent_id: str, user_id=Depends(get_current_user_id),
    storage=Depends(get_storage), shared_storage=Depends(get_shared_context_storage),
    access=Depends(get_resource_access_service),
):
    await access.resolve_agent(user_id, agent_id)
    session = await owned_session(storage, user_id, agent_id, session_id)
    if session is None or session.config.personal_chat is None:
        raise HTTPException(404, "Personal conversation not found")
    config = session.config.personal_chat
    result = {
        "kind": config.kind, "context_mode": config.context_mode,
        "private_summary": session.state.summary, "goal": config.goal,
        "revision": 0, "events": [], "summary": None, "metrics": {},
    }
    if config.kind == "group":
        root = await group_root(storage, user_id, session)
        record = await shared_storage.get_team_shared_context(user_id, context_key(user_id, root.id))
        if record:
            result.update(
                revision=record.state.revision,
                events=[e.model_dump(mode="json") for e in record.state.events[-100:]],
                summary=(record.state.summaries[root.id].model_dump(mode="json") if root.id in record.state.summaries else None),
                metrics=record.state.metrics.model_dump(),
            )
    return result


@personal_chat_router.patch("/{session_id}/context")
async def change_context(
    session_id: str, agent_id: str, body: ContextChange,
    user_id=Depends(get_current_user_id), storage=Depends(get_storage),
    shared_storage=Depends(get_shared_context_storage), bus=Depends(get_message_bus),
    access=Depends(get_resource_access_service),
):
    from ..message_bus import MessageBusKeys

    await access.resolve_agent(user_id, agent_id)
    if await bus.is_locked(MessageBusKeys.session_lock(session_id)):
        raise HTTPException(409, "Wait for the current reply before changing personal context")
    # Same lease as ChatService: a sharing change applies at a turn boundary.
    async with bus.acquire_lock(MessageBusKeys.session_lock(session_id), ttl_secs=60):
        session = await owned_session(storage, user_id, agent_id, session_id)
        if session is None or session.config.personal_chat is None:
            raise HTTPException(404, "Personal conversation not found")
        config = session.config.personal_chat
        if config.kind == "group":
            await group_root(storage, user_id, session)
        if body.note and body.note.strip():
            root = await group_root(storage, user_id, session)
            await SharedContextService(shared_storage, bus).append_event(
                user_id=user_id, team_id=context_key(user_id, root.id),
                task_id=root.id, kind="context_update",
                content="User-shared note: " + body.note.strip(),
                source_session_id=session.id,
                delta=ContextDelta(objective=root.config.personal_chat.goal or root.config.name),
            )
        if body.context_mode is not None:
            config = config.model_copy(update={"context_mode": body.context_mode})
            await storage.upsert_session(
                user_id=user_id, agent_id=agent_id, session_id=session_id,
                config=session.config.model_copy(update={"personal_chat": config}),
            )
    return {"status": "saved"}


@personal_chat_router.delete("/groups/{session_id}", status_code=204)
async def delete_group(
    session_id: str, agent_id: str, user_id=Depends(get_current_user_id),
    storage=Depends(get_storage), shared_storage=Depends(get_shared_context_storage),
    service=Depends(get_session_service), access=Depends(get_resource_access_service),
):
    await access.resolve_agent(user_id, agent_id)
    session = await owned_session(storage, user_id, agent_id, session_id)
    if session is None:
        raise HTTPException(404, "Personal group not found")
    root = await group_root(storage, user_id, session)
    # Delete the directory first; a concurrent new run fails root validation.
    members = root.config.personal_chat.members
    for member in sorted(members, key=lambda m: m.session_id != root.id):
        await service.delete_session(user_id, member.agent_id, member.session_id)
    await shared_storage.delete_team_shared_context(user_id, context_key(user_id, root.id))
