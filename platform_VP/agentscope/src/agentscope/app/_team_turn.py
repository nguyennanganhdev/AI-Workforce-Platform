"""Small runtime state machine for one team's customer-facing turn."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel, Field

from .._utils._common import _generate_id
from ..message import Msg
from .message_bus import MessageBus, MessageBusKeys
from .storage import StorageBase, TeamTurnRecord

TEAM_CUSTOMER_CONTEXT_MAX_CHARS = 12_000


class TeamTurnState(BaseModel):
    """Who owns the customer reply and whether the team is paused."""

    turn_id: str = Field(default_factory=_generate_id)
    mode: Literal["leader", "direct_mention", "specialist_question"] = "leader"
    reply_owner_session_id: str
    reply_owner_agent_id: str
    customer_session_id: str
    task_id: str | None = None
    status: Literal["running", "awaiting_user_input", "completed"] = "running"
    pending_questions: list[str] = Field(default_factory=list)
    pending_question_ids: list[str] = Field(default_factory=list)


def build_customer_ticket_context(
    messages: list[Msg],
    *,
    exclude_message_id: str | None = None,
    max_chars: int = TEAM_CUSTOMER_CONTEXT_MAX_CHARS,
) -> str:
    """Build a bounded customer-visible transcript for a directly mentioned agent."""
    entries: list[str] = []
    for message in messages:
        if message.id == exclude_message_id or message.role not in {
            "user",
            "assistant",
        }:
            continue
        text = (message.get_text_content() or "").strip()
        if not text:
            continue
        speaker = "Customer" if message.role == "user" else message.name
        entries.append(f"{speaker}: {text}")

    selected: list[str] = []
    remaining = max_chars
    for entry in reversed(entries):
        if remaining <= 0:
            break
        selected.append(entry[:remaining])
        remaining -= len(selected[-1]) + 1
    return "\n\n".join(reversed(selected))


def _normalise_question(value: str) -> str:
    """Normalise a proposed question for cheap deterministic dedupe."""
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return " ".join(value.split())[:500]


def _is_similar_question(left: str, right: str) -> bool:
    """Treat near-identical question wording as the same requirement."""
    if left == right:
        return True
    if not left or not right:
        return False
    shorter, longer = sorted((left, right), key=len)
    if len(shorter) >= 20 and shorter in longer:
        return True
    return SequenceMatcher(None, left, right).ratio() >= 0.82


async def get_team_turn(
    bus: MessageBus,
    team_id: str,
    *,
    storage: StorageBase | None = None,
    user_id: str | None = None,
) -> TeamTurnState | None:
    """Read the team's current turn, if one has been started."""
    raw = await bus.registry_get(
        MessageBusKeys.team_turn(team_id),
        MessageBusKeys.TEAM_TURN_FIELD,
    )
    if raw:
        return TeamTurnState.model_validate_json(raw)
    if storage is None or user_id is None:
        return None
    durable = await storage.get_team_turn(user_id, team_id)
    if durable is None:
        return None
    state = TeamTurnState(
        turn_id=durable.turn_id,
        mode=durable.mode,
        reply_owner_session_id=durable.reply_owner_session_id,
        reply_owner_agent_id=durable.reply_owner_agent_id,
        customer_session_id=durable.customer_session_id,
        task_id=durable.task_id,
        status=durable.status,
        pending_questions=list(durable.pending_question_keys),
        pending_question_ids=list(durable.pending_question_ids),
    )
    await _put_team_turn(bus, team_id, state, storage=storage, user_id=user_id)
    return state


async def _put_team_turn(
    bus: MessageBus,
    team_id: str,
    state: TeamTurnState,
    *,
    storage: StorageBase | None = None,
    user_id: str | None = None,
) -> None:
    # PostgreSQL is authoritative.  Redis is only the hot cache, so a
    # process/Redis crash can never acknowledge a turn that was not made
    # durable first.
    if storage is not None and user_id is not None:
        await storage.upsert_team_turn(
            user_id,
            TeamTurnRecord(
                id=team_id,
                user_id=user_id,
                team_id=team_id,
                turn_id=state.turn_id,
                mode=state.mode,
                reply_owner_session_id=state.reply_owner_session_id,
                reply_owner_agent_id=state.reply_owner_agent_id,
                customer_session_id=state.customer_session_id,
                task_id=state.task_id,
                status=state.status,
                pending_question_ids=tuple(state.pending_question_ids),
                pending_question_keys=tuple(state.pending_questions),
            ),
        )
    await bus.registry_set(
        MessageBusKeys.team_turn(team_id),
        MessageBusKeys.TEAM_TURN_FIELD,
        state.model_dump_json(),
        ttl_secs=MessageBusKeys.TEAM_TURN_TTL_SECS,
    )


