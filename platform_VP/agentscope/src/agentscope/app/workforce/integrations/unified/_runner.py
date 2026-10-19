"""LeaderTurnRunner that runs the console Leader for a partner workflow.

Unified mode (decided 14/10/2026): a partner ticket is handled by exactly the
same runtime as a ticket opened in the web console — the fixed Workforce
Leader, the business agents published in Agent Studio, Shared Context, the
evidence gate, chat consent and the learning loop. The partner workflow
engine (durable requests, bindings, SSE, close) stays in charge of the
conversation lifecycle; this runner is the bridge between the two.

Each workflow gets its own Leader session (the pinned ``session_ref``), so two
tickets of the same customer never share context.
"""

from __future__ import annotations

import asyncio
import base64
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from ....._logging import logger
from .....event import ConfirmResult, UserConfirmResultEvent
from .....message import Base64Source, DataBlock, TextBlock, UserMsg
from ...._chat_consent import pending_chat_actions, resolve_chat_consent
from ...contracts import AssistantMessage, RequestResult, WorkflowState
from ...orchestration._tables import workflow_inputs
from ...orchestration.workflows import TurnDecision
from ...orchestration.workflows.phase_a import RuntimeTurnResult

LEADER_VERSION_ID = "console-leader"
# The end user's photos shown to the route leader per turn, and their size cap.
MAX_IMAGES_PER_TURN = 4
MAX_IMAGE_BYTES = 5 * 1024 * 1024
# Turn retries after a transient model error (rate limit, provider 5xx,
# network); a model without credit is not retried.
MAX_MODEL_RETRIES = 2
TRANSIENT_ERRORS = {"rate_limit", "upstream", "connection"}
ATTENTION_REASONS = {
    "quota": "Tài khoản model đã hết tiền (hết hạn mức API). Nạp tiền hoặc đổi key, rồi chạy lại phiếu.",
    "authentication": "Key model không hợp lệ. Kiểm tra credential của tài khoản.",
    "permission": "Key model không có quyền dùng model này. Kiểm tra credential của tài khoản.",
    "context_budget": "Phiếu vượt ngân sách context của Leader.",
    "collaboration_limit": "Phòng vượt giới hạn trao đổi giữa các agent.",
}


def attention_reason(error: str | None) -> str:
    """Why a partner turn needs a person, in the words the room shows."""

    if error is None:
        return "Leader không gửi tin nào cho người dùng trong lượt này."
    if error in TRANSIENT_ERRORS:
        return f"Lỗi model tạm thời ({error}) vẫn còn sau {MAX_MODEL_RETRIES} lần chạy lại."
    return ATTENTION_REASONS.get(error, f"Lỗi model: {error}.")


def ticket_title(text: str | None, fields: list[str]) -> str:
    """A readable ticket name from the handover's ``field: value`` lines the
    partner declared (route config ``ticket_title_fields``)."""

    values = {}
    for line in (text or "").splitlines():
        key, sep, value = line.partition(":")
        if sep and value.strip():
            values.setdefault(key.strip().casefold(), value.strip())
    parts = [values[field.casefold()] for field in fields if field.casefold() in values]
    title = " · ".join(parts)
    return title if len(title) <= 80 else title[:79].rstrip() + "…"


# Values a handover writes when it has nothing to say; the Leader need not read them.
EMPTY_VALUES = {"", "unknown", "none", "null", "n/a"}


def _handover_fields(text: str) -> dict[str, tuple[str, str]]:
    """``field: value`` lines by casefolded field, first one wins."""

    fields: dict[str, tuple[str, str]] = {}
    for line in text.splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip():
            fields.setdefault(key.strip().casefold(), (key.strip(), value.strip()))
    return fields


