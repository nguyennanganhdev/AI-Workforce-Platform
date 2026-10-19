# -*- coding: utf-8 -*-
"""Session router — create, list, update, delete, stream, and get messages."""
import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from ..._utils._common import _describe_exception, _generate_id
from ...mcp import MCPClient
from ..access import ResourceKind
from ..deps import (
    get_chat_service,
    get_current_user_id,
    get_message_bus,
    get_resource_access_service,
    get_session_service,
    get_shared_context_storage,
    get_storage,
    get_workspace_manager,
)
from ._schema import (
    AddTeamMemberRequest,
    CreateSessionRequest,
    CreateSessionResponse,
    InterruptSessionResponse,
    ListMessagesResponse,
    ListSessionsResponse,
    SessionStatusResponse,
    SessionView,
    TeamDetailResponse,
    TeamMemberView,
    UpdateSessionRequest,
)
from ..message_bus import MessageBus, MessageBusKeys
from .._service import (
    AgentView,
    ResourceAccessService,
    ChatService,
    SessionService,
    SessionStatus,
    SessionProjection,
    SubagentHitlProjector,
)
from ..storage import (
    ChatModelConfig,
    SessionKnowledgeConfig,
    TTSModelConfig,
    SessionConfig,
    SessionNaming,
    SessionRecord,
    StorageBase,
    TeamRecord,
)
from ...message import ToolCallState
from ...state import ToolContext
from ..storage._utils import _ensure_team_members, _resolve_team_leader
from ...event import CustomEvent
from ..workspace_manager import WorkspaceManagerBase
from .._shared_context import SharedContextService
from .._bus_ops import publish_session_event
from .._tool import AgentInvite, TeamCreate
from .._tool._agent_invite import _display_name
from ...message import ToolResultState


async def _build_team_detail(
    storage: StorageBase,
    access: ResourceAccessService,
    user_id: str,
    team: TeamRecord,
) -> TeamDetailResponse:
    """Resolve a team's leader agent + member agents into a
    :class:`TeamDetailResponse` for the session list endpoint.

    Args:
        storage (`StorageBase`):
            Application storage. Used to look up the leader session,
            each member agent, and each member's session.
        access (`ResourceAccessService`):
            Resolves roster agents against the viewer's current grants.
        user_id (`str`):
            The owner user id.
        team (`TeamRecord`):
            The team to resolve. Caller has already loaded it.

    Returns:
        `TeamDetailResponse`:
            The team plus its resolved leader and member agents (each
            member paired with its session id when available).
    """
    leader_agent: AgentView | None = None
    leader = await _resolve_team_leader(storage, user_id, team)
    if leader is not None:
        leader_agent = AgentView.model_validate(
            {
                **leader.agent.model_dump(),
                "editable": leader.agent.user_id == user_id,
            },
        )

    members: list[TeamMemberView] = []
    for member in await _ensure_team_members(storage, user_id, team):
        agent = await access.try_resolve_agent(user_id, member.agent_id)
        if agent is None or agent.user_id != member.owner_id:
            continue
        # Use the member's team-scoped session id directly; an invited
        # agent has multiple sessions and only ``member.session_id``
        # belongs to this team. A member whose owner is not the current
        # user was invited from another user's pool — read-only here.
        members.append(
            TeamMemberView(
                agent=AgentView.model_validate(
                    {
                        **agent.model_dump(),
                        "editable": member.owner_id == user_id,
                    },
                ),
                session_id=member.session_id,
            ),
        )

    return TeamDetailResponse(
        team=team,
        leader_agent=leader_agent,
        members=members,
    )


session_router = APIRouter(
    prefix="/sessions",
    tags=["sessions"],
    responses={404: {"description": "Not found"}},
)