async def start_team_turn(
    bus: MessageBus,
    team_id: str,
    *,
    reply_owner_session_id: str,
    reply_owner_agent_id: str,
    customer_session_id: str,
    mode: Literal["leader", "direct_mention", "specialist_question"],
    task_id: str | None = None,
    storage: StorageBase | None = None,
    user_id: str | None = None,
) -> TeamTurnState:
    """Start a user turn and clear every pending question from the prior one."""
    state = TeamTurnState(
        mode=mode,
        reply_owner_session_id=reply_owner_session_id,
        reply_owner_agent_id=reply_owner_agent_id,
        customer_session_id=customer_session_id,
        task_id=task_id,
    )
    await _put_team_turn(
        bus,
        team_id,
        state,
        storage=storage,
        user_id=user_id,
    )
    return state


async def register_user_input_request(
    bus: MessageBus,
    team_id: str,
    content: str,
    *,
    default_reply_owner_session_id: str,
    default_reply_owner_agent_id: str,
    customer_session_id: str,
    task_id: str | None = None,
    question_id: str | None = None,
    question_key: str | None = None,
    storage: StorageBase | None = None,
    user_id: str | None = None,
    specialist_owner_session_id: str | None = None,
    specialist_owner_agent_id: str | None = None,
) -> tuple[TeamTurnState, bool, bool]:
    """Record one customer question and optionally transfer reply ownership.

    Returns ``(state, duplicate, first_question)``. Only one distinct question
    may be pending. A specialist owner asks it directly; legacy callers may
    keep the existing owner for proposal/review behavior.
    """
    normalised = _normalise_question(question_key or content)
    async with bus.acquire_lock(
        MessageBusKeys.team_turn_lock(team_id),
        ttl_secs=MessageBusKeys.TEAM_TURN_LOCK_TTL_SECS,
    ):
        state = await get_team_turn(
            bus,
            team_id,
            storage=storage,
            user_id=user_id,
        )
        if state is None:
            state = TeamTurnState(
                reply_owner_session_id=default_reply_owner_session_id,
                reply_owner_agent_id=default_reply_owner_agent_id,
                customer_session_id=customer_session_id,
                task_id=task_id,
            )
        elif task_id is not None:
            state.task_id = task_id
        if specialist_owner_session_id is not None:
            if specialist_owner_agent_id is None:
                raise ValueError("specialist owner agent id is required")
            state.reply_owner_session_id = specialist_owner_session_id
            state.reply_owner_agent_id = specialist_owner_agent_id
            state.mode = "specialist_question"
        duplicate = any(
            _is_similar_question(normalised, existing)
            for existing in state.pending_questions
        )
        if duplicate:
            return state, True, False
        if state.pending_questions:
            raise ValueError(
                "One approved customer question is already pending; "
                "wait for its answer before asking another",
            )
        first_question = not state.pending_questions
        state.pending_questions.append(normalised)
        state.pending_question_ids.append(
            question_id
            or hashlib.sha256(
                f"{state.task_id or ''}\0{normalised}".encode(),
            ).hexdigest(),
        )
        await _put_team_turn(
            bus,
            team_id,
            state,
            storage=storage,
            user_id=user_id,
        )
        return state, False, first_question


