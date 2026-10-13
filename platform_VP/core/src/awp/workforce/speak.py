"""The one way a leader's words reach the resident (CaseSay and the answer of CaseFinalize).

The message row, its `assistant.message` event and what the leader meant by it (`expects`, `outcome`)
are written in one transaction, tagged with the request the leader is working for. Nothing the model
writes outside these tools is ever shown.
"""
from __future__ import annotations

from sqlalchemy import func, select

from ..guard import check_text, written_amounts
from . import tables as t
from .events import lock_conversation
from .jobs import cycle_job
from .lookup import inflight_request
from .messages import add_assistant_message
from .workflows import BLOCKED, IllegalTransition

EXPECTS = ("none", "reply", "confirmation")
MAX_SAYS = 5  # CaseSay messages in one chain of turns: a looping leader must not flood the resident


class BadText(ValueError):
    """The text may not be shown to the resident; the message says why, for the model to correct."""


def checked(text: str | None, limit: int) -> str:
    """The text as the resident will read it: stripped, not empty, within the contract's length."""
    text = (text or "").strip()
    if not text:
        raise BadText("Say something: the text is empty.")
    if len(text) > limit:
        raise BadText(f"Too long: at most {limit} characters.")
    return text


def problems(text: str, sources: list[str], rules, trusted: list[str]) -> list[str]:
    """Why `text` may not reach the resident: the guard's checks, and no amount written out in words
    (a figure the guard cannot compare with any source)."""
    out = check_text(text, sources, rules, trusted)
    words = written_amounts(text)
    if words:
        out.append("amounts written in words (" + ", ".join(words) + "): write them as digits, exactly as the "
                   "cited item states them")
    return out


async def chain_says(db, workflow_id: str) -> list[str]:
    """What the leader said to the resident since the current chain began (the texts, oldest first)."""
    async with db.engine.connect() as conn:
        cycle = await cycle_job(conn, workflow_id)
        start = cycle["payload"].get("start_seq", 0) if cycle else 0
        return list((await conn.execute(select(t.messages.c.text).where(
            t.messages.c.workflow_id == workflow_id, t.messages.c.sender == "assistant",
            t.messages.c.expects.is_not(None), t.messages.c.sequence > start)
            .order_by(t.messages.c.sequence))).scalars())


async def last_say_at(db, workflow_id: str) -> float | None:
    """When the leader last spoke to the resident in the current chain (None: not yet)."""
    async with db.engine.connect() as conn:
        cycle = await cycle_job(conn, workflow_id)
        start = cycle["payload"].get("start_seq", 0) if cycle else 0
        return (await conn.execute(select(func.max(t.messages.c.created_at)).where(
            t.messages.c.workflow_id == workflow_id, t.messages.c.sender == "assistant",
            t.messages.c.expects.is_not(None), t.messages.c.sequence > start))).scalar()


async def publish(db, workflow_id: str, text: str, *, expects: str, outcome: str | None = None,
                  limit: int = 20000) -> dict:
    """Write what the assistant says. Raises BadText for an empty or too long text and IllegalTransition
    when the workflow is closed or blocked (authorization withdrawn): a close that committed first wins,
    because the lock is taken and only then the state read."""
    text = checked(text, limit)
    async with db.engine.begin() as conn:
        conv = (await conn.execute(select(t.workflows.c.conversation_id).where(
            t.workflows.c.id == workflow_id))).scalar_one()
        await lock_conversation(conn, conv)
        wf = (await conn.execute(select(t.workflows).where(t.workflows.c.id == workflow_id))).mappings().one()
        if wf["state"] == "closed":
            raise IllegalTransition("a closed workflow takes no new messages")
        if wf["state"] in BLOCKED:
            raise IllegalTransition("a blocked workflow takes no new messages")
        return await add_assistant_message(conn, wf, text, await inflight_request(conn, workflow_id),
                                           expects=expects, outcome=outcome)
