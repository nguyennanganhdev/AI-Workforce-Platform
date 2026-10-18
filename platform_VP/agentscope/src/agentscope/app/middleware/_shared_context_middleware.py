"""Keep isolated/reference handoffs out of an agent's normal memory view."""

import asyncio
import json
import time
from collections.abc import Awaitable, Callable

from ..._logging import logger
from ...agent import Agent, ContextConfig
from ...message import Msg, TextBlock, UserMsg
from ...middleware import MiddlewareBase
from ...model import ChatResponse, ChatModelBase
from .._shared_context import SharedContextBudgetError, SharedContextService
from ..storage import ContextMode, StorageBase


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
        allow_source_references: bool = False,
        reference_event_ids: tuple[str, ...] = (),
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
        self._allow_source_references = allow_source_references
        self._reference_event_ids = reference_event_ids
        self._packet_budget: int | None = None
        self._packet_model: ChatModelBase | None = None
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

    async def _refresh_packet(
        self, agent: Agent, model: ChatModelBase
    ) -> None:
        """Refresh before both compression and inference use their budgets."""
        if self._mode == "isolated":
            agent.state.middle_context.pop("shared_context_sources", None)
        packet_budget = None
        if self._allow_source_references and isinstance(agent, Agent):
            private_input = await agent._prepare_model_input()
            base_tokens = await model.count_tokens(
                private_input["messages"][:1],
                private_input["tools"],
            )
            wrapper_tokens = await model.count_tokens(
                [
                    UserMsg(
                        name="shared_context",
                        content=self._service.system_attachment("{}", 0),
                    )
                ],
                None,
            )
            packet_budget = min(
                self._service.config.packet_max_tokens,
                model.context_size
                - base_tokens
                - wrapper_tokens
                - max(
                    1,
                    int(
                        model.context_size
                        * self._service.config.output_reserve_ratio
                    ),
                )
                - self._service.config.preflight_margin_tokens
                - int(model.context_size * agent.context_config.reserve_ratio),
            )
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
        if self._team_id and self._task_id and self._mode != "isolated":
            grant = agent.state.middle_context.get(
                "shared_context_sources", {}
            )
            sources_cached = await self._service.packet_sources_available(
                self._user_id,
                self._team_id,
                self._task_id,
                grant.get("references", ()),
            )
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
            if not sources_cached or (revision, packet_budget, model) != (
                self._event_revision,
                self._packet_budget,
                self._packet_model,
            ):
                packet, tokens = await self._service.prepare_packet(
                    model=model,
                    allow_source_references=self._allow_source_references,
                    max_tokens=packet_budget,
                    user_id=self._user_id,
                    team_id=self._team_id,
                    mode=self._mode,
                    task_id=self._task_id,
                    reference_event_ids=self._reference_event_ids,
                )
                self._packet_attachment = self._service.system_attachment(
                    packet, tokens
                )
                self._event_revision = revision
                self._packet_budget = packet_budget
                self._packet_model = model
                if self._allow_source_references:
                    agent.state.middle_context["shared_context_sources"] = {
                        "team_id": self._team_id,
                        "task_id": self._task_id,
                        "references": json.loads(packet).get(
                            "source_references", []
                        ),
                    }
                await self._service.pin_session_revision(
                    agent.state.session_id,
                    team_id=self._team_id,
                    task_id=self._task_id,
                    revision=revision,
                )

    def _model_messages(self, agent: Agent, messages: list[Msg]) -> list[Msg]:
        messages = list(messages)
        if self._packet_attachment:
            if not messages:
                raise SharedContextBudgetError(
                    "Cannot attach shared context because the model input has "
                    "no system message.",
                )
            messages[0] = messages[0].model_copy(
                update={
                    "content": [
                        *messages[0].get_content_blocks(),
                        TextBlock(text=self._packet_attachment),
                    ],
                },
                deep=True,
            )
        if self._mode in {"isolated", "references"}:
            # ``messages[1]`` may be the agent's old private summary and is
            # intentionally excluded. Only the system prompt (which carries a
            # references packet when requested) and this turn's context delta
            # are visible.
            return [messages[0], *self._current_turn_context(agent)]
        return messages

    async def _compression_config(
        self,
        agent: Agent,
        model: ChatModelBase,
        config: ContextConfig,
    ) -> ContextConfig:
        attachment_tokens = (
            await model.count_tokens(
                [
                    UserMsg(
                        name="shared_context", content=self._packet_attachment
                    )
                ],
                None,
            )
            if self._packet_attachment
            else 0
        )
        private_limit = (
            model.context_size
            - attachment_tokens
            - max(
                1,
                int(
                    model.context_size
                    * self._service.config.output_reserve_ratio
                ),
            )
            - self._service.config.preflight_margin_tokens
        )
        if private_limit <= 0:
            raise SharedContextBudgetError(
                "Shared context leaves no room for private history"
            )
        # Compression runs before runtime hints and late inbox delivery.
        trigger = min(
            config.trigger_ratio, private_limit / agent.model.context_size
        )
        return config.model_copy(
            update={
                "trigger_ratio": trigger,
                "reserve_ratio": min(config.reserve_ratio, trigger * 0.5),
                "context_buffer_ratio": min(
                    config.context_buffer_ratio, max(0, trigger - 0.01)
                ),
                "compression_fallback_to_truncation": False,
                "compression_retry_drop_oldest": False,
            }
        )

    async def on_model_call(
        self,
        agent: Agent,
        input_kwargs: dict,
        next_handler: Callable[..., Awaitable[ChatResponse]],
    ) -> ChatResponse:
        await self._refresh_packet(agent, input_kwargs["current_model"])
        filtered = self._model_messages(agent, input_kwargs["messages"])

        current_model = input_kwargs["current_model"]
        prompt_tokens = await current_model.count_tokens(
            filtered,
            input_kwargs["tools"],
        )
        prompt_limit = (
            current_model.context_size
            - max(
                1,
                int(
                    current_model.context_size
                    * self._service.config.output_reserve_ratio
                ),
            )
            - self._service.config.preflight_margin_tokens
        )
        if (
            prompt_tokens > prompt_limit
            and self._mode == "task"
            and isinstance(agent, Agent)
        ):
            config = await self._compression_config(
                agent, current_model, agent.context_config
            )
            private_tokens = await agent.model.count_tokens(
                **await agent._prepare_model_input()
            )
            config = config.model_copy(
                update={
                    "trigger_ratio": min(
                        config.trigger_ratio,
                        private_tokens / agent.model.context_size,
                    ),
                }
            )
            await agent.compress_context(context_config=config)
            await self._refresh_packet(agent, current_model)
            rebuilt = await agent._prepare_model_input()
            input_kwargs = {**input_kwargs, **rebuilt}
            filtered = self._model_messages(agent, rebuilt["messages"])
            prompt_tokens = await current_model.count_tokens(
                filtered, input_kwargs["tools"]
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
                current_model.context_size
                * self._service.config.output_reserve_ratio,
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
                    [
                        Msg(
                            name=agent.name,
                            role="assistant",
                            content=response.content,
                        )
                    ],
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
        await self._refresh_packet(agent, agent.model)
        config = await self._compression_config(
            agent,
            agent.model,
            input_kwargs.get("context_config") or agent.context_config,
        )
        await next_handler(**{**input_kwargs, "context_config": config})


__all__ = ["SharedContextIsolationMiddleware"]
