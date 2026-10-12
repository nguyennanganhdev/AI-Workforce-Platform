"""Chat messages of a workflow. Every message is written with the public event that announces it."""
from __future__ import annotations

from typing import Any

from sqlalchemy import insert, or_, select

from . import tables as t
from .common import iso, now
from .events import emit
from .tables import new_id
from .workflows import IllegalTransition


def public_message(row: Any) -> dict:
    return {"message_id": row["id"], "workflow_id": row["workflow_id"], "sender": row["sender"],
            "text": row["text"], "created_at": iso(row["created_at"])}


async def add_user_message(conn, workflow: Any, request_id: str, text: str, sequence: int) -> str:
    """The resident's text. `sequence` is that of the request.accepted event written just before."""
    mid = new_id("msg")
    await conn.execute(insert(t.messages).values(
        id=mid, conversation_id=workflow["conversation_id"], workflow_id=workflow["id"],
        request_id=request_id, sender="user", text=text, asset_ids=[], sequence=sequence,
        created_at=now()))
    return mid


async def add_assistant_message(conn, workflow: Any, text: str, request_id: str | None, *,
                                expects: str | None = None, outcome: str | None = None,
                                source: str | None = None) -> dict:
    """What the assistant says to the resident: the message row and the assistant.message event
    in the caller's transaction. The one path for anything shown to the resident (CaseSay, S3).
    `expects` and `outcome` record what the leader meant by it, for settle; `source` says who wrote it when it was
    not the leader (a provider's template), so the leader's own context can show it as a quotation.

    Refused once the workflow is closed. The state is re-read after the event took the
    conversation's write lock, so a close that committed since the caller looked is seen.
    """
    mid = new_id("msg")
    text = text.replace("\x00", "")  # PostgreSQL cannot store NUL in text
    ev = await emit(conn, workflow["conversation_id"], "assistant.message",
                    {"message_id": mid, "text": text}, workflow=workflow)
    state = (await conn.execute(select(t.workflows.c.state).where(
        t.workflows.c.id == workflow["id"]))).scalar_one()
    if state == "closed":
        raise IllegalTransition("a closed workflow takes no new messages")
    await conn.execute(insert(t.messages).values(
        id=mid, conversation_id=workflow["conversation_id"], workflow_id=workflow["id"],
        request_id=request_id, sender="assistant", text=text, asset_ids=[], expects=expects,
        outcome=outcome, source=source, sequence=ev.sequence, created_at=now()))
    return {"message_id": mid, "event_id": ev.event_id, "sequence": ev.sequence}


async def of_request(conn, request_id: str) -> list[dict]:
    """The assistant messages a request produced, oldest first (contract 9.1 `result.messages`)."""
    rows = await conn.execute(select(t.messages).where(
        t.messages.c.request_id == request_id, t.messages.c.sender == "assistant")
        .order_by(t.messages.c.sequence))
    return [public_message(r) for r in rows.mappings()]


async def owed(conn, workflow_id: str) -> tuple[str, str] | None:
    """(expects, text) of the leader's last question when the resident has not answered it yet: the newest message that
    is either the resident's or a leader's question is the question. An event from outside does not answer it."""
    row = (await conn.execute(select(t.messages.c.sender, t.messages.c.expects, t.messages.c.text).where(
        t.messages.c.workflow_id == workflow_id,
        or_(t.messages.c.sender == "user", t.messages.c.expects.in_(("reply", "confirmation"))))
        .order_by(t.messages.c.sequence.desc()).limit(1))).first()
    return (row[1], row[2]) if row is not None and row[0] == "assistant" else None
