"""Keep isolated/reference handoffs out of an agent's normal memory view."""

from collections.abc import Awaitable, Callable

from ...agent import Agent
from ...message import Msg, TextBlock
from ...middleware import MiddlewareBase
from ...model import ChatResponse
from .._shared_context import SharedContextBudgetError, SharedContextService
from ..storage import ContextMode


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
        team_id: str,
        prior_context: list[Msg] | None = None,
        packet_attachment: str = "",
    ) -> None:
        self._mode = mode
        self._service = service
        self._user_id = user_id
        self._team_id = team_id
        self._packet_attachment = packet_attachment
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
        messages = list(input_kwargs["messages"])
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
            filtered = [messages[0], *self._current_turn_context(agent)]
        else:
            filtered = messages

        current_model = input_kwargs["current_model"]
        prompt_tokens = await current_model.count_tokens(
            filtered,
            input_kwargs["tools"],
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
        await self._service.record_prompt_measurement(
            user_id=self._user_id,
            team_id=self._team_id,
            prompt_tokens=prompt_tokens,
            model_context_size=current_model.context_size,
            reserved_output_tokens=reserved_output_tokens,
            preflight_margin_tokens=(self._service.config.preflight_margin_tokens),
            token_counter=getattr(
                current_model,
                "token_counting_strategy",
                "custom-model-counter",
            ),
            budget_exceeded=budget_exceeded,
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

        return await next_handler(
            **{
                **input_kwargs,
                "messages": filtered,
            },
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