@session_router.post(
    "/{session_id}/team/members",
    response_model=TeamDetailResponse,
    summary="Manually add a dormant team member",
)
async def add_team_member(
    session_id: str,
    body: AddTeamMemberRequest,
    agent_id: str = Query(description="Leader agent the session belongs to."),
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    access: ResourceAccessService = Depends(get_resource_access_service),
    message_bus: MessageBus = Depends(get_message_bus),
    workspace_manager: WorkspaceManagerBase = Depends(get_workspace_manager),
    shared_storage: StorageBase = Depends(get_shared_context_storage),
) -> TeamDetailResponse:
    """Reuse the invite primitive without starting a worker or invoking the leader."""
    session = await storage.get_session(user_id, agent_id, session_id)
    if session is None or session.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Session not found.")
    leader = await access.resolve_agent(user_id, agent_id)
    if leader.data.system_role != "leader":
        raise HTTPException(status_code=403, detail="Add members from the leader session.")
    invited = await access.resolve_agent(user_id, body.agent_id)
    if (
        invited.id == leader.id
        or invited.source != "user"
        or invited.data.system_role != "business"
        or invited.data.lifecycle_state != "published"
        or not invited.data.invite_config.invitable
        or not (invited.data.invite_config.invite_description or "").strip()
    ):
        raise HTTPException(status_code=400, detail="Agent is not available for invitation.")

    lock_key = MessageBusKeys.session_lock(session_id)
    if not await message_bus.try_lock(lock_key):
        raise HTTPException(status_code=409, detail="Wait for the current leader operation to finish before adding a member.")
    try:
        shared_context = SharedContextService(shared_storage, message_bus)
        kwargs = dict(
            storage=storage, message_bus=message_bus,
            workspace_manager=workspace_manager, user_id=user_id,
            session_id=session_id, agent_id=agent_id,
            shared_context_service=shared_context,
        )
        session = await storage.get_session(user_id, agent_id, session_id)
        if session is None or session.agent_id != agent_id:
            raise HTTPException(status_code=404, detail="Session not found.")
        created_team = session.team_id is None
        if created_team:
            result = await TeamCreate(**kwargs)(
                name=session.config.name or "Team", description="",
            )
            if result.state == ToolResultState.ERROR:
                raise HTTPException(status_code=400, detail=result.content[0].text)
        try:
            result = await AgentInvite(
                **kwargs, invitable_pool=[invited], resource_access_service=access,
            ).invite_member(
                _display_name(invited.data.name, invited.id),
                invited.data.invite_config.invite_description or "",
                wake=False, start_task=False,
            )
            if result.state == ToolResultState.ERROR:
                raise HTTPException(status_code=400, detail=result.content[0].text)
        except BaseException:
            if created_team:
                # Do not leave an empty team that the leader could still manage.
                created = await storage.get_session(user_id, agent_id, session_id)
                if created is not None and created.team_id is not None:
                    await storage.delete_team(user_id, created.team_id)
                    await storage.set_session_team_id(user_id, session_id, None)
            raise
        session = await storage.get_session(user_id, agent_id, session_id)
        team = await storage.get_team(user_id, session.team_id)
        team.data.manual_membership = True
        await storage.upsert_team(user_id, team)
        await publish_session_event(
            message_bus, session_id,
            CustomEvent(name="team_updated", value={}).model_dump(mode="json"),
        )
        return await _build_team_detail(storage, access, user_id, team)
    finally:
        await message_bus.unlock(lock_key)


async def _ensure_credential_exists(
    access: ResourceAccessService,
    user_id: str,
    config: ChatModelConfig | TTSModelConfig | None,
) -> None:
    """Validate that the credential referenced by ``config`` is visible to
    the given user (own or shared). No-op when ``config`` is ``None``.

    Args:
        access (`ResourceAccessService`): Injected access service.
        user_id (`str`): The authenticated user ID.
        config (`ChatModelConfig | TTSModelConfig | None`): Model config to
            validate. Pass ``None`` to skip the check.

    Raises:
        `HTTPException`: 404 if the credential does not exist or is not
            visible to the user.
    """
    if config is None:
        return
    # ``get_resource`` raises 404 when the credential is neither owned
    # nor shared to the viewer — exactly the semantics we want.
    await access.get_resource(
        user_id,
        ResourceKind.CREDENTIAL,
        config.credential_id,
    )


