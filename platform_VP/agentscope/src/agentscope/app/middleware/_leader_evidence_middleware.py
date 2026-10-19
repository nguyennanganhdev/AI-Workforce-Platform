"""Coordinate Workforce Leader turns without validating business claims."""

import json
import re
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
from ...types import ErrorInfo, ErrorType, ReplyFinishedReason
from .._chat_consent import pending_chat_actions
from .._shared_context import SharedContextService
from ..storage import StorageBase


class LeaderEvidenceMiddleware(MiddlewareBase):
    """Keep Leader delegation and finalization event-driven."""

    def __init__(
        self,
        storage: StorageBase,
        shared_context: SharedContextService,
        user_id: str,
        agent_id: str,
        session_id: str,
        *,
        wait_seconds: float = 60.0,
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
                if result is not None and call.name == "AgentInvite":
                    started = result.metadata.get("started_targets")
                    if isinstance(started, list):
                        targets.update(str(t).strip().casefold() for t in started)
                        continue
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
                elif (
                    call.name == "TeamSay"
                    and payload.get("kind")
                    in {
                        "handoff",
                        "question",
                    }
                    and payload.get("resolution") not in {"complete", "stop"}
                ):
                    target = str(payload.get("to") or call.id)
                    targets.add(target.strip().casefold())
        return len(targets)

    async def _review(self) -> list[str]:
        session = await self._storage.get_session(
            self._user_id, self._agent_id, self._session_id
        )
        if session is None or session.team_id is None:
            return []
        return await self._shared_context.collaboration_review(
            self._user_id, session.team_id, self._session_id
        )

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

    async def _workers_running(self) -> bool:
        """Sleep for active work, but allow the Leader to review peer reports."""

        session = await self._storage.get_session(
            self._user_id, self._agent_id, self._session_id
        )
        if session is None or session.team_id is None:
            return False
        record = await self._shared_context.storage.get_team_shared_context(
            self._user_id, session.team_id
        )
        task = record.state.tasks.get(record.state.active_task_id) if record else None
        return bool(
            task
            and any(
                sid != self._session_id
                and branch.customer_revision == task.latest_customer_revision
                and branch.status in {"running", "waiting_peer"}
                for sid, branch in task.collaboration.items()
            )
        )

    async def on_reasoning(self, agent, input_kwargs, next_handler):
        """Stop this run after delegation; a peer reply starts a fresh run."""

        question = await self._question()
        expected = self._expected_reports(agent)
        await self._review()
        if expected or question or await self._workers_running():
            agent.state.append_context(
                agent.name,
                [
                    HintBlock(
                        hint=(
                            "Delegated work is now owned by another participant. "
                            "End this run without another model call. A later "
                            "peer reply or customer answer will start a fresh run."
                        ),
                    ),
                ],
            )
            yield agent.state.context[-1]
            return
        async for event in next_handler(**input_kwargs):
            yield event

    async def _has_unseen_context(self) -> bool:
        """Detect team updates that arrived after the model input was pinned."""

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

    async def _seal_final_answer(self) -> bool:
        """Freeze exactly the Shared Context revision used for synthesis."""

        session = await self._storage.get_session(
            self._user_id,
            self._agent_id,
            self._session_id,
        )
        if session is None or session.team_id is None:
            return True
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
        return await self._shared_context.seal_final_answer(
            self._user_id,
            session.team_id,
            self._session_id,
            expected_event_revision=seen,
        )

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
    def _incomplete_text(agent: Agent, partial_text: str = "") -> str:
        del agent
        partial = LeaderEvidenceMiddleware._usable_partial_text(partial_text)
        limitation = (
            "Phần còn thiếu chưa có đủ bằng chứng để xác minh, nên tôi không "
            "suy đoán. Không có tác vụ nền nào được cam kết sau câu trả lời này."
        )
        if partial:
            return f"{partial}\n\n{limitation}"
        return (
            "Hiện chưa có đủ kết quả đã xác minh để đưa ra một phương án hoàn "
            f"chỉnh. {limitation}"
        )

    @staticmethod
    def _usable_partial_text(text: str) -> str:
        """Keep useful synthesis, never a promise/status placeholder."""

        forbidden = (
            "hãy chờ",
            "xin chờ",
            "vui lòng chờ",
            "đang chờ",
            "sẽ tiếp tục",
            "sẽ cập nhật",
            "tôi sẽ",
            "nhóm chưa hoàn tất",
            "xin leader",
            "leader cho hướng",
            "cho hướng xử lý",
            "please wait",
            "will continue",
            "will update",
            "after successful team message",
            "end this run",
            "must end run",
        )
        chunks = re.split(r"(?<=[.!?])\s+|[\r\n]+", text.strip())
        useful = [
            chunk.strip()
            for chunk in chunks
            if chunk.strip()
            and not any(
                marker in " ".join(chunk.casefold().split()) for marker in forbidden
            )
        ]
        return " ".join(useful)

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
    def _is_customer_intake(text: str) -> bool:
        """Return whether the fixed Leader is asking for customer input."""

        normalized = " ".join(text.casefold().split())
        return any(
            marker in normalized
            for marker in (
                "bạn cung cấp",
                "bạn cho biết",
                "bạn xuất phát từ đâu",
                "vui lòng cung cấp",
                "vui lòng cho biết",
                "hãy cung cấp",
                "hãy cho biết",
                "where will you depart",
                "where are you departing",
                "how many people",
                "please provide",
                "please tell me",
                "could you provide",
                "could you tell me",
            )
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
                        {"label": "System", "sublabel": "Team Coordination"},
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
        """Buffer customer text and validate only settled Leader replies."""

        nudges = 0
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

            expected = self._expected_reports(agent)
            await self._review()
            question = await self._question()
            if expected or question or await self._workers_running():
                # Delegation and specialist-owned clarification are terminal
                # for this run. The recipient/customer response will wake a
                # new run with a fresh Shared Context snapshot.
                discard_text()
                yield event.model_copy(
                    update={
                        "finished_reason": ReplyFinishedReason.COMPLETED,
                        "error": None,
                    }
                )
                return

            current_text = self._buffered_text(buffered_text)
            if not self._usable_partial_text(current_text):
                discard_text()
                if nudges >= self._max_nudges:
                    yield event.model_copy(
                        update={
                            "finished_reason": ReplyFinishedReason.ERROR,
                            "error": ErrorInfo(
                                type=ErrorType.INTERNAL,
                                message="Leader chưa tạo được câu trả lời tổng hợp.",
                            ),
                        }
                    )
                    return
                nudges += 1
                self._nudge(
                    agent,
                    "TeamSay resolution=complete/stop closes internal work, "
                    "not this run. Review any remaining assignments, then "
                    "synthesize the verified results and limitations for the "
                    "customer in Vietnamese. Do not emit an instruction to "
                    "end the run or a progress-only placeholder.",
                )
                continue
            if self._is_customer_intake(current_text):
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
                    "The fixed Workforce Leader must not ask the customer for "
                    "task-specific information. Create the team if needed and "
                    "delegate intake to the single best-matched specialist. "
                    "Only that specialist may call "
                    "TeamSay(kind=requires_user_input) and ask the customer.",
                )
                continue

            review = await self._review()
            if review and nudges < self._max_nudges:
                discard_text()
                nudges += 1
                self._nudge(
                    agent,
                    "Review incoming peer results/proposals/conflicts. Resolve "
                    "assignments with TeamSay resolution=complete/stop/verify, "
                    "then synthesize every useful verified partial result. Do "
                    "not ask the customer or Leader to choose a routine next "
                    "step and do not forward an internal dependency.",
                )
                continue
            if review:
                discard_text()
                for replacement in self._replacement(
                    agent,
                    event,
                    self._incomplete_text(agent, current_text),
                ):
                    yield replacement
                continue
            if await self._has_unseen_context():
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
                    "New team context arrived after the previous "
                    "model snapshot. Re-read Shared Context and synthesize "
                    "one complete customer answer from the newest revision. "
                    "Do not emit an intermediate progress update.",
                )
                continue
            if not await self._seal_final_answer():
                discard_text()
                if nudges >= self._max_nudges:
                    for replacement in self._replacement(
                        agent,
                        event,
                        self._incomplete_text(agent, current_text),
                    ):
                        yield replacement
                    continue
                nudges += 1
                self._nudge(
                    agent,
                    "The team state changed before finalization or still "
                    "contains open work. Re-read Shared Context. Resolve or "
                    "stop each assignment, then synthesize verified results "
                    "and explicit limitations without promising future work.",
                )
                continue
            for text_event in buffered_text:
                yield text_event
            buffered_text.clear()
            yield event


__all__ = ["LeaderEvidenceMiddleware"]
