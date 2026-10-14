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
from ...._chat_consent import pending_chat_actions, resolve_chat_consent
from .....message import TextBlock, UserMsg
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
    ) -> None:
        self._uows = uows
        self._clock = clock
        self._wait_seconds = (
            float(os.getenv("WORKFORCE_LEADER_WAIT_SECONDS", "240"))
            if wait_seconds is None
            else wait_seconds
        )
        self._app: Any = None

    def bind(self, app: Any) -> None:
        self._app = app

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


__all__ = ["LEADER_VERSION_ID", "ChatLeaderTurnRunner"]
