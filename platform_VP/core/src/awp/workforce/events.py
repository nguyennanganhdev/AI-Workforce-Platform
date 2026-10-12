"""The public event log of a conversation (contract 9.5-9.7).

`emit` runs inside the caller's transaction, so an event commits together with the change
it reports. The sequence comes from one UPDATE ... RETURNING on the conversation row: the row
lock makes writers of one conversation take turns, so commit order is sequence order and a
reader never sees sequence N+1 before N.
"""
from __future__ import annotations

from typing import Any, NamedTuple

from sqlalchemy import insert, select, update

from . import tables as t
from .common import iso, now
from .errors import WorkforceError, failed
from .tables import new_id
from .waker import poke_on_commit

PUBLIC = frozenset({
    "request.accepted", "workflow.status_changed", "ticket.created", "ticket.status_changed",
    "assistant.message", "approval.required", "approval.resolved", "operation.status_changed",
    "workflow.awaiting_user", "workflow.needs_attention", "workflow.closed"})

DEFAULT_LIMIT, MAX_LIMIT = 100, 500
BASE = "/workforce/v1/partner"


class Emitted(NamedTuple):
    event_id: str
    sequence: int


def snapshot_url(conversation_id: str) -> str:
    return f"{BASE}/conversations/{conversation_id}"


async def lock_conversation(conn, conversation_id: str, *, wait: bool = True) -> bool:
    """Take the conversation's write lock now. Every writer of a workflow calls this FIRST, before
    it touches any other row of that conversation (workflow, job, request): one lock order for all
    of them, so no two transactions wait on each other (a deadlock on Postgres, hidden on SQLite),
    and the workflow row read after it cannot change before the transaction ends.

    `wait=False` is for work that can come back later (the sweeps, the engine's claim): on PostgreSQL it uses
    `FOR UPDATE SKIP LOCKED` and returns False at once when another transaction holds the lock, instead of
    keeping a pooled connection idle behind it. SQLite has one writer for the whole file, so it always waits."""
    if conn.dialect.name == "postgresql":
        locked = (await conn.execute(select(t.conversations.c.id).where(t.conversations.c.id == conversation_id)
                                     .with_for_update(skip_locked=not wait))).first()
        if locked is not None:
            return True
        if (await conn.execute(select(t.conversations.c.id).where(t.conversations.c.id == conversation_id))).first() is None:
            raise LookupError(f"no conversation {conversation_id}")
        return False  # the row exists and somebody else has it
    done = await conn.execute(update(t.conversations).where(t.conversations.c.id == conversation_id)
                              .values(last_sequence=t.conversations.c.last_sequence))
    if done.rowcount != 1:
        raise LookupError(f"no conversation {conversation_id}")
    return True


async def emit(conn, conversation_id: str, event_type: str, payload: dict[str, Any], *,
               workflow: Any = None, occurred_at: float | None = None) -> Emitted:
    """Append a public event. `workflow` (a row or dict) supplies the workflow and ticket ids."""
    if event_type not in PUBLIC:
        raise ValueError(f"{event_type} is not a public event type")
    row = (await conn.execute(
        update(t.conversations).where(t.conversations.c.id == conversation_id)
        .values(last_sequence=t.conversations.c.last_sequence + 1)
        .returning(t.conversations.c.last_sequence))).first()
    if row is None:
        raise LookupError(f"no conversation {conversation_id}")
    seq, event_id, stamp = row[0], new_id("evt"), now()
    w = workflow or {}
    await conn.execute(insert(t.events).values(
        event_id=event_id, conversation_id=conversation_id, sequence=seq, event_type=event_type,
        workflow_id=w.get("id"), ticket_id=w.get("ticket_id"), external_ticket_id=w.get("external_ticket_id"),
        payload=payload, occurred_at=occurred_at or stamp, recorded_at=stamp))
    poke_on_commit(conn, conversation_id)
    return Emitted(event_id, seq)


def public_event(row: Any, conv: Any) -> dict:
    """The envelope of contract 9.7: the same JSON in history and in an SSE `data:` line."""
    return {
        "schema_version": "1", "event_id": row["event_id"], "sequence": row["sequence"],
        "event_type": row["event_type"], "occurred_at": iso(row["occurred_at"]),
        "recorded_at": iso(row["recorded_at"]), "conversation_id": row["conversation_id"],
        "external_ticket_id": row["external_ticket_id"] or conv["external_ticket_id"],
        "external_conversation_id": conv["external_conversation_id"],
        "external_user_id": conv["external_user_id"], "workflow_id": row["workflow_id"],
        "ticket_id": row["ticket_id"], "payload": row["payload"]}


def expired(conversation_id: str) -> WorkforceError:
    return WorkforceError("EVENT_CURSOR_EXPIRED", 410, "Load a new conversation snapshot before reconnecting.",
                          {"snapshot_url": snapshot_url(conversation_id)})


async def resolve_cursor(conn, conv: Any, cursor: str | None) -> int:
    """The sequence a cursor stands for. Ids are never compared as strings: the id is looked up.

    No cursor means "from the start", which is gone once the head of the log was purged (410).
    A cursor of another conversation answers like an unknown one, so it reveals nothing.
    """
    if cursor is None:
        if conv["purged_through"] > 0:
            raise expired(conv["id"])
        return 0
    row = (await conn.execute(select(t.events.c.conversation_id, t.events.c.sequence).where(
        t.events.c.event_id == cursor))).first()
    if row is not None and row[0] == conv["id"]:
        return row[1]
    gone = (await conn.execute(select(t.event_tombstones.c.conversation_id).where(
        t.event_tombstones.c.event_id == cursor))).first()
    if gone is not None and gone[0] == conv["id"]:
        raise expired(conv["id"])
    raise failed("Cursor is not an event of this conversation.",
                 [{"field": "after_cursor", "reason": "unknown cursor"}])


async def read_after(conn, conversation_id: str, sequence: int, limit: int) -> list:
    rows = await conn.execute(
        select(t.events).where(t.events.c.conversation_id == conversation_id,
                               t.events.c.sequence > sequence)
        .order_by(t.events.c.sequence).limit(limit))
    return list(rows.mappings())


async def history(conn, conv: Any, cursor: str | None, limit: int = DEFAULT_LIMIT) -> dict:
    after = await resolve_cursor(conn, conv, cursor)
    rows = await read_after(conn, conv["id"], after, limit + 1)
    page = rows[:limit]
    return {"items": [public_event(r, conv) for r in page],
            "next_cursor": page[-1]["event_id"] if page else cursor,
            "has_more": len(rows) > limit}


async def last_event_id(conn, conversation_id: str) -> str | None:
    row = (await conn.execute(
        select(t.events.c.event_id).where(t.events.c.conversation_id == conversation_id)
        .order_by(t.events.c.sequence.desc()).limit(1))).first()
    return row[0] if row else None