def ticket_brief(text: str | None, spec: dict | None) -> tuple[str | None, dict | None]:
    """What the Leader reads of a handover, and what the room shows of it.

    The route declares ``ticket_input``: ``fields`` (what the Leader reads,
    in that order), ``request`` (what the person asked, shown on the
    ticket card) and ``facts`` (a few short values shown beside it).
    Lines it does not list, and fields with an empty value, are left out:
    standing rules belong in the route's ``leader_brief``, which is cached.
    Without a declaration the handover passes through unchanged.
    """

    if not text or not spec or not spec.get("fields"):
        return text, None
    fields = _handover_fields(text)
    empty = EMPTY_VALUES | {str(value).casefold() for value in spec.get("empty_values") or []}

    def value(name: str) -> str | None:
        found = fields.get(name.casefold())
        return found[1] if found and found[1].casefold() not in empty else None

    lines = [f"{fields[name.casefold()][0]}: {value(name)}" for name in spec["fields"] if value(name)]
    if not lines:
        # A later message of the person, not a handover.
        return text, None
    request: list[str] = []
    for name in spec.get("request") or []:
        part = value(name)
        if not part or any(part in seen for seen in request):
            continue
        # A description that repeats the title replaces it.
        request = [seen for seen in request if seen not in part] + [part]
    card = {
        "request": "\n".join(request),
        "facts": [part for name in spec.get("facts") or [] if (part := value(name))],
    }
    return "\n".join(lines), card


def _text_of(message: Any) -> str:
    if message.role != "assistant":
        return ""
    return "".join(
        block.text for block in message.get_content_blocks() if isinstance(block, TextBlock)
    ).strip()


