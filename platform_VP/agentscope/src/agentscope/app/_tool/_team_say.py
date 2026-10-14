"""The TeamSay tool — sends a message to one or all team members."""

import hashlib
import json
from typing import Any, Literal

from pydantic import Field

from ...message import HintBlock, TextBlock, ToolResultState
from ...tool import ParamsBase, ToolChunk
from .._bus_ops import deliver_to_inbox
from .._shared_context import (
    CollaborationStoppedError,
    ContextDirective,
    SharedContextConcurrencyError,
    SharedContextService,
)
from .._team_turn import (
    get_team_turn,
    register_user_input_request,
    reject_user_input_request,
    return_team_reply_to_leader,
)
from ..message_bus import MessageBusKeys
from ..storage import (
    ContextDelta,
    ContextMode,
    ContextResultScope,
    TeamHandoffRecord,
)
from ..storage._utils import _ensure_team_members, _resolve_team_leader
from ._constants import HANDLE_LEN
from ._team_tool_base import _TeamToolBase

STALE_CONTEXT_RESULT = (
    "TeamSay: result stored for audit but not shared because the customer "
    "changed the task after this agent loaded context."
)

_PROGRESS_ONLY_MARKERS = (
    "đang tìm",
    "đang tra cứu",
    "đang tiến hành",
    "đang trong quá trình",
    "sẽ tiếp tục",
    "sẽ cập nhật",
    "sẽ lên lịch",
    "sẽ phối hợp",
    "sẽ tổng hợp",
    "sẽ gửi",
    "will prepare",
    "will coordinate",
    "will collect",
    "vui lòng chờ",
    "i am searching",
    "i'm searching",
    "working on",
    "will continue",
    "will update",
    "please wait",
)


class _TeamSayParams(ParamsBase):
    """Parameters for :class:`TeamSay`."""

    content: str = Field(
        description=(
            "The message text. Plain natural-language; the recipient "
            "sees it as a user message in its context."
        ),
    )
    to: str | None = Field(
        default=None,
        description=(
            "Recipient member handle. Leaders may pass ``null`` to broadcast. "
            "Workers must use a specific roster handle except when "
            "``kind=requires_user_input``: then ``null`` transfers temporary "
            "customer-clarification ownership and does not broadcast."
        ),
    )
    kind: Literal[
        "handoff",
        "question",
        "answer",
        "result",
        "progress",
        "requires_user_input",
        "user_input_proposal",
        "conflict",
        "error",
    ] = Field(
        default="result",
        description=(
            "Internal message purpose. Use ``requires_user_input`` only "
            "when the customer must provide missing information."
        ),
    )
    task_id: str | None = Field(
        default=None,
        description="Logical task id; omit to use the team's active task.",
    )
    context_mode: ContextMode = Field(
        default="task",
        description=(
            "Context loaded by recipients: task=shared task state, "
            "references=only cited events, isolated=only this handoff."
        ),
    )
    result_scope: ContextResultScope | None = Field(
        default=None,
        description=(
            "Whether this handoff becomes shared state. Defaults to shared "
            "for task/references and caller for isolated."
        ),
    )
    reference_event_ids: tuple[str, ...] = Field(
        default=(),
        max_length=50,
        description="Source event ids required in references mode.",
    )
    context_delta: ContextDelta | None = Field(
        default=None,
        description=(
            "Optional validated update to task state. Use only for facts, "
            "constraints, decisions, or outputs supported by this message."
        ),
    )
    idempotency_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description=(
            "Stable retry key. Omit normally; the runtime derives one per "
            "team turn and payload."
        ),
    )
    thread_id: str | None = Field(default=None, min_length=1, max_length=255)
    in_reply_to: str | None = Field(default=None, min_length=1, max_length=255)
    artifact_refs: tuple[str, ...] = Field(default=(), max_length=50)
    hop_count: int = Field(default=1, ge=1, le=12)
    question_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description=(
            "Stable semantic key for requires_user_input, for example "
            "missing:account_id. Optional; the runtime derives one from "
            "the question text when omitted."
        ),
    )
    resolution: Literal["complete", "stop", "verify"] | None = Field(
        default=None,
        description=(
            "Reply owner only: resolve the assignment addressed by to. "
            "complete marks the assignment finished; stop reports incomplete; "
            "verify permits at most two checks. Never closes the ticket."
        ),
    )


