# -*- coding: utf-8 -*-
"""Chat router — fire-and-forget trigger for chat runs.

The endpoint no longer returns an SSE stream. Instead, it kicks off a
chat run as a background task and returns immediately. Events produced
by the run are published to the message bus and delivered to the
frontend via the long-lived ``GET /sessions/{sid}/stream`` SSE
connection provided by the session router.

Two trigger paths, deliberately asymmetric:

- **New user message(s)** are spawned directly into the
  :class:`ChatRunRegistry`. The registry's single-run-per-session rule
  surfaces as a 409, which is exactly the desired double-submit guard.
- **HITL results** (``UserConfirmResultEvent`` /
  ``ExternalExecutionResultEvent``) are *enqueued* onto the shared
  run-trigger queue and drained by the single
  :class:`WakeupDispatcher`. Routing the resume through the queue keeps
  the dispatcher the sole spawn site, so a resume can never collide with
  the worker's still-finishing parked run (the old 409 race) — the
  dispatcher serialises them.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import (
    get_chat_run_registry,
    get_chat_service,
    get_current_user_id,
    get_message_bus,
    get_storage,
    get_shared_context_storage,
)
from ._schema import ChatRequest, ChatTriggerResponse
from .._manager import ChatRunRegistry
from .._service import (
    ChatService,
    SessionProjection,
    SubagentHitlProjector,
)
from ..message_bus import MessageBus, MessageBusKeys
from .._bus_ops import enqueue_run_trigger
from .._chat_consent import (
    parse_chat_consent,
    pending_chat_actions,
    resolve_chat_consent,
)
from .._team_turn import get_team_turn, start_team_turn
from .._tool._constants import HANDLE_LEN
from ..storage import StorageBase
from ..storage._utils import _ensure_team_members, _resolve_team_leader
from ...event import UserConfirmResultEvent, ExternalExecutionResultEvent
from ...message import AssistantMsg, Msg
from ..._utils._common import _generate_id

chat_router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    responses={404: {"description": "Not found"}},
)


def _strip_leading_mention(message: Msg, display_name: str) -> Msg:
    """Return a copy with one exact leading ``@display_name`` removed."""
    copied = message.model_copy(deep=True)
    prefix = f"@{display_name}"
    for block in copied.content:
        if block.type != "text":
            continue
        text = block.text.lstrip()
        if not text.casefold().startswith(prefix.casefold()):
            break
        boundary = text[len(prefix) : len(prefix) + 1]
        if boundary and not boundary.isspace() and boundary not in ":,-":
            break
        block.text = text[len(prefix) :].lstrip(" :,-")
        break
    return copied


def _match_leading_mention(
    message: Msg,
    candidates: list[tuple[str, str, str]],
) -> tuple[str, str, str] | None:
    """Resolve a leading team-member mention, preferring longest name."""
    text = (message.get_text_content() or "").lstrip()
    for candidate in sorted(candidates, key=lambda item: len(item[2]), reverse=True):
        prefix = f"@{candidate[2]}"
        if not text.casefold().startswith(prefix.casefold()):
            continue
        boundary = text[len(prefix) : len(prefix) + 1]
        if not boundary or boundary.isspace() or boundary in ":,-":
            return candidate
    return None


@chat_router.post(
    "/",
    response_model=ChatTriggerResponse,
    summary="Trigger a chat run (fire-and-forget)",
)
async def chat(
    request: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service),
    chat_run_registry: ChatRunRegistry = Depends(get_chat_run_registry),
    message_bus: MessageBus = Depends(get_message_bus),
    storage: StorageBase = Depends(get_storage),
    shared_context_storage: StorageBase = Depends(get_shared_context_storage),
) -> ChatTriggerResponse:
    """Trigger a chat run for the specified session.

    Events produced during the run are published to the message bus and
    delivered to any active ``GET /sessions/{session_id}/stream`` SSE
    subscriber. The caller does **not** receive events from this
    endpoint's response body.

    Accepts the same ``input`` payloads as before:

    - ``Msg`` / ``list[Msg]``: new user message(s) — spawned directly.
    - ``UserConfirmResultEvent`` / ``ExternalExecutionResultEvent``:
      resume a paused tool call (human-in-the-loop) — routed to the
      owning session and enqueued for the dispatcher.
    - ``None``: continue from current state — spawned directly.

    Args:
        request (`ChatRequest`):
            JSON body with ``agent_id``, ``session_id``, and ``input``.
        user_id (`str`):
            Injected user id.
        chat_service (`ChatService`):
            Injected application-wide chat service.
        chat_run_registry (`ChatRunRegistry`):
            Injected per-process chat-run registry.
        message_bus (`MessageBus`):
            Injected message bus, used to resolve subagent-confirm
            routing and to enqueue resume triggers.

    Returns:
        `ChatTriggerResponse`:
            Confirms the run was scheduled (for a resume, that it was
            enqueued).

    Raises:
        `HTTPException`:
            409 if a chat run for this session is already in flight in
            this process (the registry enforces single-run-per-session).
            Only direct-spawn paths (new messages / ``None``) can raise
            this; the enqueued resume path never does.
    """
    # User prose is resolved by the server against stored ASKING calls, never
    # by an LLM or a client-supplied tool payload. Each decision grants one call.
    if isinstance(request.input, Msg) and not request.new_task:
        consent = parse_chat_consent(request.input.get_text_content() or "")
        pending = await pending_chat_actions(
            storage, user_id, request.agent_id, request.session_id,
        )
        if request.target_agent_id:
            pending = [
                item
                for item in pending
                if item.agent_id == request.target_agent_id
            ]
        if pending:
            resolved = resolve_chat_consent(request.input, pending)
            if resolved is not None:
                action, decision = resolved
                await storage.upsert_message(user_id, request.session_id, request.input)
                await enqueue_run_trigger(
                    message_bus,
                    user_id=user_id,
                    session_id=action.session_id,
                    agent_id=action.agent_id,
                    kind=MessageBusKeys.WAKEUP_KIND_RESUME,
                    inputs=decision,
                )
                return ChatTriggerResponse(status="started", session_id=action.session_id)
            if pending:
                # Keep the parked calls unchanged when a reply is ambiguous.
                # This also prevents a normal message from entering a parked
                # worker and causing the old "received no event" reply failure.
                text = (
                    "Đang có thao tác chờ quyết định và hệ thống chưa thực hiện "
                    "thao tác đó. Vui lòng bấm “Xác nhận” hoặc “Từ chối” trên "
                    "thẻ thao tác trước khi gửi yêu cầu khác."
                )
                answer = AssistantMsg(name="System", content=text)
                await storage.upsert_message(user_id, request.session_id, request.input)
                await storage.upsert_message(user_id, request.session_id, answer)
                return ChatTriggerResponse(
                    status="awaiting_confirmation", session_id=request.session_id,
                    message=answer,
                )
        elif consent is not None:
            answer = AssistantMsg(
                name="System",
                content=(
                    "Hiện không có thao tác nào đang chờ xác nhận hoặc từ chối. "
                    "Hệ thống chưa thực hiện thêm nghiệp vụ nào. Vui lòng nêu rõ "
                    "thao tác bạn muốn thực hiện."
                ),
            )
            await storage.upsert_message(user_id, request.session_id, request.input)
            await storage.upsert_message(user_id, request.session_id, answer)
            return ChatTriggerResponse(
                status="no_pending_confirmation",
                session_id=request.session_id,
                message=answer,
            )

    # ------------------------------------------------------------------
    # HITL resume — route to the owning session, then enqueue.
    #
    # A confirmation / external-result POSTed to a *leader* session may
    # actually belong to a team *member*: the leader is the single front
    # door clients talk to. Resolve the owning worker HERE, then enqueue
    # a ``resume`` trigger for that session. The single WakeupDispatcher
    # drains it — spawning under the *worker* session id, serialised
    # behind any still-finishing parked run, so there is no registry
    # collision (no 409) and the leader's run slot is never occupied by
    # the worker's resume.
    # ------------------------------------------------------------------
    if isinstance(
        request.input,
        (UserConfirmResultEvent, ExternalExecutionResultEvent),
    ):
        run_session_id = request.session_id
        run_agent_id = request.agent_id
        target = await SubagentHitlProjector.resolve(
            SessionProjection(message_bus),
            request.session_id,
            request.input.reply_id,
        )
        if target is not None:
            run_session_id = target["worker_session_id"]
            run_agent_id = target["worker_agent_id"]

        await enqueue_run_trigger(
            message_bus,
            user_id=user_id,
            session_id=run_session_id,
            agent_id=run_agent_id,
            kind=MessageBusKeys.WAKEUP_KIND_RESUME,
            inputs=request.input,
        )
        return ChatTriggerResponse(status="started", session_id=run_session_id)

    # ------------------------------------------------------------------
    # New user message(s). A normal team turn belongs to the leader. An
    # explicit leading @mention transfers reply ownership to that member for
    # this turn; every collaborator remains internal.
    # ------------------------------------------------------------------
    run_session_id = request.session_id
    run_agent_id = request.agent_id
    run_input = request.input
    customer_session_id = request.session_id
    customer_message: Msg | None = None
    team_turn_start: tuple[
        str,
        str,
        str,
        str,
        Literal["leader", "direct_mention"],
        str | None,
    ] | None = None
    session = await storage.get_session(
        user_id,
        request.agent_id,
        request.session_id,
    )
    if request.target_agent_id is not None and (
        session is None or session.team_id is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target_agent_id requires an existing team session.",
        )
    if session is not None and session.team_id is not None:
        team = await storage.get_team(user_id, session.team_id)
        leader = (
            await _resolve_team_leader(storage, user_id, team)
            if team is not None
            else None
        )
        if team is not None and leader is not None:
            previous_turn = await get_team_turn(
                message_bus,
                team.id,
                storage=shared_context_storage,
                user_id=user_id,
            )
            context_record = await shared_context_storage.get_team_shared_context(
                user_id,
                team.id,
            )
            selected_task_id = request.task_id
            if request.in_reply_to is not None:
                parent = next(
                    (
                        event
                        for event in (
                            context_record.state.events if context_record else ()
                        )
                        if event.id == request.in_reply_to
                    ),
                    None,
                )
                if parent is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="in_reply_to does not belong to this team.",
                    )
                if selected_task_id is not None and parent.task_id != selected_task_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="in_reply_to belongs to a different task.",
                    )
                selected_task_id = parent.task_id
            if selected_task_id is not None and (
                context_record is None
                or selected_task_id not in context_record.state.tasks
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="task_id does not belong to this team.",
                )
            if request.new_task:
                selected_task_id = _generate_id()
            if selected_task_id is None and previous_turn is not None:
                selected_task_id = previous_turn.task_id
            if (
                request.in_reply_to is None
                and previous_turn is not None
                and previous_turn.status == "awaiting_user_input"
                and len(previous_turn.pending_question_ids) == 1
            ):
                request.in_reply_to = previous_turn.pending_question_ids[0]

            input_messages = (
                [run_input]
                if isinstance(run_input, Msg)
                else run_input
                if isinstance(run_input, list)
                else []
            )
            for input_message in input_messages:
                input_message.metadata = {
                    **input_message.metadata,
                    "shared_context_task_id": selected_task_id,
                    "shared_context_in_reply_to": request.in_reply_to,
                }
            candidates: list[tuple[str, str, str]] = [
                (leader.agent.id, leader.session_id, leader.name),
            ]
            resolved_members = []
            for member in await _ensure_team_members(storage, user_id, team):
                member_agent = await storage.get_agent(
                    member.owner_id,
                    member.agent_id,
                )
                if member_agent is None:
                    continue
                resolved_members.append((member, member_agent))

            all_names = [
                leader.name.casefold(),
                *(agent.data.name.casefold() for _, agent in resolved_members),
            ]
            for member, member_agent in resolved_members:
                display_name = member_agent.data.name
                if (
                    member.role != "invited"
                    or all_names.count(display_name.casefold()) == 1
                ):
                    candidates.append(
                        (member.agent_id, member.session_id, display_name),
                    )
                if member.role == "invited":
                    candidates.append(
                        (
                            member.agent_id,
                            member.session_id,
                            display_name
                            + f"@{member.agent_id[:HANDLE_LEN]}",
                        ),
                    )

            target = None
            if request.target_agent_id is not None:
                target = next(
                    (
                        candidate
                        for candidate in candidates
                        if candidate[0] == request.target_agent_id
                    ),
                    None,
                )
                if target is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="target_agent_id is not a member of this team.",
                    )
            elif isinstance(run_input, Msg):
                target = _match_leading_mention(run_input, candidates)

            # A plain answer continues with a directly mentioned reply owner.
            # Internal worker questions remain Leader-mediated.
            target_mode: Literal["direct_mention"] = "direct_mention"
            if (
                target is None
                and previous_turn is not None
                and previous_turn.status == "awaiting_user_input"
                and previous_turn.mode == "direct_mention"
                and previous_turn.customer_session_id == request.session_id
            ):
                target = next(
                    (
                        candidate
                        for candidate in candidates
                        if candidate[1]
                        == previous_turn.reply_owner_session_id
                    ),
                    None,
                )
                target_mode = previous_turn.mode

            if target is not None:
                run_agent_id, run_session_id, display_name = target
                if isinstance(run_input, Msg):
                    # Preserve the visible @message in the leader transcript,
                    # while giving the addressed worker a clean request.
                    if customer_session_id != run_session_id:
                        customer_message = run_input
                    run_input = _strip_leading_mention(
                        run_input,
                        display_name,
                    )
                    run_input.metadata = {
                        **run_input.metadata,
                        "team_turn_mode": target_mode,
                        "reply_owner_agent_id": run_agent_id,
                    }
                team_turn_start = (
                    team.id,
                    run_session_id,
                    run_agent_id,
                    customer_session_id,
                    target_mode,
                    selected_task_id,
                )
            else:
                # Plain customer prose always enters through the Leader, even
                # if the request originated from a worker session. Only an
                # explicit mention/target grants that worker reply ownership.
                run_agent_id = leader.agent.id
                run_session_id = leader.session_id
                if customer_session_id != leader.session_id and isinstance(
                    run_input,
                    Msg,
                ):
                    customer_message = run_input
                team_turn_start = (
                    team.id,
                    leader.session_id,
                    leader.agent.id,
                    customer_session_id,
                    "leader",
                    selected_task_id,
                )

    existing = chat_run_registry.get(run_session_id)
    if existing is not None and not existing.done():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Session {run_session_id!r} already has an active chat "
                "run in this process."
            ),
        )
    async def _run_chat() -> None:
        if customer_message is not None:
            await storage.upsert_message(
                user_id,
                customer_session_id,
                customer_message,
            )
        if team_turn_start is not None:
            (
                team_id,
                owner_session_id,
                owner_agent_id,
                customer_id,
                mode,
                task_id,
            ) = team_turn_start
            await start_team_turn(
                message_bus,
                team_id,
                reply_owner_session_id=owner_session_id,
                reply_owner_agent_id=owner_agent_id,
                customer_session_id=customer_id,
                mode=mode,
                task_id=task_id,
                storage=shared_context_storage,
                user_id=user_id,
            )
        await chat_service.run(
            user_id=user_id,
            session_id=run_session_id,
            agent_id=run_agent_id,
            input_msg=run_input,
        )

    run_coro = _run_chat()
    try:
        chat_run_registry.spawn(
            run_coro,
            session_id=run_session_id,
        )
    except RuntimeError as e:
        run_coro.close()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    return ChatTriggerResponse(
        status="started",
        session_id=run_session_id,
    )