async def _ensure_knowledge_bases_exist(
    access: ResourceAccessService,
    user_id: str,
    config: SessionKnowledgeConfig | None,
) -> None:
    """Validate every KB id in ``config`` is visible to the given user.

    No-op when ``config`` is ``None`` or its ``knowledge_base_ids``
    list is empty.

    Args:
        access (`ResourceAccessService`): Injected access service.
        user_id (`str`): The authenticated user ID.
        config (`SessionKnowledgeConfig | None`):
            Knowledge config to validate.  Pass ``None`` to skip.

    Raises:
        `HTTPException`: 404 if any KB id is not visible to the user.
    """
    if config is None or not config.knowledge_base_ids:
        return
    for kb_id in config.knowledge_base_ids:
        await access.get_resource(
            user_id,
            ResourceKind.KNOWLEDGE_BASE,
            kb_id,
        )


@session_router.get(
    "/",
    response_model=ListSessionsResponse,
    summary="List sessions for an agent",
)
async def list_sessions(
    agent_id: str = Query(description="Filter sessions by agent ID."),
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    access: ResourceAccessService = Depends(get_resource_access_service),
    message_bus: MessageBus = Depends(get_message_bus),
) -> ListSessionsResponse:
    """Return all sessions for an agent as enriched
    :class:`SessionView` entries.

    Each entry bundles what the chat UI needs to render without
    follow-up requests: the session record, its status, and — when
    the session participates in a team — the resolved team detail
    (leader agent + member agents with their session ids).

    The record arrives trimmed: ``state.context``, ``state.summary``
    and ``state.tool_context`` are cleared, since they hold the model's
    conversation and every file it has read. Fetch a session's messages
    from ``GET /sessions/{id}/messages`` instead.

    Args:
        agent_id (`str`):
            Agent whose sessions to list. May be an agent shared to
            the viewer through :class:`ResourceAccessPolicyBase`;
            the returned sessions are still the viewer's own.
        user_id (`str`):
            Injected authenticated user ID.
        storage (`StorageBase`):
            Injected storage backend.
        access (`ResourceAccessService`):
            Injected resource access service; used to validate that
            the target agent is visible to the viewer.
        message_bus (`MessageBus`):
            Injected message bus (used for ``session_is_running``).

    Returns:
        `ListSessionsResponse`:
            Enriched session views and their count.

    Raises:
        `HTTPException`: 404 if the agent is not visible to the caller.
    """
    # Verify visibility (own or shared) — raises 404 otherwise. Sessions
    # themselves are always looked up under ``user_id``, so a viewer
    # only ever sees their own runs of a shared agent.
    await access.resolve_agent(user_id, agent_id)

    sessions = await storage.list_sessions(user_id, agent_id)
    views: list[SessionView] = []
    for session in sessions:
        team_detail = None
        if session.team_id:
            team_record = await storage.get_team(user_id, session.team_id)
            if team_record is not None:
                team_detail = await _build_team_detail(
                    storage,
                    access,
                    user_id,
                    team_record,
                )
                if team_record.session_id != session.id:
                    leader_session = await storage.get_session(
                        user_id,
                        "",
                        team_record.session_id,
                    )
                    if leader_session is not None:
                        shared_model = (
                            leader_session.config.sub_agent_chat_model_config
                        )
                        if shared_model is not None:
                            session = session.model_copy(
                                update={
                                    "config": session.config.model_copy(
                                        update={
                                            "chat_model_config": shared_model,
                                        }
                                    ),
                                }
                            )
        is_running = await message_bus.is_locked(
            MessageBusKeys.session_lock(session.id),
        )
        # Derived before the trim below, which drops the context it reads.
        session_status = (
            SessionStatus.RUNNING
            if is_running
            else SessionService.derive_parked_status(session.state.context)
        )
        views.append(
            SessionView(
                # ``context`` is the conversation the model sees,
                # ``summary`` its compressed form, and ``tool_context``
                # caches every file read — megabytes a session, none of
                # which a sidebar renders.
                session=session.model_copy(
                    update={
                        "state": session.state.model_copy(
                            update={
                                "context": [],
                                "summary": "",
                                "tool_context": ToolContext(),
                            },
                        ),
                    },
                ),
                is_running=is_running,
                status=session_status,
                team=team_detail,
            ),
        )
    return ListSessionsResponse(sessions=views, total=len(views))