async def return_team_reply_to_leader(
    bus: MessageBus,
    team_id: str,
    *,
    specialist_session_id: str,
    leader_session_id: str,
    leader_agent_id: str,
    storage: StorageBase | None = None,
    user_id: str | None = None,
) -> bool:
    """Return a specialist-owned clarification turn to the team leader."""

    async with bus.acquire_lock(
        MessageBusKeys.team_turn_lock(team_id),
        ttl_secs=MessageBusKeys.TEAM_TURN_LOCK_TTL_SECS,
    ):
        state = await get_team_turn(
            bus,
            team_id,
            storage=storage,
            user_id=user_id,
        )
        if (
            state is None
            or state.mode != "specialist_question"
            or state.reply_owner_session_id != specialist_session_id
        ):
            return False
        state.reply_owner_session_id = leader_session_id
        state.reply_owner_agent_id = leader_agent_id
        state.mode = "leader"
        state.status = "running"
        await _put_team_turn(
            bus,
            team_id,
            state,
            storage=storage,
            user_id=user_id,
        )
        return True


async def reject_user_input_request(
    bus: MessageBus,
    team_id: str,
    question_id: str,
    *,
    storage: StorageBase | None = None,
    user_id: str | None = None,
) -> None:
    """Remove a stale question that lost its shared-context revision race."""

    async with bus.acquire_lock(
        MessageBusKeys.team_turn_lock(team_id),
        ttl_secs=MessageBusKeys.TEAM_TURN_LOCK_TTL_SECS,
    ):
        state = await get_team_turn(
            bus,
            team_id,
            storage=storage,
            user_id=user_id,
        )
        if state is None or question_id not in state.pending_question_ids:
            return
        retained = [
            (key, pending_id)
            for key, pending_id in zip(
                state.pending_questions,
                state.pending_question_ids,
                strict=True,
            )
            if pending_id != question_id
        ]
        state.pending_questions = [key for key, _pending_id in retained]
        state.pending_question_ids = [
            pending_id for _key, pending_id in retained
        ]
        if not retained:
            state.status = "running"
        await _put_team_turn(
            bus,
            team_id,
            state,
            storage=storage,
            user_id=user_id,
        )


async def set_team_turn_task(
    bus: MessageBus,
    team_id: str,
    task_id: str,
    *,
    storage: StorageBase | None = None,
    user_id: str | None = None,
) -> TeamTurnState | None:
    """Attach the current customer-facing turn to its durable task."""

    async with bus.acquire_lock(
        MessageBusKeys.team_turn_lock(team_id),
        ttl_secs=MessageBusKeys.TEAM_TURN_LOCK_TTL_SECS,
    ):
        state = await get_team_turn(
            bus,
            team_id,
            storage=storage,
            user_id=user_id,
        )
        if state is None:
            return None
        state.task_id = task_id
        await _put_team_turn(
            bus,
            team_id,
            state,
            storage=storage,
            user_id=user_id,
        )
        return state


async def finish_team_turn(
    bus: MessageBus,
    team_id: str,
    *,
    session_id: str,
    storage: StorageBase | None = None,
    user_id: str | None = None,
) -> bool:
    """Close the owner's reply, waiting only for a registered question."""

    async with bus.acquire_lock(
        MessageBusKeys.team_turn_lock(team_id),
        ttl_secs=MessageBusKeys.TEAM_TURN_LOCK_TTL_SECS,
    ):
        state = await get_team_turn(
            bus,
            team_id,
            storage=storage,
            user_id=user_id,
        )
        if state is None or state.reply_owner_session_id != session_id:
            return False
        state.status = (
            "awaiting_user_input"
            if state.pending_question_ids
            else "completed"
        )
        await _put_team_turn(
            bus,
            team_id,
            state,
            storage=storage,
            user_id=user_id,
        )
        return True


async def team_is_awaiting_user(
    bus: MessageBus,
    team_id: str,
    *,
    storage: StorageBase | None = None,
    user_id: str | None = None,
) -> bool:
    """Return whether automatic runs for this team must stay asleep."""
    state = await get_team_turn(
        bus,
        team_id,
        storage=storage,
        user_id=user_id,
    )
    return state is not None and state.status == "awaiting_user_input"


async def team_is_paused(
    bus: MessageBus,
    team_id: str,
    *,
    storage: StorageBase | None = None,
    user_id: str | None = None,
) -> bool:
    """Return whether automatic collaboration must wait for a new user turn."""

    state = await get_team_turn(
        bus,
        team_id,
        storage=storage,
        user_id=user_id,
    )
    return state is not None and state.status != "running"


# Kept for callers written before the specialist-owned clarification turn.
mark_team_awaiting_user = finish_team_turn
