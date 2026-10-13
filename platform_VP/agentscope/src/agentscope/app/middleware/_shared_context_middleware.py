"""Keep isolated/reference handoffs out of an agent's normal memory view."""

import asyncio
import time
from collections.abc import Awaitable, Callable

from ..._logging import logger
from ...agent import Agent
from ...message import Msg, UserMsg
from ...middleware import MiddlewareBase
from ...model import ChatResponse
from .._shared_context import SharedContextBudgetError, SharedContextService
from ..storage import ContextMode, StorageBase

SHARED_CONTEXT_MSG_NAME = "shared_context"
"""Name of the trailing message that carries the ticket's shared packet."""


class SharedContextIsolationMiddleware(MiddlewareBase):
    """Filter model input without deleting the durable private transcript.

    Isolated and reference-only turns see the system prompt plus the current
    reply only. Their reply ids are recorded in ``middle_context`` so later
    normal task turns do not accidentally ingest those private exchanges.
    """

    def __init__(
        self,
        mode: ContextMode,
        service: SharedContextService,
        user_id: str,
        team_id: str | None,
        prior_context: list[Msg] | None = None,
        packet_attachment: str = "",
        *,
        task_id: str | None = None,
        membership_storage: StorageBase | None = None,
        agent_id: str | None = None,
    ) -> None:
        self._mode = mode
        self._agent_id = agent_id
        self._service = service
        self._user_id = user_id
        self._team_id = team_id
        self._packet_attachment = packet_attachment
        self._task_id = task_id
        self._membership_storage = membership_storage or service.storage
        self._event_revision: int | None = None
        prior_context = prior_context or []
        self._prior_message_ids = {message.id for message in prior_context}
        self._prior_block_ids = {
            message.id: {block.id for block in message.get_content_blocks()}
            for message in prior_context
        }

    def _current_turn_context(self, agent: Agent) -> list[Msg]:
        """Return whole new messages plus only newly appended blocks.

        Team inbox delivery appends a :class:`HintBlock` to an existing
        assistant message, while a customer/direct-mention input is appended
        as a new message. Comparing against the pre-turn snapshot handles both
        forms without relying on ``reply_id`` (which identifies the assistant
        reply, not the incoming message).
        """

        current: list[Msg] = []
        for message in agent.state.context:
            if message.id not in self._prior_message_ids:
                current.append(message)
                continue

            old_block_ids = self._prior_block_ids.get(message.id, set())
            added_blocks = [
                block
                for block in message.get_content_blocks()
                if block.id not in old_block_ids
            ]
            if added_blocks:
                current.append(
                    message.model_copy(
                        update={"content": added_blocks},
                        deep=True,
                    ),
                )
        return current

    async def on_model_call(
        self,
        agent: Agent,
        input_kwargs: dict,
        next_handler: Callable[..., Awaitable[ChatResponse]],
    ) -> ChatResponse:
        # TeamCreate can run inside the first Leader reply, after middleware
        # assembly. Adopt that durable membership before the next model call
        # instead of leaving the long-lived run permanently teamless.
        if self._team_id is None or self._task_id is None:
            session_id = getattr(agent.state, "session_id", None)
            session = (
                await self._membership_storage.get_session(
                    self._user_id,
                    "",
                    session_id,
                )
                if session_id
                else None
            )
            if session is not None and session.team_id is not None:
                self._team_id = session.team_id
                record = await self._service.storage.get_team_shared_context(
                    self._user_id,
                    self._team_id,
                )
                if record is not None:
                    self._task_id = record.state.active_task_id

        # A long-lived Leader run may receive peer results after its initial
        # snapshot. Refresh by event revision (not metrics writes) before the
        # next model call so new source ids and dependency states are visible.
        if self._team_id and self._task_id and self._mode == "task":
            record = await self._service.storage.get_team_shared_context(
                self._user_id, self._team_id
            )
            revision = (
                max(
                    (
                        event.revision
                        for event in record.state.events
                        if event.task_id == self._task_id
                    ),
                    default=0,
                )
                if record
                else 0
            )
            if revision != self._event_revision:
                packet, tokens = await self._service.prepare_packet(
                    model=input_kwargs["current_model"],
                    user_id=self._user_id,
                    team_id=self._team_id,
                    mode="task",
                    task_id=self._task_id,
                )
                self._packet_attachment = self._service.system_attachment(
                    packet, tokens
                )
                self._event_revision = revision
                await self._service.pin_session_revision(
                    agent.state.session_id,
                    team_id=self._team_id,
                    task_id=self._task_id,
                    revision=revision,
                )
        messages = list(input_kwargs["messages"])
        if self._packet_attachment and not messages:
            raise SharedContextBudgetError(
                "Cannot attach shared context because the model input has "
                "no system message.",
            )
        if self._mode in {"isolated", "references"}:
            # ``messages[1]`` may be the agent's old private summary and is
            # intentionally excluded. Only the system prompt, this turn's
            # context delta and the (references) packet are visible.
            filtered = [messages[0], *self._current_turn_context(agent)]
        else:
            filtered = messages
        if self._packet_attachment:
            # The packet changes whenever a teammate reports. Keeping it as
            # the LAST message leaves the system prompt, tool schemas and the
            # private history as an unchanged prefix between calls, which is
            # what provider prompt caching reuses. Appending it to the system
            # message (the previous design) invalidated the cache for the
            # whole conversation on every new shared event.
            filtered = [
                *filtered,
                UserMsg(name=SHARED_CONTEXT_MSG_NAME, content=self._packet_attachment),
            ]

        current_model = input_kwargs["current_model"]
        prompt_tokens = await current_model.count_tokens(
            filtered,
            input_kwargs["tools"],
        )
        message_tokens = await current_model.count_tokens(filtered, None)
        system_tokens = await current_model.count_tokens(filtered[:1], None)
        tool_tokens = max(0, prompt_tokens - message_tokens)
        conversation_tokens = max(0, message_tokens - system_tokens)
        logger.info(
            "Model input team=%s session=%s reply=%s: total=%d tools=%d "
            "system_with_shared=%d conversation=%d",
            self._team_id,
            getattr(agent.state, "session_id", None),
            agent.state.reply_id,
            prompt_tokens,
            tool_tokens,
            system_tokens,
            conversation_tokens,
        )
        reserved_output_tokens = max(
            1,
            int(
                current_model.context_size * self._service.config.output_reserve_ratio,
            ),
        )
        budget_exceeded = (
            prompt_tokens
            + reserved_output_tokens
            + self._service.config.preflight_margin_tokens
            > current_model.context_size
        )
        if self._team_id is not None:
            await self._service.record_prompt_measurement(
                user_id=self._user_id,
                team_id=self._team_id,
                prompt_tokens=prompt_tokens,
                model_context_size=current_model.context_size,
                reserved_output_tokens=reserved_output_tokens,
                preflight_margin_tokens=self._service.config.preflight_margin_tokens,
                token_counter=getattr(
                    current_model,
                    "token_counting_strategy",
                    "custom-model-counter",
                ),
                budget_exceeded=budget_exceeded,
                tool_schema_tokens=tool_tokens,
                system_prompt_tokens=system_tokens,
                conversation_tokens=conversation_tokens,
            )
        if budget_exceeded:
            raise SharedContextBudgetError(
                "Measured model input plus the configured output reserve "
                "exceeds "
                f"the model context window ({prompt_tokens} + "
                f"{reserved_output_tokens} output reserve + "
                f"{self._service.config.preflight_margin_tokens} safety "
                f"margin > {current_model.context_size}). "
                "No context was silently truncated; narrow the task or "
                "reduce referenced artifacts and retry.",
            )

        kwargs = {**input_kwargs, "messages": filtered}
        session_id = getattr(agent.state, "session_id", None)
        if self._team_id is None or session_id is None:
            return await next_handler(**kwargs)
        remaining, epoch = await self._service.measure_collaboration(
            self._user_id,
            self._team_id,
            session_id,
            tokens=prompt_tokens,
            model_call=True,
            task_id=self._task_id,
        )
        started = time.monotonic()
        output_tokens = 0

        usage = None

        async def record_usage() -> None:
            # Provider usage is observability, not a budget input: a failure
            # here must never fail the agent's turn.
            try:
                await self._service.record_provider_usage(
                    user_id=self._user_id,
                    team_id=self._team_id,
                    agent_id=self._agent_id or agent.name,
                    agent_name=agent.name,
                    model=str(getattr(current_model, "model", "") or ""),
                    usage=usage,
                )
            except Exception:  # noqa: BLE001
                logger.exception("Could not record provider usage")

        async def charge(*, elapsed_floor: float = 0.0):
            await self._service.measure_collaboration(
                self._user_id,
                self._team_id,
                session_id,
                tokens=output_tokens,
                active_seconds=max(
                    elapsed_floor,
                    time.monotonic() - started,
                ),
                customer_revision=epoch,
                task_id=self._task_id,
            )

        try:
            async with asyncio.timeout(remaining):
                response = await next_handler(**kwargs)
        except TimeoutError:
            # The timeout callback can fire a few microseconds before the
            # monotonic measurement reaches ``remaining``. Charge at least
            # the reserved window so the domain-specific bounded-runtime
            # error is stable instead of leaking asyncio.TimeoutError.
            await charge(elapsed_floor=remaining)
            raise  # pragma: no cover - measure_collaboration raises first
        except BaseException:
            await charge()
            raise
        if not hasattr(response, "__aiter__"):
            usage = response.usage
            await record_usage()
            output_tokens = (
                response.usage.output_tokens
                if response.usage
                else await current_model.count_tokens(
                    [Msg(name=agent.name, role="assistant", content=response.content)],
                    None,
                )
            )
            await charge()
            return response

        async def measured_stream():
            nonlocal output_tokens, usage
            partial_content = []
            complete = False
            try:
                async with asyncio.timeout(
                    max(0, remaining - (time.monotonic() - started))
                ):
                    async for chunk in response:
                        partial_content.extend(chunk.content)
                        if chunk.is_last:
                            complete = True
                            usage = chunk.usage
                            output_tokens = (
                                chunk.usage.output_tokens
                                if chunk.usage
                                else await current_model.count_tokens(
                                    [
                                        Msg(
                                            name=agent.name,
                                            role="assistant",
                                            content=chunk.content,
                                        )
                                    ],
                                    None,
                                )
                            )
                        yield chunk
            finally:
                await response.aclose()
                if not complete and partial_content:
                    # Conservative on interrupted cumulative streams; never
                    # record a partially generated answer as zero output.
                    output_tokens = await current_model.count_tokens(
                        [
                            Msg(
                                name=agent.name,
                                role="assistant",
                                content=partial_content,
                            )
                        ],
                        None,
                    )
                await record_usage()
                await charge()

        return measured_stream()

    async def on_acting(self, agent, input_kwargs, next_handler):
        session_id = getattr(agent.state, "session_id", None)
        if self._team_id is None or session_id is None:
            async for result in next_handler(**input_kwargs):
                yield result
            return
        remaining, epoch = await self._service.measure_collaboration(
            self._user_id, self._team_id, session_id, task_id=self._task_id
        )
        started = time.monotonic()
        try:
            async with asyncio.timeout(remaining):
                async for result in next_handler(**input_kwargs):
                    yield result
        finally:
            await self._service.measure_collaboration(
                self._user_id,
                self._team_id,
                session_id,
                active_seconds=time.monotonic() - started,
                customer_revision=epoch,
                task_id=self._task_id,
            )

    async def on_compress_context(
        self,
        agent: Agent,
        input_kwargs: dict,
        next_handler: Callable[..., Awaitable[None]],
    ) -> None:
        """Do not rewrite private memory for a context-isolated handoff."""

        if self._mode in {"isolated", "references"}:
            return
        await next_handler(**input_kwargs)


__all__ = ["SharedContextIsolationMiddleware"]