class ChatLeaderTurnRunner:
    """Run one workflow turn through the console ``ChatService``.

    ``bind(app)`` must be called after ``create_app``: the chat service,
    storage and workspace manager live on ``app.state`` and are created in
    the application lifespan.
    """

    def __init__(
        self,
        uows: Callable[[], Any],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        wait_seconds: float | None = None,
        case: Any = None,
        approvals: Any = None,
    ) -> None:
        self._uows = uows
        # Partner routes onboarded from a declaration (see _case.py).
        self._case = case
        self._approvals = approvals
        self._clock = clock
        # The blob store of partner assets; None: photos are not offered.
        self._images: Any = None
        self._wait_seconds = (
            float(os.getenv("WORKFORCE_LEADER_WAIT_SECONDS", "240"))
            if wait_seconds is None
            else wait_seconds
        )
        self._app: Any = None

    def attach_images(self, blob_store: Any) -> None:
        self._images = blob_store

    async def _new_images(self, workflow_id: str) -> list[DataBlock]:
        """The end user's photos bound to this workflow not shown yet."""

        if self._images is None or self._case is None:
            return []
        from ...assets._tables import assets

        store = self._case.store
        shown = {entry["text"] for entry in await store.entries(workflow_id, kind="image")}
        async with self._uows() as uow:
            rows = (
                await uow.execute(
                    select(assets.c.id, assets.c.object_uri, assets.c.content_type, assets.c.filename, assets.c.actual_size)
                    .where(
                        assets.c.workflow_id == workflow_id,
                        assets.c.origin == "customer",
                        assets.c.status == "active",
                    )
                    .order_by(assets.c.created_at),
                )
            ).mappings().all()
        blocks: list[DataBlock] = []
        for row in rows:
            if len(blocks) >= MAX_IMAGES_PER_TURN or row["id"] in shown:
                continue
            if not str(row["content_type"]).startswith("image/") or (row["actual_size"] or 0) > MAX_IMAGE_BYTES:
                continue
            async with self._images.open(row["object_uri"]) as body:
                data = await body.read()
            blocks.append(
                DataBlock(
                    source=Base64Source(data=base64.b64encode(data).decode("ascii"), media_type=row["content_type"]),
                    name=row["filename"],
                ),
            )
            await store.append(workflow_id, "image", row["id"])
        return blocks

    def attach_case(self, case: Any, approvals: Any) -> None:
        self._case = case
        self._approvals = approvals
        if self._app is not None:
            case.bind(self._app)

    async def case_middlewares(self, user_id: str, agent_id: str, session_id: str) -> list:
        if self._case is None:
            return []
        return await self._case.middlewares(user_id, agent_id, session_id)

    def bind(self, app: Any) -> None:
        self._app = app
        if self._case is not None:
            self._case.bind(app)
        app.state.partner_quality = self.quality

    async def quality(self, manager_account_id: str, days: int = 30) -> dict:
        """Outcomes, message quality and cost of the manager's partner tickets."""

        from ._quality import ticket_quality

        state = self._state()
        return await ticket_quality(
            self._uows, state.storage, state.shared_context_storage, manager_account_id, days=days,
        )

    # ------------------------------------------------------------------ deps

    def _state(self) -> Any:
        state = getattr(self._app, "state", None)
        if state is None or getattr(state, "chat_service", None) is None:
            # The durable job is retried; the app lifespan is still starting.
            raise RuntimeError("chat runtime is not ready yet")
        return state

    async def _leader_session(self, user_id: str, session_ref: str) -> tuple[Any, Any]:
        """The manager's fixed Leader and this workflow's own session."""

        from ...._router._workforce_console import _leader
        from ....storage import SessionConfig

        state = self._state()
        storage = state.storage
        leader, primary = await _leader(user_id, storage, state.workspace_manager)
        session = await storage.get_session(user_id, leader.id, session_ref)
        if session is None:
            session = await storage.upsert_session(
                user_id=user_id,
                agent_id=leader.id,
                config=SessionConfig(
                    workspace_id=session_ref,
                    name="Partner ticket",
                    chat_model_config=primary.config.chat_model_config,
                ),
                session_id=session_ref,
            )
            workspace = await state.workspace_manager.get_workspace(
                user_id,
                leader.id,
                session.id,
                session.config.workspace_id,
            )
            # The Leader orchestrates; it never calls deployment MCPs.
            for default_mcp in workspace.default_mcps:
                await workspace.remove_mcp(
                    default_mcp.name,
                    agent_id=leader.id,
                    session_id=session.id,
                )
        return leader, session

    async def _input_text(self, workflow_id: str, trigger: dict) -> str | None:
        cause = trigger.get("cause") or {}
        if cause.get("kind") != "request":
            return None
        async with self._uows() as uow:
            row = (
                await uow.execute(
                    select(workflow_inputs.c.text).where(
                        workflow_inputs.c.workflow_id == workflow_id,
                        workflow_inputs.c.cause_kind == "request",
                        workflow_inputs.c.cause_id == cause.get("request_id"),
                    ),
                )
            ).first()
        return row[0] if row else None

    async def _usage(self, user_id: str, session_id: str) -> tuple[int, int, int]:
        """(model calls, input tokens, output tokens) of the ticket's team."""

        state = self._state()
        session = await state.storage.get_session(user_id, "", session_id)
        if session is None or session.team_id is None:
            return 0, 0, 0
        record = await state.shared_context_storage.get_team_shared_context(
            user_id,
            session.team_id,
        )
        if record is None:
            return 0, 0, 0
        usage = record.state.metrics.provider_usage.values()
        return (
            sum(item.calls for item in usage),
            sum(item.input_tokens for item in usage),
            sum(item.output_tokens for item in usage),
        )

    async def _message_ids(self, user_id: str, session_id: str) -> set[str]:
        lister = getattr(self._state().storage, "list_messages", None)
        if lister is None:
            return set()
        messages, _ = await lister(user_id, session_id, limit=500)
        return {message.id for message in messages}

    async def _turn_tokens(self, user_id: str, session_id: str, before: set[str]) -> tuple[int, int]:
        """(input, output) tokens of the leader's messages written this turn."""

        lister = getattr(self._state().storage, "list_messages", None)
        if lister is None:
            return 0, 0
        messages, _ = await lister(user_id, session_id, limit=500)
        usages = [m.usage for m in messages if m.id not in before and getattr(m, "usage", None)]
        return sum(u.input_tokens for u in usages), sum(u.output_tokens for u in usages)

    async def _model_error(self, user_id: str, session_id: str, before: set[str]) -> str | None:
        """The error type this turn's Leader reply ended on, if any."""

        lister = getattr(self._state().storage, "list_messages", None)
        if lister is None:
            return None
        messages, _ = await lister(user_id, session_id, limit=500)
        return next(
            (
                str(m.error.type)
                for m in messages
                if m.id not in before and getattr(getattr(m, "error", None), "type", None)
            ),
            None,
        )

    async def _member_tokens(self, user_id: str, session_id: str, leader_agent_id: str) -> tuple[int, int]:
        """(input, output) tokens the room's members used so far (leader excluded)."""

        state = self._state()
        session = await state.storage.get_session(user_id, "", session_id)
        if session is None or session.team_id is None or state.shared_context_storage is None:
            return 0, 0
        record = await state.shared_context_storage.get_team_shared_context(user_id, session.team_id)
        if record is None:
            return 0, 0
        members = [usage for agent, usage in record.state.metrics.provider_usage.items() if agent != leader_agent_id]
        return sum(u.input_tokens for u in members), sum(u.output_tokens for u in members)

    async def _learn_from_room(self, user_id: str, agent_id: str, session_id: str) -> None:
        """The ticket's result is out: its room (if any) teaches its agents."""

        state = self._state()
        schedule = getattr(state.chat_service, "schedule_learning", None)
        if schedule is None:
            return
        session = await state.storage.get_session(user_id, agent_id, session_id)
        if session is not None and session.team_id is not None:
            schedule(user_id, session, session.team_id)

    async def workflow_closed(self, scope: Any, workflow_id: str, reason: str) -> None:
        """A partner closed a ticket: its room teaches its agents only when the
        end user confirmed the result (route config ``success_close_reasons``),
        not when the Leader merely asked for confirmation."""

        if self._case is None:
            return
        binding = await self._case.store.session_of_workflow(workflow_id)
        if binding is None:
            return
        route = await self._case.store.route(binding["route_id"]) or {}
        success = (route.get("config") or {}).get("success_close_reasons") or ["resident_confirmed"]
        if reason not in success:
            logger.info("Partner case %s closed (%s): nothing learned", workflow_id, reason)
            return
        user_id = binding["manager_account_id"]
        await self._score_recalled_memory(user_id, binding, workflow_id)
        await self._learn_from_room(user_id, binding["agent_id"], binding["session_id"])

    async def _score_recalled_memory(self, user_id: str, binding: dict, workflow_id: str) -> None:
        """Memories recalled in this ticket count as helpful when the end user
        confirmed at the first invitation, harmful when they rejected first."""

        state = self._state()
        record = getattr(state.chat_service, "record_ticket_outcome", None)
        session = await state.storage.get_session(user_id, binding["agent_id"], binding["session_id"])
        team_id = getattr(session, "team_id", None)
        if record is None or not team_id:
            return
        invitations = [
            entry for entry in await self._case.store.entries(workflow_id, kind="say")
            if entry["expects"] == "confirmation"
        ]
        retired = await record(user_id, team_id, len(invitations) <= 1)
        if retired:
            logger.info("Partner case %s: retired memories %s", workflow_id, retired)

    async def _messages_after(self, user_id: str, session_id: str, message_id: str) -> list[Any]:
        storage = self._state().storage
        messages, _ = await storage.list_messages(user_id, session_id, limit=200)
        ids = [message.id for message in messages]
        start = ids.index(message_id) + 1 if message_id in ids else len(messages)
        return messages[start:]

    async def _wait_for_reply(self, user_id: str, session_id: str, message_id: str) -> None:
        """After a resumed worker action the Leader answers in a later run."""

        bus = self._state().message_bus
        deadline = time.monotonic() + self._wait_seconds
        while time.monotonic() < deadline:
            replies = [
                m for m in await self._messages_after(user_id, session_id, message_id) if _text_of(m)
            ]
            if replies and not await bus.session_is_running(session_id):
                return
            await asyncio.sleep(1.0)

    # ----------------------------------------------------------------- turn

    async def invoke_turn(self, scope, trigger, context, execution_guard) -> TurnDecision:
        await execution_guard.check("read")
        if self._case is not None:
            from ._contract import route_for_workflow
            route = await route_for_workflow(self._case.store, context.workflow.workflow_id,
                                             context.workflow.route_id)
            if route is not None:
                from ._readiness import route_readiness

                readiness = await route_readiness(self._state().storage, route)
                if not readiness["ready"]:
                    workflow = context.workflow
                    await self._case.store.append(workflow.workflow_id, "attention", "TEAM_NOT_READY",
                                                  trigger_id=trigger["trigger_id"])
                    return TurnDecision(
                        candidate=RuntimeTurnResult(
                            trigger_id=trigger["trigger_id"], expected_state_revision=workflow.revision,
                            checkpoint=context.checkpoint.model_copy(update={"state_revision": workflow.revision + 1}),
                            result=RequestResult(messages=(AssistantMessage(
                                message_id=f"{trigger['trigger_id']}:team-not-ready",
                                workflow_id=workflow.workflow_id,
                                text="Ban quản lý đang kiểm tra đội hỗ trợ cho yêu cầu này. Yêu cầu của bạn đã được ghi nhận.",
                                created_at=self._clock(),
                            ),), data={"outcome": "needs_attention", "error_code": "TEAM_NOT_READY"}),
                        ), next_state=WorkflowState.NEEDS_ATTENTION,
                    )
                return await self._case_turn(scope, trigger, context, route)
        state = self._state()
        user_id = scope.manager_account_id
        workflow = context.workflow
        leader, session = await self._leader_session(user_id, context.checkpoint.session_refs[0])
        calls_before, input_before, output_before = await self._usage(user_id, session.id)

        text = await self._input_text(workflow.workflow_id, trigger)
        message = UserMsg(
            name="customer",
            content=[TextBlock(text=text or "(Hệ thống) Tiếp tục xử lý yêu cầu của khách.")],
        )
        pending = await pending_chat_actions(state.storage, user_id, leader.id, session.id)
        resolved = resolve_chat_consent(message, pending) if pending and text else None
        if resolved is not None:
            # The customer's explicit decision on a parked tool call: the same
            # path as the web chat router, then wait for the Leader's answer.
            action, decision = resolved
            await state.storage.upsert_message(user_id, session.id, message)
            await state.chat_service.run(user_id, action.session_id, action.agent_id, decision)
            await self._wait_for_reply(user_id, session.id, message.id)
        else:
            await state.chat_service.run(user_id, session.id, leader.id, message)

        replies = [
            _text_of(m) for m in await self._messages_after(user_id, session.id, message.id)
        ]
        reply = "\n\n".join(item for item in replies if item)
        calls_after, input_after, output_after = await self._usage(user_id, session.id)
        still_pending = await pending_chat_actions(state.storage, user_id, leader.id, session.id)
        question = None
        refreshed = await state.storage.get_session(user_id, leader.id, session.id)
        if refreshed is not None and refreshed.team_id is not None:
            from ...._shared_context import SharedContextService

            question = await SharedContextService(
                state.shared_context_storage,
                state.message_bus,
            ).pending_user_question(user_id, refreshed.team_id)
        if not reply:
            next_state = WorkflowState.NEEDS_ATTENTION
            reply = (
                "Hệ thống chưa tạo được câu trả lời cho yêu cầu này. Ban quản lý sẽ kiểm tra lại."
            )
        elif still_pending or question or reply.rstrip().endswith("?"):
            next_state = WorkflowState.AWAITING_USER
        else:
            next_state = WorkflowState.AWAITING_CONFIRMATION

        budget = context.checkpoint.used_budget
        checkpoint = context.checkpoint.model_copy(
            update={
                "state_revision": workflow.revision + 1,
                "used_budget": budget.model_copy(
                    update={
                        "model_turns": budget.model_turns
                        + max(1, calls_after - calls_before),
                        "input_tokens": budget.input_tokens
                        + max(0, input_after - input_before),
                        "output_tokens": budget.output_tokens
                        + max(0, output_after - output_before),
                    },
                ),
            },
        )
        logger.info(
            "Partner workflow %s turn: state=%s calls=%d",
            workflow.workflow_id,
            next_state,
            calls_after - calls_before,
        )
        return TurnDecision(
            candidate=RuntimeTurnResult(
                trigger_id=trigger["trigger_id"],
                expected_state_revision=workflow.revision,
                checkpoint=checkpoint,
                result=RequestResult(
                    messages=(
                        AssistantMessage(
                            message_id=f"{trigger['trigger_id']}:reply",
                            workflow_id=workflow.workflow_id,
                            text=reply[:20_000],
                            created_at=self._clock(),
                        ),
                    ),
                ),
            ),
            next_state=next_state,
        )

    # ------------------------------------------------------- partner case

    async def _case_session(
        self, user_id: str, scope: Any, workflow: Any, route: dict, session_ref: str, text: str | None = None,
    ) -> Any:
        """The ticket's own session of the manager's Leader (the console
        Leader): the ticket shows on the Leader page with its room."""

        from ...._router._workforce_console import _leader
        from ....storage import SessionConfig, SessionNaming, TeamData, TeamRecord
        from ....storage._model._team import direct_routing_default
        from ._case import _members

        state = self._state()
        storage = state.storage
        leader, primary = await _leader(user_id, storage, state.workspace_manager)
        session = await storage.get_session(user_id, leader.id, session_ref)
        if session is None:
            fields = (route.get("config") or {}).get("ticket_title_fields") or []
            session = await storage.upsert_session(
                user_id=user_id,
                agent_id=leader.id,
                config=SessionConfig(
                    workspace_id=session_ref,
                    name=ticket_title(text, fields) or "Phiếu đối tác",
                    # The first turn's model names it in a few words.
                    naming=SessionNaming(auto=True),
                    chat_model_config=primary.config.chat_model_config,
                ),
                session_id=session_ref,
            )
            workspace = await state.workspace_manager.get_workspace(
                user_id, leader.id, session.id, session.config.workspace_id,
            )
            # The Leader orchestrates; the route's tools belong to the room's members.
            for client in await workspace.list_mcps(agent_id=leader.id, session_id=session.id):
                await workspace.remove_mcp(client.name, agent_id=leader.id, session_id=session.id)
            for default_mcp in workspace.default_mcps:
                await workspace.remove_mcp(default_mcp.name, agent_id=leader.id, session_id=session.id)
            await self._case.store.bind_session(
                {
                    "session_id": session.id,
                    "workflow_id": workflow.workflow_id,
                    "route_id": route["route_id"],
                    "manager_account_id": user_id,
                    "scope": scope.model_dump(mode="json"),
                    "agent_id": leader.id,
                    "agent_version": 0,
                    "trigger_id": None,
                },
            )
        if session.team_id is None and _members(route):
            # The Leader always works a partner ticket with a room: it opens
            # with the session (a model call less) and carries the ticket's name.
            team = TeamRecord(
                user_id=user_id, session_id=session.id, leader_agent_id=leader.id,
                data=TeamData(name=session.config.name, description="Phòng xử lý phiếu",
                              direct_member_routing=direct_routing_default(), member_ids=[]),
            )
            await storage.upsert_team(user_id, team)
            await storage.set_session_team_id(user_id, session.id, team.id)
            session = await storage.get_session(user_id, leader.id, session.id)
        if session.state.middle_context.get("workflow_id") != workflow.workflow_id:
            session.state.middle_context["workflow_id"] = workflow.workflow_id
            session = await storage.upsert_session(user_id=user_id, agent_id=leader.id,
                config=session.config, state=session.state, session_id=session.id)
        if route.get("contract_frozen"):
            versions = {agent_id: int(binding["version"]) for agent_id, binding in
                        ((route.get("config") or {}).get("member_agents") or {}).items()}
            if session.state.middle_context.get("partner_agent_versions") != versions:
                session.state.middle_context["partner_agent_versions"] = versions
                session = await storage.upsert_session(user_id=user_id, agent_id=leader.id,
                    config=session.config, state=session.state, session_id=session.id)
        return session

    async def _wait_for_say(self, workflow_id: str, trigger_id: str) -> None:
        deadline = time.monotonic() + self._wait_seconds
        while time.monotonic() < deadline:
            if await self._case.store.entries(workflow_id, kind="say", trigger_id=trigger_id):
                return
            await asyncio.sleep(1.0)

    async def _case_turn(self, scope, trigger, context, route: dict) -> TurnDecision:
        state = self._state()
        storage = state.storage
        user_id = scope.manager_account_id
        workflow = context.workflow
        store = self._case.store
        text = await self._input_text(workflow.workflow_id, trigger)
        session = await self._case_session(
            user_id, scope, workflow, route, context.checkpoint.session_refs[0], text,
        )
        agent_id = session.agent_id
        trigger_id = trigger["trigger_id"]
        await store.set_trigger(session.id, trigger_id)
        cause = trigger.get("cause") or {}
        approval_ids = list(context.checkpoint.pending_approval_ids)
        ran = False
        # What this turn costs: the leader's new messages plus the room's members.
        before_ids = await self._message_ids(user_id, session.id)
        members_before = await self._member_tokens(user_id, session.id, agent_id)
        if cause.get("kind") == "approval" and self._approvals is not None:
            approval = await self._approvals.get(cause["approval_id"])
            pending = await pending_chat_actions(storage, user_id, agent_id, session.id)
            action = next(
                (item for item in pending if approval and item.tool_call.id == approval["tool_call_id"]),
                None,
            )
            if action is not None:
                decision = UserConfirmResultEvent(
                    reply_id=action.reply_id,
                    confirm_results=[
                        ConfirmResult(
                            confirmed=approval["status"] == "approved",
                            tool_call=action.tool_call.model_copy(deep=True),
                            rules=None,
                        ),
                    ],
                )
                # A member's parked call resumes in its own session; its
                # report then wakes the Leader, who speaks within this turn.
                await state.chat_service.run(user_id, action.session_id, action.agent_id, decision)
                if action.session_id != session.id:
                    await self._wait_for_say(workflow.workflow_id, trigger_id)
                ran = True
            approval_ids = [item for item in approval_ids if item != cause["approval_id"]]
        elif f"{trigger_id}:input" in before_ids:
            # A retry after a transient model error: the input is already in
            # the session; resending it would duplicate it.
            attempt = len(await store.entries(workflow.workflow_id, kind="model_error", trigger_id=trigger_id))
            message = UserMsg(
                id=f"{trigger_id}:retry{attempt}",
                name="customer",
                content=[TextBlock(text="(Hệ thống) Lượt trước bị lỗi model nên chưa trả lời. Tiếp tục xử lý yêu cầu ở trên.")],
                metadata={"actor": "system"},
            )
            await state.chat_service.run(user_id, session.id, agent_id, message)
            ran = True
        else:
            parts = []
            heard = await store.take_pending(workflow.workflow_id)
            confirmed = not text and await self._case.confirm_completed_work(workflow.workflow_id, route, heard)
            if heard:
                parts.append(
                    "(Hệ thống) Sự kiện mới của việc đang theo dõi:\n"
                    + "\n".join(f"E{item['seq']}: {item['text'].split(': {', 1)[0]}" for item in heard)
                    + "\nChi tiết đã lưu theo mã E; đọc CaseEvidence khi cần, không thực hiện lại thao tác.",
                )
            brief, card = ticket_brief(text, (route.get("config") or {}).get("ticket_input"))
            if brief:
                parts.append(brief)
            images = await self._new_images(workflow.workflow_id)
            if images:
                parts.append(f"(Hệ thống) Người dùng gửi kèm {len(images)} ảnh bên dưới.")
            if parts and not confirmed:
                message = UserMsg(
                    id=f"{trigger_id}:input", name="customer", content=[TextBlock(text="\n\n".join(parts)), *images],
                    # The room shows the ticket as a card, not the lines the Leader reads.
                    metadata={"actor": "resident" if text else "system",
                              **({"ticket": card} if card else {})},
                )
                await state.chat_service.run(user_id, session.id, agent_id, message)
                ran = True
        # The turn is over: a later wake-up (a member's late report) has no
        # turn to speak through; the next trigger reads what it said.
        await store.set_trigger(session.id, None)
        leader_in, leader_out = await self._turn_tokens(user_id, session.id, before_ids)
        members_after = await self._member_tokens(user_id, session.id, agent_id)
        spent_in = leader_in + max(0, members_after[0] - members_before[0])
        spent_out = leader_out + max(0, members_after[1] - members_before[1])

        says = await store.entries(workflow.workflow_id, kind="say", trigger_id=trigger_id)
        rejected = await store.entries(workflow.workflow_id, kind="rejected", trigger_id=trigger_id)
        error = await self._model_error(user_id, session.id, before_ids) if ran and not says else None
        if error in TRANSIENT_ERRORS:
            failures = await store.entries(workflow.workflow_id, kind="model_error", trigger_id=trigger_id)
            if len(failures) < MAX_MODEL_RETRIES:
                await store.append(workflow.workflow_id, "model_error", "transient", trigger_id=trigger_id)
                # The durable job retries the turn (see the retry branch above).
                raise RuntimeError("transient model error; the partner turn is retried")
        messages = [
            AssistantMessage(
                message_id=f"{trigger_id}:say:{item['seq']}",
                workflow_id=workflow.workflow_id,
                text=item["text"][:20_000],
                created_at=self._clock(),
            )
            for item in says
        ]
        rules = (route.get("config") or {}).get("rules") or {}
        if not says and ran and rules.get("safe_reply"):
            messages = [
                AssistantMessage(
                    message_id=f"{trigger_id}:safe",
                    workflow_id=workflow.workflow_id,
                    text=str(rules["safe_reply"])[:20_000],
                    created_at=self._clock(),
                ),
            ]
        if self._approvals is not None and (cause.get("kind") == "approval" or not approval_ids):
            parked = await pending_chat_actions(storage, user_id, agent_id, session.id)
            policy = (route.get("config") or {}).get("policy") or {}
            opened = await self._approvals.open(
                workflow,
                parked,
                expected_revision=workflow.revision + 1,
                ttl_seconds=int(policy.get("approval_ttl_seconds") or 86_400),
                describe=lambda name: f"Trợ lý cần bạn đồng ý trước khi thực hiện: {name}.",
            )
            approval_ids = sorted(set(approval_ids) | set(opened))

        if approval_ids:
            next_state = WorkflowState.AWAITING_APPROVAL
        elif ran and not says:
            next_state = WorkflowState.NEEDS_ATTENTION
            reason = attention_reason(error)
            await store.append(workflow.workflow_id, "attention", reason, trigger_id=trigger_id)
            await self._case.share_attention(workflow.workflow_id, reason)
        elif says and says[-1]["expects"] == "reply":
            next_state = WorkflowState.AWAITING_USER
        elif says and says[-1]["expects"] == "confirmation":
            next_state = WorkflowState.AWAITING_CONFIRMATION
        elif not ran and workflow.state not in (WorkflowState.ACCEPTED, WorkflowState.ACTIVE):
            next_state = workflow.state
        else:
            next_state = WorkflowState.AWAITING_USER

        budget = context.checkpoint.used_budget
        checkpoint = context.checkpoint.model_copy(
            update={
                "state_revision": workflow.revision + 1,
                "pending_approval_ids": tuple(approval_ids),
                "used_budget": budget.model_copy(
                    update={
                        "model_turns": budget.model_turns + (1 if ran else 0),
                        "input_tokens": budget.input_tokens + spent_in,
                        "output_tokens": budget.output_tokens + spent_out,
                    },
                ),
            },
        )
        logger.info(
            "Partner case %s turn %s: state=%s says=%d rejected=%d tokens=%d/%d",
            workflow.workflow_id,
            trigger_id,
            next_state,
            len(says),
            len(rejected),
            spent_in,
            spent_out,
        )
        return TurnDecision(
            candidate=RuntimeTurnResult(
                trigger_id=trigger_id,
                expected_state_revision=workflow.revision,
                checkpoint=checkpoint,
                result=RequestResult(messages=tuple(messages), data=(
                    {"outcome": "fallback", "error_code": "PARTNER_TURN_NO_PUBLIC_REPLY"}
                    if ran and not says and not approval_ids else {}
                )),
            ),
            next_state=next_state,
        )


__all__ = ["LEADER_VERSION_ID", "ChatLeaderTurnRunner"]