@session_router.post(
    "/",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new session",
)
async def create_session(
    body: CreateSessionRequest,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    workspace_manager: WorkspaceManagerBase = Depends(get_workspace_manager),
    access: ResourceAccessService = Depends(get_resource_access_service),
    session_service: SessionService = Depends(get_session_service),
) -> CreateSessionResponse:
    """Create (or resume) a session for a given agent and workspace.

    At most one session exists per ``(user_id, agent_id, workspace_id)``
    triple — a second call with the same triple updates the existing session
    rather than creating a duplicate.

    Args:
        body (`CreateSessionRequest`): Agent, workspace, and model config.
        user_id (`str`): Injected authenticated user ID.
        storage (`StorageBase`): Injected storage backend.
        workspace_manager (`WorkspaceManagerBase`): Injected workspace
            manager; consulted via
            :meth:`WorkspaceManagerBase.assign_workspace_id` to fill in
            ``workspace_id`` when the request body omits it.
        access (`ResourceAccessService`): Injected access service.

    Returns:
        `CreateSessionResponse`: The session identifier.

    Raises:
        `HTTPException`: 404 if the agent / credential / knowledge base
            is not visible to the caller.
    """
    # Agent must be visible to the caller (own or shared).
    agent_record = await access.resolve_agent(user_id, body.agent_id)

    knowledge_config = body.knowledge_config
    default_knowledge_ids = getattr(agent_record.data, "knowledge_base_ids", [])
    if "knowledge_config" not in body.model_fields_set and default_knowledge_ids:
        knowledge_config = SessionKnowledgeConfig(
            knowledge_base_ids=default_knowledge_ids,
            parameters={"mode": "agentic"},
        )

    await _ensure_credential_exists(access, user_id, body.chat_model_config)
    await _ensure_credential_exists(
        access, user_id, body.sub_agent_chat_model_config
    )
    await _ensure_credential_exists(
        access,
        user_id,
        body.fallback_chat_model_config,
    )
    await _ensure_credential_exists(access, user_id, body.tts_model_config)
    await _ensure_knowledge_bases_exist(
        access,
        user_id,
        knowledge_config,
    )

    # Builder bindings belong to the agent; MCP clients belong to each session.
    mcps: list[MCPClient] | None = None
    if (
        getattr(agent_record.data, "execution_mode", None) is not None
        and agent_record.data.system_role == "business"
        and agent_record.source == "user"
    ):
        selected: dict[str, list[str]] = {}
        for binding in agent_record.data.tool_bindings:
            selected.setdefault(binding["mcp_id"], []).append(binding["tool_name"])
        mcps = []
        for mcp_id, tool_names in selected.items():
            record = await storage.get_mcp(user_id, mcp_id)
            if record is None or not record.enabled:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"MCP {mcp_id} không còn khả dụng.",
                )
            client = MCPClient.model_validate(record.client.model_dump(mode="json"))
            client.enable_tools = list(dict.fromkeys(tool_names))
            mcps.append(client)

    # Resolve the workspace binding for this session. Explicit
    # ``body.workspace_id`` always wins (used by team invite / borrow
    # flows to force sharing); otherwise defer to the manager's
    # isolation policy — see ``WorkspaceManagerBase.assign_workspace_id``.
    resolved_workspace_id = body.workspace_id or (
        await workspace_manager.assign_workspace_id(
            user_id=user_id,
            agent_id=body.agent_id,
            session_id=_generate_id(),
        )
    )

    session_record = await storage.upsert_session(
        user_id=user_id,
        agent_id=body.agent_id,
        config=SessionConfig(
            workspace_id=resolved_workspace_id,
            chat_model_config=body.chat_model_config,
            sub_agent_chat_model_config=body.sub_agent_chat_model_config,
            fallback_chat_model_config=body.fallback_chat_model_config,
            tts_model_config=body.tts_model_config,
            knowledge_config=knowledge_config,
            # A caller that named the session owns that name; anything
            # else starts on the creation timestamp and is the server's
            # to replace once the conversation says what it is about.
            naming=SessionNaming(auto=body.name is None),
            **({"name": body.name} if body.name is not None else {}),
        ),
    )
    if mcps is not None:
        try:
            workspace = await workspace_manager.get_workspace(
                user_id,
                body.agent_id,
                session_record.id,
                resolved_workspace_id,
            )
            for default_mcp in workspace.default_mcps:
                await workspace.remove_mcp(
                    default_mcp.name,
                    agent_id=body.agent_id,
                    session_id=session_record.id,
                )
            for client in mcps:
                await workspace.add_mcp(
                    client,
                    agent_id=body.agent_id,
                    session_id=session_record.id,
                )
        except Exception as exc:
            await session_service.delete_session(user_id, body.agent_id, session_record.id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=_describe_exception(exc),
            ) from exc
    return CreateSessionResponse(session_id=session_record.id)


