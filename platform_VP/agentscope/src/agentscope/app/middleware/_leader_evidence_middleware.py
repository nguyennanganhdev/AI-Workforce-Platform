"""Hold a delegated Leader reply until workers provide current evidence."""

import asyncio
import json
import os
from collections.abc import AsyncGenerator, Callable

from ..._utils._common import _generate_id
from ...agent import Agent
from ...event import (
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
from ...types import ReplyFinishedReason
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
        wait_seconds: float | None = None,
        max_nudges: int = 2,
        max_rounds: int = 4,
        on_verified_answer: Callable[[str], None] | None = None,
    ) -> None:
        self._on_verified_answer = on_verified_answer
        self._storage = storage
        self._shared_context = shared_context
        self._user_id = user_id
        self._agent_id = agent_id
        self._session_id = session_id
        # One budget for the whole reply, not per wait: a two-stage plan
        # (lookups, then a dependent calculation) must not run out of
        # patience after the first stage. Default leaves room for the
        # per-assignment active-time budget (180 s) plus delivery.
        self._wait_seconds = (
            float(os.getenv("WORKFORCE_LEADER_WAIT_SECONDS", "240"))
            if wait_seconds is None
            else wait_seconds
        )
        self._max_nudges = max_nudges
        self._max_rounds = max_rounds
        self._safety_poll_seconds = 5.0

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
                if result is not None and call.name == "AgentInvite":
                    actual = result.metadata.get("invited_targets")
                    if isinstance(actual, list):
                        targets.update(str(t).strip().casefold() for t in actual)
                        continue
                if result is None or result.state != ToolResultState.SUCCESS:
                    continue
                try:
                    payload = json.loads(call.input)
                except (TypeError, ValueError):
                    continue
                if call.name == "AgentInvite":
                    target = str(payload.get("target") or call.id)
                    targets.add(target.strip().casefold())
                elif call.name == "TeamSay" and (
                    (
                        payload.get("kind") in {"handoff", "question"}
                        and payload.get("resolution") not in {"complete", "stop"}
                    )
                    or (
                        payload.get("kind") == "review"
                        and payload.get("decision") == "challenge"
                    )
                ):
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
        team_exists, completed, _errors, _verified, waiting = await self._status()
        pending = await self._review() if team_exists and not waiting else []
        # ``completed`` counts the members that reported or failed. Every
        # dispatched member must have: one queued behind another's report has
        # not run yet, and answering without it drops its part of the work.
        return team_exists and not pending and (
            waiting or completed >= max(expected, 1)
        )

    async def _review(self) -> list[str]:
        session = await self._storage.get_session(
            self._user_id, self._agent_id, self._session_id
        )
        if session is None or session.team_id is None:
            return []
        return await self._shared_context.collaboration_review(
            self._user_id, session.team_id, self._session_id
        )

    async def _wait_until_ready(self, expected: int, deadline: float) -> bool:
        """Wait for the team, waking on context-change signals.

        Each teammate report, Leader decision or handoff delivery publishes a
        signal; the state is re-checked when one arrives, with a slow safety
        poll in case a signal is missed (e.g. a Redis reconnect).
        """

        watch = getattr(self._shared_context, "watch", None)
        session = await self._storage.get_session(
            self._user_id, self._agent_id, self._session_id
        )
        if watch is None or session is None or session.team_id is None:
            return await self._poll_until_ready(expected, deadline, interval=0.5)
        async with watch(session.team_id) as changes:
            return await self._poll_until_ready(
                expected,
                deadline,
                interval=self._safety_poll_seconds,
                changes=changes,
            )

    async def _poll_until_ready(
        self,
        expected: int,
        deadline: float,
        *,
        interval: float,
        changes: asyncio.Queue | None = None,
    ) -> bool:
        loop = asyncio.get_running_loop()
        await self._shared_context_release()
        while True:
            if await self._ready(expected):
                return True
            if await self._pending_consent():
                return True
            remaining = deadline - loop.time()
            if remaining <= 0:
                return False
            timeout = min(interval, remaining)
            if changes is None:
                await asyncio.sleep(timeout)
            else:
                try:
                    await asyncio.wait_for(changes.get(), timeout=timeout)
                    # Coalesce a burst of signals into one re-check.
                    while not changes.empty():
                        changes.get_nowait()
                except TimeoutError:
                    pass
            await self._shared_context_release()

    async def _shared_context_release(self) -> None:
        """Start queued assignments whose dependencies already reported.

        TeamSay releases them on each report; this covers reports that end
        without a TeamSay (e.g. a worker run that failed).
        """

        release = getattr(self._shared_context, "deliver_ready_assignments", None)
        if release is None:
            return
        session = await self._storage.get_session(
            self._user_id, self._agent_id, self._session_id
        )
        if session is not None and session.team_id is not None:
            await release(self._user_id, session.team_id)

    async def _pending_consent(self) -> bool:
        return bool(
            await pending_chat_actions(
                self._storage,
                self._user_id,
                self._agent_id,
                self._session_id,
            )
        )

    async def _question(self) -> str | None:
        session = await self._storage.get_session(
            self._user_id, self._agent_id, self._session_id
        )
        if session is None or session.team_id is None:
            return None
        return await self._shared_context.pending_user_question(
            self._user_id, session.team_id
        )

    async def _unsupported_claims(self, content: str) -> tuple[str, ...]:
        session = await self._storage.get_session(
            self._user_id, self._agent_id, self._session_id
        )
        if session is None or session.team_id is None:
            return ()
        return await self._shared_context.unsupported_customer_reply_claims(
            self._user_id,
            session.team_id,
            content,
        )

    async def _has_unseen_evidence(self) -> bool:
        """Detect facts that arrived after the model input was pinned."""

        session = await self._storage.get_session(
            self._user_id,
            self._agent_id,
            self._session_id,
        )
        if session is None or session.team_id is None:
            return False
        task_id = await self._shared_context.active_task_id(
            self._user_id,
            session.team_id,
        )
        seen = await self._shared_context.session_revision(
            self._session_id,
            team_id=session.team_id,
            task_id=task_id,
        )
        if seen is None:
            return False
        latest = await self._shared_context.latest_event_revision(
            self._user_id,
            session.team_id,
            task_id,
        )
        return latest > seen

    @staticmethod
    def _replacement(agent: Agent, event: ReplyEndEvent, text: str):
        block_id = _generate_id()
        agent.state.append_context(agent.name, [TextBlock(id=block_id, text=text)])
        yield TextBlockStartEvent(reply_id=event.reply_id, block_id=block_id)
        yield TextBlockDeltaEvent(
            reply_id=event.reply_id, block_id=block_id, delta=text
        )
        yield TextBlockEndEvent(reply_id=event.reply_id, block_id=block_id, text=text)
        yield event.model_copy(
            update={"finished_reason": ReplyFinishedReason.COMPLETED, "error": None}
        )

    @staticmethod
    def _incomplete_text(agent: Agent) -> str:
        latest = next(
            (
                m.get_text_content() or ""
                for m in reversed(agent.state.context)
                if m.role == "user"
            ),
            "",
        )
        if any(ord(char) > 127 for char in latest):
            return "Nhóm chưa hoàn tất yêu cầu trong giới hạn xử lý hiện tại và chưa có đủ kết quả đã xác minh. Vui lòng thử lại; hệ thống sẽ tiếp tục trong đúng ticket này và không giả định kết quả còn thiếu."
        return "The team did not finish within this processing window and has insufficient verified results. Please retry; the system will continue in this ticket without inventing missing outcomes."

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
        # A clarification may contain several questions and finish with a
        # polite sentence, so checking only the final character rejects valid
        # Vietnamese/English intake turns.  It is safe when it actually asks
        # the customer, contains no externally verifiable claim, and does not
        # assert a concrete price/address/availability.
        if "?" in text:
            # A model sometimes restates a fully actionable request, promises
            # to start, then asks an explicitly optional preference.  That is
            # a deferral, not required intake: withhold it so the next
            # reasoning round must delegate to the available specialists.
            optional_deferral_markers = (
                "có muốn ưu tiên",
                "nếu không có yêu cầu thêm",
                "nếu không có ưu tiên",
                "bạn có ưu tiên nào",
                "would you prefer",
                "do you have any preference",
                "if you have no preference",
                "if there are no other requirements",
            )
            if any(marker in normalized for marker in optional_deferral_markers):
                return False
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
            clarification_markers = (
                "bạn",
                "anh/chị",
                "vui lòng",
                "cho biết",
                "xác nhận",
                "you",
                "could you",
                "please provide",
                "what ",
                "where ",
                "when ",
                "which ",
                "how many",
            )
            return not risky and any(
                marker in normalized for marker in clarification_markers
            )
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
        rounds = 0
        dispatched_seen = 0
        deadline = asyncio.get_running_loop().time() + self._wait_seconds
        buffered_text: list[object] = []

        def discard_text():
            # Withheld claims must not survive in private memory either.
            for message in agent.state.context:
                if message.id == agent.state.reply_id:
                    message.content = [
                        block
                        for block in message.content
                        if not isinstance(block, TextBlock)
                    ]
            buffered_text.clear()

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

            if event.finished_reason not in {
                ReplyFinishedReason.COMPLETED,
                ReplyFinishedReason.EXCEED_MAX_ITERS,
            }:
                discard_text()
                yield event
                continue

            question = await self._question()
            if question:
                discard_text()
                for replacement in self._replacement(agent, event, question):
                    yield replacement
                continue

            expected = self._expected_reports(agent)
            pending_assignments = await self._review()
            new_dispatch = expected > dispatched_seen
            current_text = self._buffered_text(buffered_text)
            _team_exists, completed, errors, _verified, waiting = await self._status()
            has_current_evidence = completed > 0 or errors > 0 or waiting

            if (new_dispatch or pending_assignments) and rounds < self._max_rounds:
                # Even if the worker finished quickly, this text was authored
                # before its report reached the Leader's model context. Drop
                # it and force a fresh reasoning round after the inbox drain.
                # Every new dispatch (a dependent stage, a challenge) waits
                # again within the same reply budget.
                dispatched_seen = expected
                ready = await self._wait_until_ready(max(expected, 1), deadline)
                discard_text()
                if await self._pending_consent():
                    # The structured pending action is already presented in
                    # chat. Parking for consent is successful orchestration,
                    # not missing evidence and not a reason to retry workers.
                    yield event
                    continue
                if not ready:
                    # Never promise a later update unless a durable workflow
                    # owns that delivery. A bounded timeout is incomplete.
                    for replacement in self._replacement(
                        agent, event, self._incomplete_text(agent)
                    ):
                        yield replacement
                    continue
                rounds += 1
                self._nudge(
                    agent,
                    "Read the newly arrived worker reports from the inbox and "
                    "shared context. Check each report against its done_when; "
                    "if one misses it, TeamSay(kind='review', decision='challenge') "
                    "with exactly what is missing. Otherwise answer the customer "
                    "using only that current evidence. Do not emit a progress "
                    "placeholder.",
                )
                continue

            review = await self._review()
            if review and nudges < self._max_nudges:
                discard_text()
                nudges += 1
                self._nudge(
                    agent,
                    "Review incoming results/proposals/conflicts with TeamSay(kind='review', decision='accept'|'challenge'|'stop'), or request concrete missing work. Approve only genuine customer questions. Do not forward a worker's internal dependency to the customer.",
                )
                continue
            if review:
                discard_text()
                for replacement in self._replacement(
                    agent, event, self._incomplete_text(agent)
                ):
                    yield replacement
                continue
            if await self._has_unseen_evidence():
                discard_text()
                if nudges >= self._max_nudges:
                    for replacement in self._replacement(
                        agent, event, self._incomplete_text(agent)
                    ):
                        yield replacement
                    continue
                nudges += 1
                self._nudge(
                    agent,
                    "New verified team evidence arrived after the previous "
                    "model snapshot. Re-read Shared Context and synthesize "
                    "one complete customer answer from the newest revision. "
                    "Do not emit an intermediate progress update.",
                )
                continue
            safe_without_evidence = self._safe_without_evidence(current_text)
            # A long factual answer does not become a safe clarification just
            # because it ends with "Which option do you want?".  Validate
            # concrete anchors for every non-empty reply.  The support set also
            # contains customer-confirmed messages, so repeating dates/budgets
            # while asking a real clarification remains valid.
            unsupported = (
                await self._unsupported_claims(current_text)
                if current_text
                else ()
            )
            if unsupported:
                discard_text()
                if nudges >= self._max_nudges:
                    for replacement in self._replacement(
                        agent, event, self._incomplete_text(agent)
                    ):
                        yield replacement
                    continue
                nudges += 1
                self._nudge(
                    agent,
                    "Evidence Gate rejected unsupported concrete names or "
                    "numbers: "
                    + ", ".join(unsupported[:12])
                    + ". Rewrite the customer answer using only exact names, "
                    "numbers and facts present in current verified reports. "
                    "Do not add examples from model memory.",
                )
                continue
            if has_current_evidence or safe_without_evidence:
                for text_event in buffered_text:
                    yield text_event
                buffered_text.clear()
                if has_current_evidence and self._on_verified_answer is not None:
                    session = await self._storage.get_session(
                        self._user_id, self._agent_id, self._session_id
                    )
                    if session is not None and session.team_id is not None:
                        try:
                            self._on_verified_answer(session.team_id)
                        except Exception:  # noqa: BLE001 - learning is optional
                            pass
                yield event
                continue

            discard_text()
            if nudges >= self._max_nudges:
                for replacement in self._replacement(
                    agent, event, self._incomplete_text(agent)
                ):
                    yield replacement
                continue

            nudges += 1
            self._nudge(
                agent,
                (
                    "This customer-facing answer has no current worker or MCP "
                    "evidence. Delegate the domain task to a published agent, "
                    "ask one concise REQUIRED clarification question, or explicitly say "
                    "that the capability/data cannot be verified. Never supply "
                    "names, prices, addresses, availability or recommendations "
                    "from model memory. If the user already supplied the core "
                    "inputs needed for read-only lookup, delegate now; do not "
                    "delay work to ask optional preferences."
                ),
            )


__all__ = ["LeaderEvidenceMiddleware"]