_LEADER_DESCRIPTION = """Send a message to a specific team member or \
broadcast to all members.

## When to Use This Tool
- Pass **new** requirements or context from the user to a specific member.
- Broadcast an update or coordination message to all members.
- Ask a member a follow-up question when you need clarification.

## When NOT to Use This Tool
- DO NOT repeatedly call this to check on a member's progress — members \
will automatically notify you via ``TeamSay`` when they finish their task. \
Wait for their message instead of polling.
- DO NOT call this right after inviting a member with ``AgentInvite``. The \
member receives the invite ``prompt`` as its initial task and reports back \
when done — just wait for their message. \
- The session is not in a team yet (call ``TeamCreate`` first).
- You want to talk to yourself — use your own reasoning.

## Important
- Each invited member starts working immediately. When it finishes its task, \
it calls ``TeamSay`` to report results back to you. You do not need to prompt \
it again — just wait for its reply.
- **DO NOT** reply to a member's report message unless you have further \
questions or requirements. ``TeamSay`` is for coordination, not chit-chat — \
your top priority is to complete the overall task.
- The fixed Workforce Leader never asks for task-specific missing information.
  Delegate intake to the responsible specialist; that specialist can ask the
  customer directly and returns completed work for final synthesis.
- Normal team work uses ``context_mode="task"`` and
  ``result_scope="shared"`` so later members receive important results.
  Use ``isolated`` only for an independent side question; it defaults to a
  caller-only result. Use ``references`` with explicit source event ids when
  the recipient needs only those sources. Put relevant facts/decisions and
  superseded item ids in ``context_delta``; never put private reasoning there.
- Use ``kind="handoff"`` for assignments and ``question``/``answer`` for a
  linked peer exchange. Preserve ``thread_id`` and ``in_reply_to``; the runtime
  caps one chain at 12 hops.
- For ``requires_user_input``, you may provide a stable ``question_key``
  describing the missing information. Otherwise the runtime deduplicates from
  the normalized question text.
"""

_WORKER_DESCRIPTION = """Send an internal message to one team member.

## When to Use This Tool
- **IMPORTANT**: When you finish your assigned task, you MUST call this \
tool to report your results back to the reply owner named in your runtime \
instructions. The reply owner is waiting \
for your report — do not end your turn without sending it.
- Share intermediate findings with one specific collaborator.
- Use ``kind="question"`` when your own work needs the peer's answer; you will
  wait for it. A peer may ask you back for clarification, and the runtime will
  wake you to answer before you return to your existing wait.
- Use ``kind="handoff"`` for a separate remaining deliverable you do not own.
  The selected peer becomes active and is tracked independently.
- If genuinely customer-owned information is missing, call this exactly once
  with ``to=null`` and ``kind="requires_user_input"``. This makes you the
  temporary customer-facing owner for the clarification. Ask the same concise
  question naturally in your final reply. After the customer answers, finish
  your task and report the result to the Leader for synthesis.

## When NOT to Use This Tool
- You want to talk to yourself — use your own reasoning.
- The message is a transient internal thought with no value to others.
- Never omit ``to``. Worker broadcast is rejected by the runtime.
- Normal task results should remain ``context_mode="task"`` and
  ``result_scope="shared"``. Use ``isolated`` for a truly independent side
  question, and publish a caller-only result into shared state later only when
  it becomes relevant to the group. Never share private reasoning.
"""