@session_router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a session",
)
async def delete_session(
    session_id: str,
    agent_id: str = Query(description="Agent the session belongs to."),
    user_id: str = Depends(get_current_user_id),
    session_service: SessionService = Depends(get_session_service),
) -> None:
    """Permanently delete a session and all its associated state.

    Cancels any in-flight chat run for this session (and for every
    worker session if this one is a team leader) before dropping
    storage records and bus state. The cancel path is cross-process:
    whichever worker is actually running the session will receive the
    cancel broadcast and abort.

    Args:
        session_id (`str`): The session to delete.
        agent_id (`str`): The agent the session belongs to.
        user_id (`str`): Injected authenticated user ID.
        session_service (`SessionService`): Injected session service.

    Raises:
        `HTTPException`: 404 if the session does not exist or does not belong
            to the authenticated user.
    """
    deleted = await session_service.delete_session(
        user_id,
        agent_id,
        session_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )


@session_router.post(
    "/{session_id}/interrupt",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Interrupt a running or HITL-parked chat run for a session",
    responses={
        404: {"description": "Session not found."},
    },
)
async def interrupt_session(
    session_id: str,
    agent_id: str = Query(description="Agent the session belongs to."),
    user_id: str = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service),
) -> InterruptSessionResponse:
    """Request interruption of an in-progress reply for a session.

    Thin HTTP wrapper around :meth:`ChatService.interrupt`; see that
    method for the running vs not-running dispatch. Idempotent — an
    idle target session is a silent no-op at the agent layer.

    Args:
        session_id: The session whose reply should be interrupted.
        agent_id: The agent that owns the session.
        user_id: Injected authenticated user id.
        chat_service: Injected chat service.

    Returns:
        202 with :class:`InterruptSessionResponse` echoing the
        session id.

    Raises:
        HTTPException: 404 if the session does not exist.
    """
    try:
        await chat_service.interrupt(user_id, session_id, agent_id)
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    return InterruptSessionResponse(session_id=session_id)


