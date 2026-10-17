# -*- coding: utf-8 -*-
"""The team member middleware that should be equipped with the member agents
within a team."""

import json
from collections import Counter
from collections.abc import Awaitable
from typing import AsyncGenerator, Callable

from ..._utils._common import _generate_id, _json_loads_with_repair
from ...agent import Agent
from ...event import (
    HintBlockEvent,
    ReplyEndEvent,
    TextBlockDeltaEvent,
    TextBlockEndEvent,
    TextBlockStartEvent,
)
from ...message import (
    HintBlock,
    TextBlock,
    ToolCallBlock,
    ToolResultBlock,
    ToolResultState,
)
from ...middleware import MiddlewareBase
from ...tool import ToolChoice, ToolResponse
from ...types import ErrorInfo, ErrorType, ReplyFinishedReason
from .._tool._team_say import STALE_CONTEXT_RESULT
from ._leader_evidence_middleware import LeaderEvidenceMiddleware


class TeamMemberLoopMiddleware(MiddlewareBase):
    """The team member loop engineering middleware, that requires:

    1. The member should end its reply by calling `TeamSay` to report to the
     current reply owner (normally the team leader).
    2. When exceeds the max iteration numbers, the agent is guided to send
    reply owner a message to ask for permission to continue the operation.

    A member that keeps ending without reporting is nudged at most
    ``max_nudges`` times; after that the reply is released as an
    ``ERROR`` so it terminates and the failure travels the normal
    error path instead of looping under the session lock forever.
    """

    def __init__(
        self,
        leader_name: str,
        max_nudges: int = 3,
        pending_question: Callable[[], Awaitable[str | None]] | None = None,
        require_report: bool = True,
        require_input_readiness: bool = False,
    ) -> None:
        """Initialize the middleware.

        Args:
            leader_name (`str`):
                The current reply owner's routable team name, i.e. the only
                valid
                ``TeamSay(to=...)`` target that counts as a report.
            max_nudges (`int`, defaults to 3):
                How many times one reply may be forced to continue
                before it is failed instead.
        """
        super().__init__()
        self._leader_name: str = leader_name
        self._max_nudges: int = max_nudges
        self._pending_question = pending_question
        self._paused = False
        self._require_report = require_report
        self._require_input_readiness = require_input_readiness

    @staticmethod
    def _input_is_ready(agent: "Agent") -> bool:
        """Return whether InputReady succeeded in this reply."""

        for message in reversed(agent.state.context):
            if message.id != agent.state.reply_id or message.role != "assistant":
                continue
            blocks = message.get_content_blocks()
            results = {
                block.id: block
                for block in blocks
                if isinstance(block, ToolResultBlock)
            }
            for call in reversed(blocks):
                if not isinstance(call, ToolCallBlock) or call.name != "InputReady":
                    continue
                result = results.get(call.id)
                return bool(
                    result is not None
                    and result.state == ToolResultState.SUCCESS
                    and result.metadata.get("input_ready") is True
                )
        return False

    @staticmethod
    def _repeated_calls(agent: "Agent") -> set[tuple[str, str]]:
        counts: Counter = Counter()
        for message in agent.state.context:
            if message.id != agent.state.reply_id or message.role != "assistant":
                continue
            results = {
                b.id: b
                for b in message.get_content_blocks()
                if isinstance(b, ToolResultBlock)
            }
            for call in message.get_content_blocks():
                if not isinstance(call, ToolCallBlock) or not (
                    call.name.startswith("mcp__") or call.name == "Skill"
                ):
                    continue
                result = results.get(call.id)
                if result is None:
                    continue
                try:
                    args = json.dumps(
                        json.loads(call.input), sort_keys=True, ensure_ascii=False
                    )
                except (ValueError, TypeError):
                    args = call.input
                output = (
                    result.output
                    if isinstance(result.output, str)
                    else [
                        b.model_dump(
                            mode="json", exclude={"id", "created_at", "finished_at"}
                        )
                        for b in result.output
                    ]
                )
                counts[
                    (call.name, args, result.state, json.dumps(output, sort_keys=True))
                ] += 1
        return {
            (name, args) for (name, args, _, _), count in counts.items() if count >= 3
        }

    async def on_reasoning(self, agent, input_kwargs, next_handler):
        self._paused = False
        if self._pending_question and await self._pending_question():
            self._paused = True
            # No model call or new tool work while the customer owes an answer.
            agent.state.append_context(
                agent.name,
                [
                    HintBlock(
                        hint="Internal assignment paused; wait for its dependency or reply-owner decision. Do not ask the customer for another agent's output."
                    )
                ],
            )
            yield agent.state.context[-1]
            return
        if (
            self._last_tool_call_reports_to_leader(agent)
            or LeaderEvidenceMiddleware._expected_reports(agent)
        ):
            self._paused = True
            agent.state.append_context(
                agent.name,
                [HintBlock(hint="Message delivered. End this run; a later reply or mention starts a fresh run.")],
            )
            yield agent.state.context[-1]
            return
        if self._repeated_calls(agent) and not self._last_tool_call_reports_to_leader(
            agent
        ):
            agent.state.append_context(
                agent.name,
                [
                    HintBlock(
                        hint=(
                            "Repeated tool calls returned identical results with no progress. "
                            "Call TeamSay(to=null, kind='requires_user_input') "
                            "for genuinely customer-owned missing information, or "
                            f"TeamSay(to={self._leader_name!r}, kind='result') "
                            "to report the blocker. "
                            "Do not retry tools or invent an external identifier/outcome."
                        ),
                    )
                ],
            )
            input_kwargs = {**input_kwargs, "tool_choice": ToolChoice(mode="TeamSay")}
        async for event in next_handler(**input_kwargs):
            yield event

    async def on_acting(self, agent, input_kwargs, next_handler):
        call = input_kwargs["tool_call"]
        pause_reason = await self._pending_question() if self._pending_question else None
        # Finish the independent requests already generated in this batch.
        paused = bool(pause_reason) and not (
            pause_reason == "waiting_peer" and call.name == "TeamSay"
        )
        try:
            args = json.dumps(
                json.loads(call.input), sort_keys=True, ensure_ascii=False
            )
        except (ValueError, TypeError):
            args = call.input
        if self._require_input_readiness and not self._input_is_ready(agent):
            allowed = call.name == "InputReady"
            if call.name == "TeamSay":
                try:
                    kind = _json_loads_with_repair(call.input).get("kind", "result")
                except Exception:  # noqa: BLE001  # malformed model tool input
                    kind = None
                allowed = kind in {
                    "requires_user_input",
                    "answer",
                    "result",
                    "error",
                    "conflict",
                }
            if not allowed:
                yield ToolResponse(
                    content=[
                        TextBlock(
                            text=(
                                "Input readiness required. Call InputReady first with exact customer evidence, "
                                "or call TeamSay(kind='requires_user_input', to=null) for all missing inputs. "
                                "No business tool or peer handoff was executed."
                            ),
                        ),
                    ],
                    state=ToolResultState.ERROR,
                )
                return
        if paused or (call.name, args) in self._repeated_calls(agent):
            yield ToolResponse(
                content=[
                    TextBlock(
                        text=(
                            "Execution paused: waiting for customer input. No tool was executed."
                            if paused
                            else "Repeated unchanged result: stop retrying and report the blocker via TeamSay. No tool was executed."
                        )
                    )
                ],
                state=ToolResultState.ERROR,
            )
            return
        async for result in next_handler(**input_kwargs):
            yield result

    def _last_tool_call_reports_to_leader(self, agent: "Agent") -> bool:
        """Whether this reply's final tool call successfully reports back.

        Args:
            agent (`Agent`):
                The replying member agent, read for its context and
                the id of the reply in flight.

        Returns:
            `bool`:
                ``True`` when the reply's last tool call is a
                ``TeamSay`` explicitly addressed to the reply owner that
                returned ``SUCCESS``. Worker broadcasts are never valid
                reports.
        """
        for msg in reversed(agent.state.context):
            if (
                msg.id != agent.state.reply_id
                or msg.role != "assistant"
                or msg.name != agent.name
            ):
                continue

            blocks = msg.get_content_blocks()
            last_tool_call = next(
                (
                    block
                    for block in reversed(blocks)
                    if isinstance(block, ToolCallBlock)
                ),
                None,
            )
            if last_tool_call is None:
                continue

            # The last tool action must be a successful TeamSay addressed to
            # the reply owner. A later non-TeamSay tool therefore invalidates
            # an earlier progress report.
            if last_tool_call.name != "TeamSay":
                return False
            try:
                kwargs = _json_loads_with_repair(last_tool_call.input)
            except Exception:  # pylint: disable=broad-except
                # Unparsable arguments (e.g. a truncated stream) cannot
                # have produced a successful report.
                return False
            result = next(
                (
                    block
                    for block in blocks
                    if isinstance(block, ToolResultBlock)
                    and block.id == last_tool_call.id
                ),
                None,
            )
            if result is None or result.state != ToolResultState.SUCCESS:
                return False
            declared_kind = kwargs.get("kind")
            kind = result.metadata.get("kind", declared_kind or "result")
            if kind == "requires_user_input" and self._is_null_target(
                kwargs.get("to"),
            ):
                return True
            if kind == "progress" or not kwargs.get("to"):
                return False
            if kwargs.get("to") != self._leader_name and declared_kind not in {
                "handoff",
                "question",
                "answer",
                "result",
            }:
                return False
            return True

        return False

    @staticmethod
    def _is_null_target(value: object) -> bool:
        """Accept JSON null and the common model string spellings equally."""

        return value is None or (
            isinstance(value, str)
            and value.strip().casefold() in {"null", "none"}
        )

    @staticmethod
    def _pending_customer_question(agent: "Agent") -> str | None:
        """Return the last successfully registered direct customer question."""

        for msg in reversed(agent.state.context):
            if msg.id != agent.state.reply_id or msg.role != "assistant":
                continue
            blocks = msg.get_content_blocks()
            call = next(
                (
                    block
                    for block in reversed(blocks)
                    if isinstance(block, ToolCallBlock)
                ),
                None,
            )
            if call is None or call.name != "TeamSay":
                return None
            try:
                kwargs = _json_loads_with_repair(call.input)
            except Exception:  # pylint: disable=broad-except
                return None
            result = next(
                (
                    block
                    for block in blocks
                    if isinstance(block, ToolResultBlock) and block.id == call.id
                ),
                None,
            )
            if (
                result is not None
                and result.state == ToolResultState.SUCCESS
                and result.metadata.get("kind", kwargs.get("kind"))
                == "requires_user_input"
                and TeamMemberLoopMiddleware._is_null_target(kwargs.get("to"))
            ):
                content = kwargs.get("content")
                return content.strip() if isinstance(content, str) else None
            return None
        return None

    @staticmethod
    def _reply_has_customer_question(agent: "Agent", question: str) -> bool:
        normalized = " ".join(question.casefold().split())
        return any(
            isinstance(block, TextBlock)
            and normalized in " ".join(block.text.casefold().split())
            for msg in agent.state.context
            if msg.id == agent.state.reply_id and msg.role == "assistant"
            for block in msg.get_content_blocks()
        )

    def _last_report_used_stale_context(self, agent: "Agent") -> bool:
        """Whether the last TeamSay was rejected by the revision guard."""

        for msg in reversed(agent.state.context):
            if msg.id != agent.state.reply_id or msg.role != "assistant":
                continue
            blocks = msg.get_content_blocks()
            call = next(
                (
                    block
                    for block in reversed(blocks)
                    if isinstance(block, ToolCallBlock)
                ),
                None,
            )
            if call is None or call.name != "TeamSay":
                return False
            result = next(
                (
                    block
                    for block in blocks
                    if isinstance(block, ToolResultBlock) and block.id == call.id
                ),
                None,
            )
            if result is None or result.state != ToolResultState.ERROR:
                return False
            output = (
                result.output
                if isinstance(result.output, str)
                else "\n".join(
                    block.text
                    for block in result.output
                    if isinstance(block, TextBlock)
                )
            )
            return STALE_CONTEXT_RESULT in output
        return False

    async def on_reply(
        self,
        agent: "Agent",
        input_kwargs: dict,
        next_handler: Callable[..., AsyncGenerator],
    ) -> AsyncGenerator:
        """Discard normal `ReplyEndEvent`s until `TeamSay` reports success.

        Args:
            agent (`Agent`):
                The replying member agent. Its context receives the
                reminder hints, and its ``cur_iter`` is relaxed so a
                nudged reply can still act.
            input_kwargs (`dict`):
                The reply arguments, forwarded to ``next_handler``
                unchanged.
            next_handler (`Callable[..., AsyncGenerator]`):
                The rest of the middleware chain.

        Yields:
            `AgentEvent | Msg`:
                Everything the inner reply produces, except a
                ``ReplyEndEvent`` that arrives without a successful
                report: that one is replaced by a reminder
                ``HintBlockEvent`` (forcing another round) or, once the
                nudge budget is spent, by an ``ERROR`` reply-end event.
        """
        nudges = 0

        async for evt in next_handler(**input_kwargs):
            if not isinstance(evt, ReplyEndEvent):
                yield evt
                continue

            # For the ReplyEndEvent
            question = self._pending_customer_question(agent)
            if question and not self._reply_has_customer_question(
                agent,
                question,
            ):
                block_id = _generate_id()
                agent.state.append_context(
                    agent.name,
                    [TextBlock(id=block_id, text=question)],
                )
                yield TextBlockStartEvent(
                    reply_id=evt.reply_id,
                    block_id=block_id,
                )
                yield TextBlockDeltaEvent(
                    reply_id=evt.reply_id,
                    block_id=block_id,
                    delta=question,
                )
                yield TextBlockEndEvent(
                    reply_id=evt.reply_id,
                    block_id=block_id,
                    text=question,
                )
            if self._paused:
                yield evt
                continue
            if self._last_tool_call_reports_to_leader(agent):
                # The report has been delivered successfully, so let the
                # original reply-end event escape the middleware chain.
                yield evt
                continue

            if not self._require_report:
                # An explicitly mentioned agent can answer the user directly.
                yield evt
                continue

            if self._last_report_used_stale_context(agent):
                yield ReplyEndEvent(
                    session_id=evt.session_id,
                    reply_id=evt.reply_id,
                    finished_reason=ReplyFinishedReason.ERROR,
                    error=ErrorInfo(
                        type=ErrorType.INTERNAL,
                        message=(
                            "Shared context changed while this worker was "
                            "running. Start a fresh worker turn so it reloads "
                            "the latest ticket context before recomputing."
                        ),
                    ),
                )
                continue

            if evt.finished_reason not in (
                ReplyFinishedReason.COMPLETED,
                ReplyFinishedReason.EXCEED_MAX_ITERS,
            ):
                # Interrupted / already-failed endings cannot be continued
                # by swallowing their ReplyEndEvent.  Forward unchanged.
                # TODO: When the subagent fails, the leader should be aware
                #  of that.
                yield evt
                continue

            if nudges >= self._max_nudges:
                # Out of patience: end the reply as an error so it stops
                # holding the session, and let the error path report it.
                yield ReplyEndEvent(
                    session_id=evt.session_id,
                    reply_id=evt.reply_id,
                    finished_reason=ReplyFinishedReason.ERROR,
                    error=ErrorInfo(
                        type=ErrorType.INTERNAL,
                        message=(
                            f"{agent.name} ended {nudges} replies in a row "
                            f"without reporting to {self._leader_name} via "
                            f"TeamSay; giving up on this turn."
                        ),
                    ),
                )
                continue

            nudges += 1
            if evt.finished_reason == ReplyFinishedReason.EXCEED_MAX_ITERS:
                instruction = (
                    "<system-reminder>You have reached the maximum number "
                    f"of ReAct iterations ({agent.react_config.max_iters}). "
                    "Call `TeamSay` now to report to the reply owner "
                    f"{self._leader_name!r} and ask for "
                    "permission to continue.</system-reminder>"
                )
            else:
                instruction = (
                    "<system-reminder>You MUST call the tool `TeamSay` "
                    "to report to the reply owner "
                    f"{self._leader_name!r} with kind=result/error to finish your task. "
                    "If missing another agent's output, use TeamSay(to=that peer, kind=question, content=a specific task) and wait. "
                    "Progress alone is not a completed assignment. For genuinely customer-owned missing information, "
                    "use TeamSay(to=null, kind=requires_user_input) and ask the customer directly."
                    "</system-reminder>"
                )

            # Free one iteration so the agent can actually make the
            # TeamSay call. Both endings need this: a COMPLETED reply on
            # the very last iteration would otherwise come straight back
            # as EXCEED_MAX_ITERS with no reasoning in between, which the
            # agent rejects as a swallow-without-progress loop.
            agent.state.cur_iter = min(
                agent.state.cur_iter,
                agent.react_config.max_iters - 1,
            )

            hint_block = HintBlock(
                hint=instruction,
                source=json.dumps(
                    {"label": "System", "sublabel": "Reminder"},
                ),
            )
            agent.state.append_context(agent.name, [hint_block])
            yield HintBlockEvent(
                reply_id=agent.state.reply_id,
                block_id=hint_block.id,
                source=hint_block.source,
                hint=instruction,
            )
