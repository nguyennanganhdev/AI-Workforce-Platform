# -*- coding: utf-8 -*-
"""Generic middleware that drains the message bus inbox before reasoning.

Producers push :class:`~agentscope.message.HintBlock` payloads into
the per-session inbox via :class:`~agentscope.app._message_bus.MessageBus`.
This middleware drains the inbox at the start of each reasoning step
and injects the HintBlocks into ``agent.state.context`` — appended to
the last assistant message's content list (same pattern as
:class:`ToolOffloadMiddleware`).

Each injected HintBlock also yields a one-shot ``HintBlockEvent``
so the front-end SSE stream can render it in real time.
"""
from collections.abc import AsyncGenerator, Callable
import json
from typing import TYPE_CHECKING, Any

from ..._logging import logger
from ...agent import Agent
from ...event import HintBlockEvent
from ...message import AssistantMsg, HintBlock
from ...middleware import MiddlewareBase
from ..message_bus import MessageBus, MessageBusKeys

if TYPE_CHECKING:
    from .._shared_context import SharedContextService


def _handoff_id(block: HintBlock) -> str | None:
    try:
        value = json.loads(block.source or "{}")
    except (TypeError, ValueError):
        return None
    handoff_id = value.get("handoff_id")
    return handoff_id if isinstance(handoff_id, str) and handoff_id else None


class InboxMiddleware(MiddlewareBase):  # pylint: disable=abstract-method
    """Drain the session's inbox and inject HintBlocks before each
    reasoning step.

    Each entry in the inbox is a serialised
    :class:`~agentscope.message.HintBlock`. The middleware
    deserializes them, appends to the last assistant message in
    ``agent.state.context``, and yields a one-shot ``HintBlockEvent``
    for each so the front-end sees them.

    Args:
        message_bus (`MessageBus`):
            The application message bus to read from.
        max_count (`int`, defaults to ``100``):
            Maximum number of entries drained per reasoning step.
    """

    def __init__(
        self,
        message_bus: MessageBus,
        max_count: int = 100,
        shared_context: "SharedContextService | None" = None,
        user_id: str | None = None,
    ) -> None:
        """Initialise the middleware.

        Args:
            message_bus (`MessageBus`):
                The application-level message bus.
            max_count (`int`, defaults to ``100``):
                Maximum entries drained per reasoning step.
        """
        self._bus = message_bus
        self._max_count = max_count
        self._shared_context = shared_context
        self._user_id = user_id

    async def on_reasoning(  # type: ignore[override]
        self,
        agent: Agent,
        input_kwargs: dict,
        next_handler: Callable[..., AsyncGenerator],
    ) -> AsyncGenerator[Any, None]:
        """Drain the inbox, inject HintBlocks into context, yield
        events, then continue with downstream reasoning.

        Args:
            agent (`Agent`):
                The executing agent. ``agent.state.session_id`` selects
                the inbox to drain.
            input_kwargs (`dict`):
                Reasoning input kwargs (contains ``tool_choice``);
                forwarded unchanged to ``next_handler``.
            next_handler (`Callable[..., AsyncGenerator]`):
                The downstream middleware or core reasoning logic.

        Yields:
            `Any`:
                One ``HintBlockEvent`` per drained inbox entry,
                followed by events from downstream.
        """
        entries = await self._bus.queue_drain(
            MessageBusKeys.inbox(agent.state.session_id),
            max_count=self._max_count,
        )

        if entries:
            drained_blocks = [
                HintBlock.model_validate(payload)
                for _entry_id, payload in entries
            ]

            # At-least-once durable handoffs may legitimately be replayed
            # after a crash.  A recipient must observe each handoff once in
            # its private context, while the durable row is acknowledged only
            # after the payload was successfully decoded and injected (or was
            # already present from a previous attempt).
            seen: set[str] = set()
            for message in agent.state.context:
                for block in message.get_content_blocks():
                    if isinstance(block, HintBlock):
                        handoff_id = _handoff_id(block)
                        if handoff_id:
                            seen.add(handoff_id)
            hint_blocks: list[HintBlock] = []
            acknowledged: list[str] = []
            for hint in drained_blocks:
                handoff_id = _handoff_id(hint)
                if handoff_id is None:
                    hint_blocks.append(hint)
                    continue
                acknowledged.append(handoff_id)
                if handoff_id not in seen:
                    hint_blocks.append(hint)
                    seen.add(handoff_id)

            logger.info(
                "InboxMiddleware: injecting %d HintBlock(s) into context "
                "for session %s",
                len(hint_blocks),
                agent.state.session_id,
            )

            # Inject into agent context (same pattern as
            # ToolOffloadMiddleware).
            if hint_blocks and len(agent.state.context) > 0:
                last_msg = agent.state.context[-1]
                if (
                    last_msg.role == "assistant"
                    and last_msg.name == agent.name
                ):
                    last_msg.content.extend(hint_blocks)
                else:
                    agent.state.context.append(
                        AssistantMsg(
                            id=agent.state.reply_id,
                            name=agent.name,
                            content=list(hint_blocks),
                        ),
                    )
            elif hint_blocks:
                agent.state.context.append(
                    AssistantMsg(
                        id=agent.state.reply_id,
                        name=agent.name,
                        content=list(hint_blocks),
                    ),
                )

            # Yield one-shot events so the front-end SSE stream sees
            # each HintBlock.
            for hint in hint_blocks:
                yield HintBlockEvent(
                    reply_id=agent.state.reply_id,
                    block_id=hint.id,
                    source=hint.source,
                    hint=hint.hint,
                )

            for handoff_id in acknowledged:
                await self._bus.registry_del(
                    MessageBusKeys.team_context_directives(
                        agent.state.session_id,
                    ),
                    handoff_id,
                )
                if self._shared_context is not None:
                    await self._shared_context.acknowledge_handoff(
                        handoff_id,
                        agent.state.session_id,
                        self._user_id,
                    )

        async for evt in next_handler(**input_kwargs):
            yield evt
