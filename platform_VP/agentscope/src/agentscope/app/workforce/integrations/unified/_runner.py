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
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from ....._logging import logger
from .....event import ConfirmResult, UserConfirmResultEvent
from .....message import TextBlock, UserMsg
from ...._chat_consent import pending_chat_actions, resolve_chat_consent
from ...contracts import AssistantMessage, RequestResult, WorkflowState
from ...orchestration._tables import workflow_inputs
from ...orchestration.workflows import TurnDecision
from ...orchestration.workflows.phase_a import RuntimeTurnResult

LEADER_VERSION_ID = "console-leader"


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
        self._wait_seconds = (
            float(os.getenv("WORKFORCE_LEADER_WAIT_SECONDS", "240"))
            if wait_seconds is None
            else wait_seconds
        )
        self._app: Any = None

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
            route = await self._case.store.route(context.workflow.route_id)
            if route is not None:
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

    async def _case_session(self, user_id: str, scope: Any, workflow: Any, route: dict, session_ref: str) -> Any:
        """The route leader's own session for this workflow, version pinned."""

        from ....storage import SessionConfig

        state = self._state()
        storage = state.storage
        agent_id = route["leader_agent_id"]
        session = await storage.get_session(user_id, agent_id, session_ref)
        if session is not None:
            return session
        agent = await storage.get_agent(user_id, agent_id)
        if agent is None:
            raise RuntimeError(f"route leader agent {agent_id} is missing")
        primary = await storage.list_sessions(user_id, agent_id)
        model = primary[0].config.chat_model_config if primary else None
        session = await storage.upsert_session(
            user_id=user_id,
            agent_id=agent_id,
            config=SessionConfig(
                workspace_id=session_ref,
                name=f"Partner ticket {workflow.audience.external_ticket_id or workflow.workflow_id}",
                chat_model_config=model,
            ),
            session_id=session_ref,
        )
        version = int(agent.data.published_version or 0)
        if version:
            session.state.middle_context["agent_version"] = version
            await storage.upsert_session(
                user_id=user_id,
                agent_id=agent_id,
                config=session.config,
                state=session.state,
                session_id=session.id,
            )
        workspace = await state.workspace_manager.get_workspace(
            user_id, agent_id, session.id, session.config.workspace_id,
        )
        # The route's tools reach the leader through the case middleware only.
        for client in await workspace.list_mcps(agent_id=agent_id, session_id=session.id):
            await workspace.remove_mcp(client.name, agent_id=agent_id, session_id=session.id)
        for default_mcp in workspace.default_mcps:
            await workspace.remove_mcp(default_mcp.name, agent_id=agent_id, session_id=session.id)
        await self._case.store.bind_session(
            {
                "session_id": session.id,
                "workflow_id": workflow.workflow_id,
                "route_id": route["route_id"],
                "manager_account_id": user_id,
                "scope": scope.model_dump(mode="json"),
                "agent_id": agent_id,
                "agent_version": version,
                "trigger_id": None,
            },
        )
        return session

    async def _case_turn(self, scope, trigger, context, route: dict) -> TurnDecision:
        state = self._state()
        storage = state.storage
        user_id = scope.manager_account_id
        workflow = context.workflow
        store = self._case.store
        agent_id = route["leader_agent_id"]
        session = await self._case_session(
            user_id, scope, workflow, route, context.checkpoint.session_refs[0],
        )
        trigger_id = trigger["trigger_id"]
        await store.set_trigger(session.id, trigger_id)
        cause = trigger.get("cause") or {}
        approval_ids = list(context.checkpoint.pending_approval_ids)
        ran = False
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
                await state.chat_service.run(user_id, session.id, agent_id, decision)
                ran = True
            approval_ids = [item for item in approval_ids if item != cause["approval_id"]]
        else:
            parts = []
            heard = await store.take_pending(workflow.workflow_id)
            if heard:
                parts.append(
                    "(Hệ thống) Sự kiện mới của việc đang theo dõi:\n"
                    + "\n".join(f"E{item['seq']}: {item['text']}" for item in heard),
                )
            text = await self._input_text(workflow.workflow_id, trigger)
            if text:
                parts.append(text)
            if parts:
                message = UserMsg(name="customer", content=[TextBlock(text="\n\n".join(parts))])
                await state.chat_service.run(user_id, session.id, agent_id, message)
                ran = True
        # The turn is over: a later wake-up (a member's late report) has no
        # turn to speak through; the next trigger reads what it said.
        await store.set_trigger(session.id, None)

        says =await store.entries(workflow.workflow_id, kind="say", trigger_id=trigger_id)
        rejected = await store.entries(workflow.workflow_id, kind="rejected", trigger_id=trigger_id)
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
                    update={"model_turns": budget.model_turns + (1 if ran else 0)},
                ),
            },
        )
        logger.info(
            "Partner case %s turn %s: state=%s says=%d rejected=%d",
            workflow.workflow_id,
            trigger_id,
            next_state,
            len(says),
            len(rejected),
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