@session_router.patch(
    "/{session_id}",
    response_model=SessionRecord,
    summary="Update a session",
)
async def update_session(
    session_id: str,
    body: UpdateSessionRequest,
    agent_id: str = Query(description="Agent the session belongs to."),
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    access: ResourceAccessService = Depends(get_resource_access_service),
    message_bus: MessageBus = Depends(get_message_bus),
) -> SessionRecord:
    """Update the configuration of an existing session.

    Rejected while a chat run holds the session: the agent snapshots
    its configuration once at run start, so a mid-run change would be
    ignored for the current reply anyway — and writing it would race
    the run's own state persistence.

    Args:
        session_id (`str`): The session to update.
        body (`UpdateSessionRequest`): Fields to update.
        user_id (`str`): Injected authenticated user ID.
        storage (`StorageBase`): Injected storage backend.
        access (`ResourceAccessService`): Injected access service.
        message_bus (`MessageBus`): Injected message bus; used to
            detect an in-flight run.

    Returns:
        `SessionRecord`: The full session record after the update.

    Raises:
        `HTTPException`: 404 if the session does not exist, or if the
            referenced credential / KB is not visible to the caller;
            409 if a chat run is currently active on the session.
    """
    existing = await storage.get_session(user_id, agent_id, session_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    # Checked after the 404 so a missing session reports as missing, and
    # before the validation round trips below so we fail fast.
    if await message_bus.is_locked(MessageBusKeys.session_lock(session_id)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Cannot modify session configuration while the session "
                "is running."
            ),
        )

    if (
        "sub_agent_chat_model_config" in body.model_fields_set
        and existing.team_id
    ):
        team = await storage.get_team(user_id, existing.team_id)
        if team is not None:
            if team.session_id != session_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Change the shared sub-agent model from the leader session.",
                )
            for member in await _ensure_team_members(storage, user_id, team):
                if await message_bus.is_locked(
                    MessageBusKeys.session_lock(member.session_id),
                ):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Cannot modify the sub-agent model while a team member is running.",
                    )

    await _ensure_credential_exists(access, user_id, body.chat_model_config)
    await _ensure_credential_exists(
        access, user_id, body.sub_agent_chat_model_config
    )
    await _ensure_credential_exists(
        access,
        user_id,
        body.fallback_chat_model_config,
    )
    await _ensure_credential_exists(access, user_id, body.tts_model_config)
    await _ensure_knowledge_bases_exist(
        access,
        user_id,
        body.knowledge_config,
    )

    # ``None`` leaves the stored state untouched (see
    # ``StorageBase.upsert_session``). ``permission_mode`` is the only
    # request field living inside ``state``; every other field is a
    # pure config write, and rewriting ``state`` for those would put
    # this handler's opening snapshot back over whatever the run has
    # persisted since.
    updated_state = None
    if body.permission_mode is not None:
        updated_ctx = existing.state.permission_context.model_copy(
            update={"mode": body.permission_mode},
        )

        updated_state = existing.state.model_copy(
            update={
                "permission_context": updated_ctx,
            },
        )

    # PATCH semantics: only fields explicitly present in the request body are
    # applied. ``exclude_unset=True`` lets clients distinguish "leave
    # unchanged" (omit) from "clear" (send ``null``) — required for clearing
    # ``fallback_chat_model_config``.
    config_updates = body.model_dump(
        exclude_unset=True,
        exclude={"permission_mode"},
    )

    # An explicit rename settles the name for good — auto-naming must
    # not overwrite what the user just typed.
    if "name" in config_updates:
        config_updates["naming"] = {
            **existing.config.naming.model_dump(),
            "auto": False,
        }

    return await storage.upsert_session(
        user_id=user_id,
        agent_id=agent_id,
        config=SessionConfig.model_validate(
            {**existing.config.model_dump(mode="json"), **config_updates},
        ),
        state=updated_state,
        session_id=session_id,
    )


# ----------------------------------------------------------------------
# Messages: fetch persisted messages for a session
# ----------------------------------------------------------------------


