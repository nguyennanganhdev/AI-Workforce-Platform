"""Hold a delegated Leader reply until workers provide current evidence."""

import asyncio
import json
import re
from collections.abc import AsyncGenerator, Callable

from ...agent import Agent
from ...event import (
    ReplyEndEvent,
    TextBlockDeltaEvent,
    TextBlockEndEvent,
    TextBlockStartEvent,
)
from ...message import HintBlock, ToolCallBlock, ToolResultBlock, ToolResultState
from ...middleware import MiddlewareBase
from ...types import ErrorInfo, ErrorType, ReplyFinishedReason
from .._chat_consent import pending_chat_actions
from .._shared_context import SharedContextService
from ..storage import StorageBase


class LeaderEvidenceMiddleware(MiddlewareBase):
    """Prevent a Leader from finishing a delegated turn without evidence."""

    def __init__(
        self,
        storage: StorageBase,
        shared_context: SharedContextService,
        user_id: str,
        agent_id: str,
        session_id: str,
        *,
        wait_seconds: float = 20.0,
        max_nudges: int = 2,
    ) -> None:
        self._storage = storage
        self._shared_context = shared_context
        self._user_id = user_id
        self._agent_id = agent_id
        self._session_id = session_id
        self._wait_seconds = wait_seconds
        self._max_nudges = max_nudges

    @staticmethod
    def _expected_reports(agent: Agent) -> int:
        """Count successful worker dispatches in the current reply."""

        targets: set[str] = set()
        for message in agent.state.context:
            if message.id != agent.state.reply_id or message.role != "assistant":
                continue
            blocks = message.get_content_blocks()
            results = {
                block.id: block
                for block in blocks
                if isinstance(block, ToolResultBlock)
            }
            for call in blocks:
                if not isinstance(call, ToolCallBlock):
                    continue
                result = results.get(call.id)
                if result is None or result.state != ToolResultState.SUCCESS:
                    continue
                try:
                    payload = json.loads(call.input)
                except (TypeError, ValueError):
                    continue
                if call.name == "AgentInvite":
                    target = str(payload.get("target") or call.id)
                    targets.add(target.strip().casefold())
                elif call.name == "TeamSay" and payload.get("kind") in {
                    "handoff",
                    "question",
                }:
                    target = str(payload.get("to") or call.id)
                    targets.add(target.strip().casefold())
        return len(targets)

    async def _status(self) -> tuple[bool, int, int, int, bool]:
        session = await self._storage.get_session(
            self._user_id,
            self._agent_id,
            self._session_id,
        )
        if session is None or session.team_id is None:
            return False, 0, 0, 0, False
        (
            completed,
            errors,
            verified,
            waiting,
        ) = await self._shared_context.team_evidence_status(
            self._user_id,
            session.team_id,
            leader_session_id=self._session_id,
        )
        return True, completed, errors, verified, waiting

    async def _ready(self, expected: int) -> bool:
        team_exists, completed, errors, _verified, waiting = await self._status()
        return team_exists and (waiting or completed >= expected or errors >= expected)

    async def _wait_until_ready(self, expected: int) -> bool:
        deadline = asyncio.get_running_loop().time() + self._wait_seconds
        while True:
            if await self._ready(expected):
                return True
            if await self._pending_consent():
                return True
            if asyncio.get_running_loop().time() >= deadline:
                return False
            await asyncio.sleep(0.1)

    async def _pending_consent(self) -> bool:
        return bool(
            await pending_chat_actions(
                self._storage,
                self._user_id,
                self._agent_id,
                self._session_id,
            )
        )

    @staticmethod
    def _buffered_text(events: list[object]) -> str:
        """Reconstruct only the text from the current reasoning round."""

        deltas: dict[str, list[str]] = {}
        final: dict[str, str] = {}
        order: list[str] = []
        for event in events:
            block_id = getattr(event, "block_id", "")
            if not block_id:
                continue
            if block_id not in order:
                order.append(block_id)
            if isinstance(event, TextBlockDeltaEvent):
                deltas.setdefault(block_id, []).append(event.delta)
            elif isinstance(event, TextBlockEndEvent) and event.text is not None:
                final[block_id] = event.text
        return "\n".join(
            final.get(block_id, "".join(deltas.get(block_id, []))) for block_id in order
        ).strip()

    @staticmethod
    def _safe_without_evidence(text: str) -> bool:
        """Allow greetings, clarification and explicit no-evidence replies."""

        normalized = " ".join(text.casefold().split())
        if not normalized:
            return True
        no_evidence_markers = (
            "không thể xác minh",
            "chưa thể xác minh",
            "không tìm thấy dữ liệu",
            "chưa tìm thấy dữ liệu",
            "không thể truy xuất",
            "chưa thể truy xuất",
            "thiếu agent",
            "thiếu công cụ",
            "không có agent",
            "chưa có agent",
            "không có công cụ",
            "chưa có công cụ",
            "cannot verify",
            "could not verify",
            "unable to retrieve",
            "no matching data",
            "missing agent",
            "missing tool",
            "no suitable agent",
            "no suitable tool",
            "no published agent",
        )
        if any(marker in normalized for marker in no_evidence_markers):
            return True
        platform_markers = (
            "agent builder",
            "mcp",
            "platform",
            "cài đặt",
            "settings",
        )
        if any(marker in normalized for marker in platform_markers):
            return True
        # A clarification is safe only while it contains no obvious factual
        # list, price or address-like assertion.
        if text.rstrip().endswith("?"):
            risky = any(
                marker in normalized
                for marker in (
                    " vnđ",
                    " vnd",
                    " usd",
                    "địa chỉ",
                    "address",
                    "còn phòng",
                    "available",
                )
            )
            list_like = bool(
                re.search(r"(?m)^\s*(?:[-*\u2022]|\d+[.)])\s+", text),
            )
            question_body = text.rstrip()[:-1]
            has_declarative_sentence = "." in question_body
            return not risky and not list_like and not has_declarative_sentence
        greeting_words = {
            "chào",
            "xin chào",
            "hello",
            "hi",
            "cảm ơn",
            "thank you",
            "thanks",
        }
        return len(normalized) <= 160 and any(
            normalized.startswith(word) for word in greeting_words
        )

    @staticmethod
    def _nudge(agent: Agent, message: str) -> None:
        agent.state.cur_iter = min(
            agent.state.cur_iter,
            agent.react_config.max_iters - 1,
        )
        agent.state.append_context(
            agent.name,
            [
                HintBlock(
                    hint=f"<system-reminder>{message}</system-reminder>",
                    source=json.dumps(
                        {"label": "System", "sublabel": "Evidence Gate"},
                    ),
                ),
            ],
        )

    async def on_reply(
        self,
        agent: Agent,
        input_kwargs: dict,
        next_handler: Callable[..., AsyncGenerator],
    ) -> AsyncGenerator:
        """Buffer customer text and retry after worker evidence arrives."""

        nudges = 0
        dispatched = False
        resynthesis_requested = False
        buffered_text: list[object] = []
        async for event in next_handler(**input_kwargs):
            if isinstance(
                event,
                (TextBlockStartEvent, TextBlockDeltaEvent, TextBlockEndEvent),
            ):
                buffered_text.append(event)
                continue
            if not isinstance(event, ReplyEndEvent):
                yield event
                continue

            expected = self._expected_reports(agent)
            dispatched = dispatched or expected > 0
            current_text = self._buffered_text(buffered_text)
            _team_exists, completed, errors, _verified, waiting = await self._status()
            has_current_evidence = completed > 0 or errors > 0 or waiting

            if dispatched and not resynthesis_requested:
                # Even if the worker finished quickly, this text was authored
                # before its report reached the Leader's model context. Drop
                # it and force a fresh reasoning round after the inbox drain.
                await self._wait_until_ready(max(expected, 1))
                buffered_text.clear()
                if await self._pending_consent():
                    # The structured pending action is already presented in
                    # chat. Parking for consent is successful orchestration,
                    # not missing evidence and not a reason to retry workers.
                    yield event
                    continue
                resynthesis_requested = True
                nudges += 1
                self._nudge(
                    agent,
                    "Read the newly arrived worker reports from the inbox and "
                    "shared context. Then answer the customer using only that "
                    "current evidence. Do not emit a progress placeholder.",
                )
                continue

            if has_current_evidence or self._safe_without_evidence(current_text):
                for text_event in buffered_text:
                    yield text_event
                buffered_text.clear()
                yield event
                continue

            buffered_text.clear()
            if nudges >= self._max_nudges:
                yield ReplyEndEvent(
                    session_id=event.session_id,
                    reply_id=event.reply_id,
                    finished_reason=ReplyFinishedReason.ERROR,
                    error=ErrorInfo(
                        type=ErrorType.INTERNAL,
                        message=(
                            "The Leader could not obtain current verified "
                            "worker evidence for this turn."
                        ),
                    ),
                )
                continue

            nudges += 1
            self._nudge(
                agent,
                (
                    "This customer-facing answer has no current worker or MCP "
                    "evidence. Delegate the domain task to a published agent, "
                    "ask one concise clarification question, or explicitly say "
                    "that the capability/data cannot be verified. Never supply "
                    "names, prices, addresses, availability or recommendations "
                    "from model memory."
                ),
            )


__all__ = ["LeaderEvidenceMiddleware"]