class TeamSay(_TeamToolBase):
    """Send a message to a teammate (or broadcast to all teammates).

    Resolves the team membership at ``__call__`` time from storage,
    so a member added moments earlier in the same chat run is
    addressable immediately.

    The ``description`` shown to the agent differs by role: leaders
    are reminded not to poll members, workers are reminded to report
    results when done. The role is passed at construction time via
    the ``role`` parameter.
    """

    name: str = "TeamSay"
    description: str

    is_concurrency_safe: bool = True
    is_read_only: bool = True

    input_schema: dict = _TeamSayParams.model_json_schema()
    # Ticket lifecycle belongs to the workflow/customer API. Keep the field
    # on ContextDelta for other callers, but do not advertise it as a TeamSay
    # argument an LLM may control.
    input_schema.get("$defs", {}).get("ContextDelta", {}).get(
        "properties", {}
    ).pop("status", None)

    def __init__(
        self,
        *args: Any,
        role: str = "leader",
        **kwargs: Any,
    ) -> None:
        """Initialise with role-specific description.

        Args:
            role (`str`, defaults to ``"leader"``):
                Either ``"leader"`` or ``"worker"``. Determines which
                description the agent sees for this tool.
            *args:
                Forwarded to :class:`_TeamToolBase.__init__`.
            **kwargs:
                Forwarded to :class:`_TeamToolBase.__init__`.
        """
        super().__init__(*args, **kwargs)
        self._role = role
        self.description = (
            _LEADER_DESCRIPTION if role == "leader" else _WORKER_DESCRIPTION
        )

    async def __call__(
        self,
        content: str,
        to: str | None = None,
        kind: Literal[
            "handoff",
            "question",
            "answer",
            "result",
            "progress",
            "requires_user_input",
            "user_input_proposal",
            "conflict",
            "error",
        ] = "result",
        task_id: str | None = None,
        context_mode: ContextMode = "task",
        result_scope: ContextResultScope | None = None,
        reference_event_ids: tuple[str, ...] = (),
        context_delta: ContextDelta | None = None,
        idempotency_key: str | None = None,
        thread_id: str | None = None,
        in_reply_to: str | None = None,
        artifact_refs: tuple[str, ...] = (),
        hop_count: int = 1,
        question_key: str | None = None,
        resolution: Literal["complete", "stop", "verify"] | None = None,
    ) -> ToolChunk:
        """Deliver the message directly via storage + message bus.

        Reads the current session record from storage to resolve the
        team_id (the agent's team membership may have changed since
        agent assembly), builds the team's (agent_id, session_id)
        directory, and pushes a HintBlock + wakeup to each recipient.

        Args:
            content (`str`):
                Message body.
            to (`str | None`, defaults to ``None``):
                Display name of a specific team member to target, or
                ``None`` for broadcast.  Routing is by name (not
                agent id) so workers can address the leader by the
                name they see in ``<team-message from="...">``.
                Names are resolved against the current team directory.

        Returns:
            `ToolChunk`:
                A confirmation containing the recipient count, or an
                error chunk on failure.
        """
        intent = None
        try:
            if (
                kind == "requires_user_input"
                and isinstance(to, str)
                and to.strip().casefold() in {"null", "none"}
            ):
                # Some models serialize a nullable target as the string
                # "null". For a customer question its intent is unambiguous.
                to = None
            if context_delta is not None:
                context_delta = ContextDelta.model_validate(context_delta)
            team = await self._require_team()
            shared_context = self._shared_context or SharedContextService(
                self._storage,
                self._message_bus,
            )

            if context_mode == "references" and not reference_event_ids:
                return ToolChunk(
                    content=[
                        TextBlock(
                            text=(
                                "TeamSay: references mode requires at least "
                                "one reference_event_id."
                            ),
                        ),
                    ],
                    state=ToolResultState.ERROR,
                )
            if hop_count < 1 or hop_count > 12:
                return ToolChunk(
                    content=[
                        TextBlock(text="TeamSay: handoff hop limit (12) exceeded.")
                    ],
                    state=ToolResultState.ERROR,
                )
            effective_scope: ContextResultScope = result_scope or (
                "caller" if context_mode == "isolated" else "shared"
            )
            # Build a (name -> (session_id, agent_id)) directory. The
            # leader is always in the directory under its plain agent
            # name; workers come from the team's members roster via
            # ``ensure_team_members`` (which migrates legacy
            # ``member_ids``-only records on first read). Invited
            # members display as ``"<name>@<agent_id[:8]>"`` so a
            # borrowed agent whose name collides with an existing
            # member (or the leader) remains addressable.
            #
            # Uniqueness of the resulting display strings within a team
            # is preserved by AgentInvite's derived id handle and its
            # one-borrow-per-agent-per-team rule.
            leader = await _resolve_team_leader(
                self._storage,
                self._user_id,
                team,
            )
            if leader is None:
                return ToolChunk(
                    content=[
                        TextBlock(
                            text=(
                                f"TeamSay: leader records missing for team {team.id}."
                            ),
                        ),
                    ],
                    state=ToolResultState.ERROR,
                )
            if (
                self._role == "leader"
                and leader.agent.data.system_role == "leader"
                and kind == "requires_user_input"
            ):
                return ToolChunk(
                    content=[
                        TextBlock(
                            text=(
                                "TeamSay: the Workforce Leader does not ask "
                                "task-specific customer questions. Delegate "
                                "intake to the responsible specialist."
                            ),
                        ),
                    ],
                    state=ToolResultState.ERROR,
                )
            directory: dict[str, tuple[str, str]] = {
                leader.name: (leader.session_id, leader.agent.id),
            }
            members = await _ensure_team_members(
                self._storage,
                self._user_id,
                team,
            )
            for member in members:
                member_agent = await self._storage.get_agent(
                    member.owner_id,
                    member.agent_id,
                )
                if member_agent is None:
                    continue
                if member.role == "invited":
                    display = f"{member_agent.data.name}@{member.agent_id[:HANDLE_LEN]}"
                else:
                    display = member_agent.data.name
                directory[display] = (member.session_id, member.agent_id)

            own_session_ids = {sid for sid, _aid in directory.values()}
            if self._session_id not in own_session_ids:
                return ToolChunk(
                    content=[
                        TextBlock(
                            text=(
                                f"TeamSay: this session "
                                f"({self._session_id}) is not part of "
                                f"team {team.id}."
                            ),
                        ),
                    ],
                    state=ToolResultState.ERROR,
                )

            turn = await get_team_turn(
                self._message_bus,
                team.id,
                storage=shared_context.storage,
                user_id=self._user_id,
            )
            effective_task_id = task_id or (turn.task_id if turn else None)
            active_task = await shared_context.active_task_id(self._user_id, team.id)
            if effective_task_id is not None:
                task_snapshot = await shared_context.storage.get_team_shared_context(
                    self._user_id, team.id
                )
                if effective_task_id not in task_snapshot.state.tasks:
                    raise ValueError(
                        "task_id must be assigned by the runtime, not invented by an agent"
                    )
                if (
                    self._role == "worker"
                    and effective_task_id
                    not in {active_task, turn.task_id if turn else None}
                    and await shared_context.session_revision(
                        self._session_id, team_id=team.id, task_id=effective_task_id
                    )
                    is None
                ):
                    raise ValueError("task_id is not pinned for this worker")
            effective_task_id = await shared_context.active_task_id(
                self._user_id,
                team.id,
                requested_task_id=effective_task_id,
            )
            based_on_revision = await shared_context.session_revision(
                self._session_id,
                team_id=team.id,
                task_id=effective_task_id,
            )
            try:
                (
                    hop_count,
                    parent_thread_id,
                ) = await shared_context.validate_handoff_link(
                    self._user_id,
                    team.id,
                    effective_task_id,
                    in_reply_to,
                    thread_id,
                    recipient_session_id=self._session_id,
                )
            except ValueError as exc:
                return ToolChunk(
                    content=[TextBlock(text=f"TeamSay: {exc}.")],
                    state=ToolResultState.ERROR,
                )
            if thread_id is None:
                thread_id = parent_thread_id

            def _handoff_id() -> str:
                if idempotency_key:
                    return idempotency_key
                canonical = json.dumps(
                    {
                        "team_id": team.id,
                        "turn_id": turn.turn_id if turn else None,
                        "sender_session_id": self._session_id,
                        "to": to,
                        "kind": kind,
                        "content": content,
                        "task_id": effective_task_id,
                        "context_mode": context_mode,
                        "result_scope": effective_scope,
                        "reference_event_ids": reference_event_ids,
                        "thread_id": thread_id,
                        "in_reply_to": in_reply_to,
                        "artifact_refs": artifact_refs,
                        "hop_count": hop_count,
                        "question_key": question_key,
                        "resolution": resolution,
                        "context_delta": (
                            context_delta.model_dump(mode="json")
                            if context_delta
                            else None
                        ),
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

            is_reply_owner = (
                turn is not None and turn.reply_owner_session_id == self._session_id
            ) or (turn is None and leader.session_id == self._session_id)
            reply_owner_name = leader.name
            if turn is not None:
                reply_owner_name = next(
                    (
                        name
                        for name, (sid, _aid) in directory.items()
                        if sid == turn.reply_owner_session_id
                    ),
                    leader.name,
                )

            # A worker may take temporary reply ownership solely to obtain
            # customer-owned information. Addressing the current owner keeps
            # the legacy proposal/review path for non-Workforce callers.
            direct_specialist_question = (
                self._role == "worker"
                and kind in {"requires_user_input", "user_input_proposal"}
                and not is_reply_owner
                and to is None
            )
            if direct_specialist_question:
                kind = "requires_user_input"
            proposal = (
                kind in {"requires_user_input", "user_input_proposal"}
                and not is_reply_owner
                and not direct_specialist_question
            )
            if proposal:
                if to != reply_owner_name:
                    return ToolChunk(
                        content=[
                            TextBlock(
                                text="Send the proposed user question to the reply owner for review."
                            )
                        ],
                        state=ToolResultState.ERROR,
                    )
                kind = "user_input_proposal"
            if kind == "conflict" and not is_reply_owner and to != reply_owner_name:
                raise ValueError(
                    "Conflicting results must be sent to the reply owner for review"
                )
            if context_delta is not None and context_delta.status is not None:
                # A stale model/schema may still submit this server-owned
                # field. Ignore only the lifecycle mutation and preserve the
                # actual handoff instead of dropping the collaboration message.
                context_delta = context_delta.model_copy(update={"status": None})
            normalized_content = " ".join(content.casefold().split())
            if (
                self._role == "worker"
                and kind in {"result", "answer"}
                and any(
                    marker in normalized_content
                    for marker in _PROGRESS_ONLY_MARKERS
                )
            ):
                # A future-tense promise is not a completed result. Preserve
                # it as optional progress and force the worker middleware to
                # continue until it sends a concrete result/question/error.
                kind = "progress"

            if kind == "requires_user_input" and (
                is_reply_owner or direct_specialist_question
            ):
                question_id = _handoff_id()
                turn, duplicate, _first = await register_user_input_request(
                    self._message_bus,
                    team.id,
                    content,
                    default_reply_owner_session_id=self._session_id,
                    default_reply_owner_agent_id=self._agent_id,
                    customer_session_id=(
                        turn.customer_session_id
                        if turn is not None
                        else leader.session_id
                    ),
                    task_id=effective_task_id,
                    question_id=question_id,
                    question_key=question_key,
                    storage=shared_context.storage,
                    user_id=self._user_id,
                    specialist_owner_session_id=(
                        self._session_id if direct_specialist_question else None
                    ),
                    specialist_owner_agent_id=(
                        self._agent_id if direct_specialist_question else None
                    ),
                )
                if not duplicate and effective_scope == "shared":
                    try:
                        question_event = await shared_context.append_event(
                            user_id=self._user_id,
                            team_id=team.id,
                            kind="requires_user_input",
                            content=content,
                            event_id=question_id,
                            task_id=effective_task_id,
                            source_agent_id=self._agent_id,
                            source_session_id=self._session_id,
                            thread_id=thread_id,
                            in_reply_to=in_reply_to,
                            artifact_refs=artifact_refs,
                            hop_count=hop_count,
                            reply_owner_agent_id=self._agent_id,
                            based_on_revision=based_on_revision,
                            reference_event_ids=reference_event_ids,
                            delta=context_delta,
                        )
                    except Exception:
                        await reject_user_input_request(
                            self._message_bus,
                            team.id,
                            question_id,
                            storage=shared_context.storage,
                            user_id=self._user_id,
                        )
                        if direct_specialist_question:
                            await return_team_reply_to_leader(
                                self._message_bus,
                                team.id,
                                specialist_session_id=self._session_id,
                                leader_session_id=leader.session_id,
                                leader_agent_id=leader.agent.id,
                                storage=shared_context.storage,
                                user_id=self._user_id,
                            )
                        raise
                    if question_event.stale:
                        await reject_user_input_request(
                            self._message_bus,
                            team.id,
                            question_event.id,
                            storage=shared_context.storage,
                            user_id=self._user_id,
                        )
                        return ToolChunk(
                            content=[
                                TextBlock(
                                    text=(
                                        "TeamSay: stale customer question "
                                        "rejected because the task changed. "
                                        "Reload context and recompute."
                                    ),
                                ),
                            ],
                            state=ToolResultState.ERROR,
                        )
                return ToolChunk(
                    content=[
                        TextBlock(
                            text=(
                                "Customer question already registered; ask it "
                                "once in your final reply."
                                if duplicate
                                else "Customer question registered; ask it once "
                                "in your final reply, then wait."
                            ),
                        ),
                    ],
                    metadata={"kind": "requires_user_input"},
                )

            if self._role == "worker" and to is None:
                return ToolChunk(
                    content=[
                        TextBlock(
                            text=(
                                "TeamSay: workers cannot broadcast. Send the "
                                "result to the reply owner or one collaborator."
                            ),
                        ),
                    ],
                    state=ToolResultState.ERROR,
                )

            if to is None:
                recipients: list[tuple[str, str]] = [
                    (sid, aid)
                    for sid, aid in directory.values()
                    if sid != self._session_id
                ]
            else:
                resolved = directory.get(to)
                if resolved is None:
                    known = sorted(directory.keys())
                    return ToolChunk(
                        content=[
                            TextBlock(
                                text=(
                                    f"TeamSay: no team member is named "
                                    f"{to!r}. Known members: {known}."
                                ),
                            ),
                        ],
                        state=ToolResultState.ERROR,
                    )
                target_session_id, target_agent_id = resolved
                if target_session_id == self._session_id:
                    return ToolChunk(
                        content=[
                            TextBlock(
                                text=(
                                    "TeamSay: cannot send a message to "
                                    "yourself; talk to yourself in your "
                                    "own reasoning instead."
                                ),
                            ),
                        ],
                        state=ToolResultState.ERROR,
                    )
                recipients = [(target_session_id, target_agent_id)]

            if (
                self._role == "worker"
                and kind == "requires_user_input"
                and to != reply_owner_name
            ):
                return ToolChunk(
                    content=[
                        TextBlock(
                            text=(
                                "TeamSay: requires_user_input must be sent "
                                f"to the reply owner {reply_owner_name!r}."
                            ),
                        ),
                    ],
                    state=ToolResultState.ERROR,
                )
            if turn is not None and turn.status != "running":
                reporting_to_owner = self._role == "worker" and to == reply_owner_name
                if not reporting_to_owner:
                    return ToolChunk(
                        content=[
                            TextBlock(
                                text=(
                                    "TeamSay: this team turn is paused. Do not "
                                    "start more collaboration until the next "
                                    "customer turn."
                                ),
                            ),
                        ],
                        state=ToolResultState.ERROR,
                    )

            # Use the team directory so cross-owner invited agents retain
            # their unambiguous scoped handle.
            sender_name = next(
                (
                    name
                    for name, (sid, _aid) in directory.items()
                    if sid == self._session_id
                ),
                self._agent_id,
            )

            wake = not (
                kind == "progress"
                or (turn is not None and turn.status != "running")
            )
            if kind == "requires_user_input":
                turn, duplicate, first_question = await register_user_input_request(
                    self._message_bus,
                    team.id,
                    content,
                    default_reply_owner_session_id=leader.session_id,
                    default_reply_owner_agent_id=leader.agent.id,
                    customer_session_id=leader.session_id,
                    task_id=effective_task_id,
                    question_id=_handoff_id(),
                    question_key=question_key,
                    storage=shared_context.storage,
                    user_id=self._user_id,
                )
                if duplicate:
                    return ToolChunk(
                        content=[
                            TextBlock(
                                text=(
                                    "Duplicate customer question suppressed; "
                                    "the reply owner already has it."
                                ),
                            ),
                        ],
                    )
                wake = first_question and turn.status == "running"

            handoff_id = _handoff_id()
            # Journal before changing dependencies. The existing dispatcher
            # replays this intent after a crash between reservation and delivery.
            intent_id = hashlib.sha256(f"{handoff_id}\0intent".encode()).hexdigest()
            intent = await shared_context.storage.get_team_handoff(
                self._user_id, intent_id
            )
            if intent is None:
                snapshot = await shared_context.storage.get_team_shared_context(
                    self._user_id, team.id
                )
                intent = TeamHandoffRecord(
                    id=intent_id,
                    user_id=self._user_id,
                    team_id=team.id,
                    handoff_id=f"intent:{handoff_id}",
                    task_id=effective_task_id,
                    kind=kind,
                    source_agent_id=self._agent_id,
                    source_session_id=self._session_id,
                    recipient_agent_id=self._agent_id,
                    recipient_session_id=self._session_id,
                    idempotency_key=handoff_id,
                    payload={
                        "collaboration_intent": {
                            "role": self._role,
                            "customer_revision": snapshot.state.tasks[
                                effective_task_id
                            ].latest_customer_revision,
                            "arguments": {
                                "content": content,
                                "to": to,
                                "kind": kind,
                                "task_id": effective_task_id,
                                "context_mode": context_mode,
                                "result_scope": effective_scope,
                                "reference_event_ids": reference_event_ids,
                                "context_delta": context_delta.model_dump(mode="json")
                                if context_delta
                                else None,
                                "idempotency_key": handoff_id,
                                "thread_id": thread_id,
                                "in_reply_to": in_reply_to,
                                "artifact_refs": artifact_refs,
                                "question_key": question_key,
                                "resolution": resolution,
                            },
                        }
                    },
                )
                await shared_context.persist_handoff(intent)
            # A specialist owns only the temporary customer clarification.
            # Its terminal reply must still settle the peer that requested it.
            coordination_owner_session_id = (
                leader.session_id
                if (
                    turn is not None
                    and turn.mode == "specialist_question"
                    and turn.reply_owner_session_id == self._session_id
                    and kind in {"result", "answer", "error"}
                )
                else turn.reply_owner_session_id
                if turn is not None
                else leader.session_id
            )
            coordination = await shared_context.coordinate_handoff(
                user_id=self._user_id,
                team_id=team.id,
                task_id=effective_task_id,
                sender=self._session_id,
                recipients=tuple(sid for sid, _ in recipients),
                owner=coordination_owner_session_id,
                handoff_id=handoff_id,
                kind=kind,
                content=content,
                in_reply_to=in_reply_to,
                references=reference_event_ids,
                resolution=resolution,
                based_on_revision=based_on_revision,
                share_report=effective_scope == "shared",
                # A direct peer answer already wakes its requester and remains
                # durable in Shared Context. Sending the same answer to the
                # Leader inbox duplicates model work before the coordinator's
                # final result arrives.
                notify_owner=not (
                    kind == "answer"
                    and in_reply_to is not None
                    and self._session_id != leader.session_id
                ),
            )
            kind, content = coordination["kind"], coordination["content"]
            # Carry server-owned dependency lineage into synthesized results
            # without requiring the model to reproduce opaque event IDs.
            reference_event_ids = tuple(
                coordination.get("reference_event_ids", reference_event_ids),
            )
            members_by_session = {sid: aid for sid, aid in directory.values()}
            recipients = [
                (sid, members_by_session[sid]) for sid in coordination["recipients"]
            ]
            shared_event = None
            if effective_scope == "shared":
                shared_event = await shared_context.append_event(
                    user_id=self._user_id,
                    team_id=team.id,
                    kind=kind,
                    content=content,
                    event_id=handoff_id,
                    task_id=effective_task_id,
                    source_agent_id=self._agent_id,
                    source_session_id=self._session_id,
                    thread_id=thread_id,
                    in_reply_to=in_reply_to,
                    artifact_refs=artifact_refs,
                    hop_count=hop_count,
                    task_owner_agent_id=(
                        recipients[0][1]
                        if kind == "handoff" and len(recipients) == 1
                        else None
                    ),
                    reply_owner_agent_id=(
                        turn.reply_owner_agent_id if turn is not None else None
                    ),
                    based_on_revision=based_on_revision,
                    reference_event_ids=reference_event_ids,
                    delta=context_delta,
                )
                if shared_event.stale:
                    if kind == "requires_user_input":
                        await reject_user_input_request(
                            self._message_bus,
                            team.id,
                            shared_event.id,
                            storage=shared_context.storage,
                            user_id=self._user_id,
                        )
                    if (
                        turn is not None
                        and turn.mode == "specialist_question"
                        and turn.reply_owner_session_id == self._session_id
                    ):
                        await return_team_reply_to_leader(
                            self._message_bus,
                            team.id,
                            specialist_session_id=self._session_id,
                            leader_session_id=leader.session_id,
                            leader_agent_id=leader.agent.id,
                            storage=shared_context.storage,
                            user_id=self._user_id,
                        )
                    return ToolChunk(
                        content=[
                            TextBlock(
                                text=(
                                    STALE_CONTEXT_RESULT
                                    + " Stop this stale turn; the Leader will "
                                    "start a fresh turn with the latest shared "
                                    "context."
                                ),
                            ),
                        ],
                        state=ToolResultState.ERROR,
                    )

            if (
                turn is not None
                and turn.mode == "specialist_question"
                and turn.reply_owner_session_id == self._session_id
                and kind in {"result", "answer", "error"}
            ):
                await return_team_reply_to_leader(
                    self._message_bus,
                    team.id,
                    specialist_session_id=self._session_id,
                    leader_session_id=leader.session_id,
                    leader_agent_id=leader.agent.id,
                    storage=shared_context.storage,
                    user_id=self._user_id,
                )

            directive_refs = reference_event_ids
            if context_mode == "references" and shared_event is not None:
                directive_refs = tuple(
                    dict.fromkeys((*directive_refs, shared_event.id)),
                )
            context_revision = (
                shared_event.revision
                if shared_event is not None
                else await shared_context.current_revision(self._user_id, team.id)
            )
            context_ref = hashlib.sha256(
                f"{team.id}\0{context_revision}".encode(),
            ).hexdigest()

            hint = HintBlock(
                hint=(
                    f'<team-message from="{sender_name}" kind="{kind}">\n'
                    f"handoff_id={handoff_id}; task_id={effective_task_id}; reply using in_reply_to={handoff_id}\n"
                    f"reference_event_ids={json.dumps(directive_refs)}\n"
                    f"{content}\n"
                    f"</team-message>"
                ),
                source=json.dumps(
                    {
                        "label": "team",
                        "sublabel": sender_name,
                        "audience": "internal",
                        "kind": kind,
                        "turn_id": turn.turn_id if turn else None,
                        "handoff_id": handoff_id,
                        "task_id": (
                            shared_event.task_id if shared_event else effective_task_id
                        ),
                        "context_mode": context_mode,
                        "result_scope": effective_scope,
                        "reference_event_ids": directive_refs,
                        "context_ref": context_ref,
                        "context_revision": context_revision,
                        "thread_id": thread_id,
                        "in_reply_to": in_reply_to,
                        "artifact_refs": artifact_refs,
                        "hop_count": hop_count,
                    },
                    ensure_ascii=False,
                ),
            )
            payload = hint.model_dump(mode="json")

            durable: list[TeamHandoffRecord] = []
            for sid, aid in recipients:
                record_id = hashlib.sha256(
                    f"{handoff_id}\0{sid}".encode(),
                ).hexdigest()
                existing = await shared_context.storage.get_team_handoff(
                    self._user_id,
                    record_id,
                )
                record = existing or TeamHandoffRecord(
                    id=record_id,
                    user_id=self._user_id,
                    team_id=team.id,
                    handoff_id=handoff_id,
                    task_id=(
                        shared_event.task_id if shared_event else effective_task_id
                    ),
                    thread_id=thread_id,
                    in_reply_to=in_reply_to,
                    kind=kind,
                    source_agent_id=self._agent_id,
                    source_session_id=self._session_id,
                    recipient_agent_id=aid,
                    recipient_session_id=sid,
                    context_mode=context_mode,
                    result_scope=effective_scope,
                    context_ref=context_ref,
                    context_revision=context_revision,
                    reference_event_ids=directive_refs,
                    artifact_refs=artifact_refs,
                    hop_count=hop_count,
                    idempotency_key=handoff_id,
                    payload=payload,
                )
                if existing is None:
                    await shared_context.persist_handoff(record)
                durable.append(record)

            count = 0
            for record in durable:
                sid = record.recipient_session_id
                aid = record.recipient_agent_id
                async with self._message_bus.acquire_lock(
                    MessageBusKeys.team_handoff_delivery_lock(
                        handoff_id,
                        sid,
                    ),
                    ttl_secs=(MessageBusKeys.TEAM_HANDOFF_DELIVERY_LOCK_TTL_SECS),
                ):
                    delivered = await self._message_bus.registry_get(
                        MessageBusKeys.team_handoff_delivery(handoff_id),
                        sid,
                    )
                    if delivered is not None or record.delivery_status in {
                        "delivered",
                        "consumed",
                        "cancelled",
                    }:
                        continue
                    await shared_context.register_directive(
                        sid,
                        ContextDirective(
                            handoff_id=handoff_id,
                            mode=context_mode,
                            task_id=(
                                shared_event.task_id
                                if shared_event
                                else effective_task_id
                            ),
                            reference_event_ids=directive_refs,
                            context_ref=context_ref,
                            context_revision=context_revision,
                            thread_id=thread_id,
                            in_reply_to=in_reply_to,
                            hop_count=hop_count,
                        ),
                    )
                    try:
                        await deliver_to_inbox(
                            self._message_bus,
                            user_id=self._user_id,
                            session_id=sid,
                            agent_id=aid,
                            payload=payload,
                            wake=wake,
                        )
                    except Exception as exc:
                        await shared_context.mark_handoff(
                            record,
                            "failed",
                            error=str(exc),
                        )
                        raise
                    await shared_context.mark_handoff(record, "delivered")
                    await self._message_bus.registry_set(
                        MessageBusKeys.team_handoff_delivery(handoff_id),
                        sid,
                        "1",
                        ttl_secs=(MessageBusKeys.TEAM_HANDOFF_DELIVERY_TTL_SECS),
                    )
                    count += 1
            await shared_context.mark_handoff(intent, "consumed")
            target = "broadcast" if to is None else f"member {to!r}"
            return ToolChunk(
                content=[
                    TextBlock(
                        text=(f"Delivered to {count} recipient(s) ({target})."),
                    ),
                ],
                metadata={
                    "handoff_id": handoff_id,
                    "kind": kind,
                    "collaboration_status": coordination["status"],
                },
            )
        except Exception as e:  # noqa: BLE001 - tool returns structured error
            return ToolChunk(
                content=[TextBlock(text=f"TeamSay failed: {e}")],
                state=ToolResultState.ERROR,
                metadata={
                    "retryable": not isinstance(
                        e,
                        (
                            ValueError,
                            CollaborationStoppedError,
                            SharedContextConcurrencyError,
                        ),
                    )
                }
                if intent is not None
                else {},
            )