@session_router.get(
    "/{session_id}/messages",
    response_model=ListMessagesResponse,
    summary="List messages for a session",
)
async def list_messages(
    session_id: str,
    agent_id: str = Query(description="Agent the session belongs to."),
    before: str
    | None = Query(
        None,
        description=(
            "A message ID used as the pagination cursor. Omit to get "
            "the latest page. Provide a message ID from a previous "
            "response to load older messages."
        ),
    ),
    offset: int
    | None = Query(
        None,
        deprecated=True,
        description=(
            "**Deprecated.** Use ``before`` for cursor-based pagination. "
            "This parameter is always ignored."
        ),
    ),
    limit: int = Query(50, ge=1, le=200, description="Max messages."),
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    message_bus: MessageBus = Depends(get_message_bus),
) -> ListMessagesResponse:
    """Return persisted messages for a session with cursor-based
    pagination.

    Args:
        session_id: The session to query.
        agent_id: Agent the session belongs to.
        before: A message ID used as the pagination cursor. Omit for
            the latest page; provide a message ID from a previous
            response to load older messages.
        offset: **Deprecated.** Numeric offset, always ignored. Still
            accepted for backward compatibility.
        limit: Maximum number of messages to return.
        user_id: Injected authenticated user ID.
        storage: Injected storage backend.
        message_bus: Injected message bus.

    Returns:
        Messages, running status, and whether more pages exist.
    """
    existing = await storage.get_session(user_id, agent_id, session_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    # Forward deprecated offset via kwargs so storage can warn.
    extra: dict = {}
    if offset is not None:
        extra["offset"] = offset

    messages, has_more = await storage.list_messages(
        user_id,
        session_id,
        limit=limit,
        before=before,
        **extra,
    )
    return ListMessagesResponse(
        messages=messages,
        is_running=await message_bus.is_locked(
            MessageBusKeys.session_lock(session_id),
        ),
        has_more=has_more,
    )


# ----------------------------------------------------------------------
# Status probe: unified session status (cluster liveness + parking state)
# ----------------------------------------------------------------------


@session_router.get(
    "/{session_id}/status",
    response_model=SessionStatusResponse,
    summary="Probe the session's high-level status",
)
async def get_session_status(
    session_id: str,
    agent_id: str = Query(description="Agent the session belongs to."),
    user_id: str = Depends(get_current_user_id),
    session_service: SessionService = Depends(get_session_service),
) -> SessionStatusResponse:
    """Return the unified :class:`SessionStatus` for a session.

    Ownership validation, cluster-liveness probing, and parked-state
    derivation are all delegated to
    :meth:`SessionService.get_session_status` — see that method for
    the precedence rules that collapse the two orthogonal signals
    (message-bus run lock + persisted context tail) into a single
    four-valued enum.

    Args:
        session_id (`str`):
            The session to probe.
        agent_id (`str`):
            The agent that owns the session (ownership validation).
        user_id (`str`):
            Injected authenticated user ID.
        session_service (`SessionService`):
            Injected session service. Owns both storage and message
            bus dependencies so the composed answer is derived in a
            single layer.

    Returns:
        `SessionStatusResponse`:
            The probed session id and its unified status.

    Raises:
        `HTTPException`: 404 if the session does not exist or does not
            belong to the authenticated user.
    """
    session_status = await session_service.get_session_status(
        user_id,
        agent_id,
        session_id,
    )
    if session_status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return SessionStatusResponse(
        session_id=session_id,
        status=session_status,
    )


# ----------------------------------------------------------------------
# Stream: live SSE connection for session events
# ----------------------------------------------------------------------

_HEARTBEAT_INTERVAL_SECS = 30
# Interval between SSE heartbeat comment frames (``:\\n\\n``).


async def _worker_still_asking(
    storage: StorageBase,
    user_id: str,
    worker_agent_id: str,
    worker_session_id: str,
    reply_id: str,
) -> bool:
    """Return whether a worker session is still parked on the ASKING
    tool call identified by ``reply_id``.

    This is the reconcile-on-read check (design §3.5): the worker
    session's own ``state.context`` is the single source of truth for
    "does this confirmation still need answering". A leader-side
    pending projection whose worker has already resolved / cancelled
    the call is a ghost and must not be replayed.

    Mirrors the wakeup guard in
    :meth:`ChatService._run_impl` — a request is "still asking" when
    the tail ``AssistantMsg`` of the worker carries a tool call in
    ``ASKING`` or ``SUBMITTED`` state for the matching ``reply_id``.

    Args:
        storage (`StorageBase`):
            Application storage.
        user_id (`str`):
            The owner user id.
        worker_agent_id (`str`):
            The worker agent that owns the session.
        worker_session_id (`str`):
            The worker session to inspect.
        reply_id (`str`):
            The reply id the pending request belongs to.

    Returns:
        `bool`:
            ``True`` if the worker is still awaiting confirmation for
            ``reply_id``; ``False`` otherwise (resolved, cancelled, or
            the session/record is gone).
    """
    session = await storage.get_session(
        user_id,
        worker_agent_id,
        worker_session_id,
    )
    if session is None or not session.state.context:
        return False
    last_msg = session.state.context[-1]
    if last_msg.role != "assistant" or last_msg.id != reply_id:
        return False
    return any(
        tc.state in (ToolCallState.ASKING, ToolCallState.SUBMITTED)
        for tc in last_msg.get_content_blocks("tool_call")
    )


@session_router.get(
    "/{session_id}/stream",
    summary="Subscribe to a session's event stream (SSE)",
    response_description="Server-Sent Events stream of AgentEvent objects",
)
async def stream_session_events(
    session_id: str,
    agent_id: str = Query(description="Agent the session belongs to."),
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    message_bus: MessageBus = Depends(get_message_bus),
) -> StreamingResponse:
    """Subscribe to a session's live event stream.

    Returns a ``text/event-stream`` that first replays any buffered
    events from the current run's replay log (if a run is in progress
    or just finished), then streams live events as they are produced
    by :meth:`ChatService.run`. The connection stays open
    until the client disconnects — subsequent runs on the same session
    are delivered over the same connection.

    A heartbeat comment frame (``:\\n\\n``) is sent every 30 seconds to
    keep the connection alive through reverse proxies.

    Args:
        session_id (`str`):
            The session to subscribe to.
        agent_id (`str`):
            The agent that owns the session (used for ownership
            validation).
        user_id (`str`):
            Injected authenticated user id.
        storage (`StorageBase`):
            Injected storage backend (ownership check only).
        message_bus (`MessageBus`):
            Injected message bus (replay + live subscription).

    Returns:
        `StreamingResponse`:
            SSE stream of AgentEvent frames + periodic heartbeats.
    """
    existing = await storage.get_session(user_id, agent_id, session_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    async def _sse_generator() -> AsyncGenerator[str, None]:
        # 1. Replay buffered events from the current run (if any).
        for _entry_id, event in await message_bus.log_read(
            MessageBusKeys.session_events(session_id),
            max_count=MessageBusKeys.SESSION_REPLAY_MAX_LEN,
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        # 1b. Inject pending subagent HITL cards projected onto this
        #     session as a team leader (design §3.5). These live in a
        #     durable Redis hash — NOT in the replay log (trimmed per
        #     run) nor in the leader's own Msg history — so a fresh
        #     reconnect after the worker parked still surfaces them.
        #
        #     Reconcile-on-read: the worker session's own context is the
        #     SSOT. Inject only when the worker is still ASKING; drop and
        #     delete ghosts (worker resolved/cancelled without clearing).
        projection = SessionProjection(message_bus)
        for payload in await projection.list(
            session_id,
            SubagentHitlProjector.KIND,
        ):
            if not await _worker_still_asking(
                storage,
                user_id,
                payload["worker_agent_id"],
                payload["worker_session_id"],
                payload["reply_id"],
            ):
                await projection.delete(
                    session_id,
                    SubagentHitlProjector.KIND,
                    SubagentHitlProjector.entry_id(
                        payload["worker_session_id"],
                        payload["reply_id"],
                    ),
                )
                continue
            custom = CustomEvent(
                name=SubagentHitlProjector.EVT_REQUIRE,
                value=payload,
            )
            data = json.dumps(
                custom.model_dump(mode="json"),
                ensure_ascii=False,
            )

            yield f"data: {data}\n\n"

        # 2. Live subscribe via a background feeder task that pushes
        #    events into a queue. The main loop reads from the queue
        #    with a timeout so we can interleave heartbeat frames.
        #
        #    We avoid calling ``wait_for(__anext__())`` on the async
        #    generator directly because cancelling a suspended
        #    ``__anext__`` leaves the generator in a "running" state
        #    that prevents ``aclose()`` from working.
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        async def _feeder() -> None:
            """Read from the bus subscription and forward to the queue.

            Pushes ``None`` as a sentinel when the subscription ends
            (which in practice only happens if the bus shuts down).
            """
            try:
                async for evt in message_bus.subscribe(
                    MessageBusKeys.session_events(session_id),
                ):
                    await queue.put(
                        {k: v for k, v in evt.items() if k != "_entry_id"},
                    )
            except asyncio.CancelledError:
                pass
            finally:
                await queue.put(None)

        feeder_task = asyncio.create_task(
            _feeder(),
            name=f"sse-feeder:{session_id}",
        )

        try:
            while True:
                try:
                    item = await asyncio.wait_for(
                        queue.get(),
                        timeout=_HEARTBEAT_INTERVAL_SECS,
                    )
                    if item is None:
                        break
                    yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ":\n\n"
        finally:
            feeder_task.cancel()
            try:
                await feeder_task
            except asyncio.CancelledError:
                pass

    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
