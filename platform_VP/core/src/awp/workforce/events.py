"""Public views deliberately exclude prompts, tool traces and service identities."""
import time

from sqlalchemy import select

from . import schema as s
from .service import Fault, row, stamp


async def own_conversation(service, conn, client, conversation_id, user):
    conv = await row(conn, s.conversations, s.conversations.c.id == conversation_id,
                     s.conversations.c.client_id == client["id"], s.conversations.c.user_id == user)
    if not conv:
        raise Fault(404, "NOT_FOUND")
    route = await row(conn, s.routes, s.routes.c.id == conv["route_id"])
    if not route or route["status"] != "active":
        raise Fault(403, "ROUTE_NOT_AUTHORIZED")
    flows = (await conn.execute(select(s.workflows.c.id).where(s.workflows.c.conversation_id == conv["id"]))).scalars().all()
    for workflow_id in flows:
        await service.binding(conn, client, workflow_id, user)
    return conv


def envelope(conv, event):
    ticket = conv["external_ticket_id"]
    return {"schema_version": "1", "event_id": event["id"], "sequence": event["sequence"],
        "event_type": event["event_type"], "occurred_at": stamp(event["occurred"]),
        "recorded_at": stamp(event["recorded"]), "conversation_id": conv["id"],
        "external_ticket_id": None if ticket.startswith("conversation:") else ticket,
        "external_conversation_id": conv["external_conversation_id"], "external_user_id": conv["user_id"],
        "workflow_id": event["workflow_id"], "ticket_id": None, "payload": event["payload"]}


async def history(service, client, conversation_id, user, cursor=None, limit=100):
    async with service.rt.db.engine.connect() as conn:
        conv = await own_conversation(service, conn, client, conversation_id, user)
        sequence = 0
        if cursor:
            prior = await row(conn, s.events, s.events.c.id == cursor)
            if not prior:
                if cursor != conv["latest_event_id"]:
                    raise Fault(410, "EVENT_CURSOR_EXPIRED")
                sequence = conv["sequence"]
            elif prior["conversation_id"] != conversation_id:
                raise Fault(403, "EVENT_CURSOR_NOT_AUTHORIZED")
            else:
                sequence = prior["sequence"]
        if sequence < conv["purged_through"]:
            raise Fault(410, "EVENT_CURSOR_EXPIRED")
        records = (await conn.execute(select(s.events).where(s.events.c.conversation_id == conversation_id,
            s.events.c.sequence > sequence).order_by(s.events.c.sequence).limit(limit + 1))).mappings().all()
        items = [envelope(conv, dict(item)) for item in records[:limit]]
        return {"items": items, "next_cursor": items[-1]["event_id"] if items else cursor,
                "has_more": len(records) > limit}


async def snapshot(service, client, conversation_id, user):
    # Lock the conversation writer row so states/messages/approvals and cursor describe one instant.
    async with service.tx() as conn:
        conv = await own_conversation(service, conn, client, conversation_id, user)
        conv = await row(conn, s.conversations, s.conversations.c.id == conversation_id, lock=True)
        flows = (await conn.execute(select(s.workflows).where(s.workflows.c.conversation_id == conversation_id))).mappings().all()
        approvals = (await conn.execute(select(s.approvals).where(s.approvals.c.workflow_id.in_([x["id"] for x in flows]),
                      s.approvals.c.status == "pending", s.approvals.c.expires > time.time()))).mappings().all()
        messages = (await conn.execute(select(s.messages).where(s.messages.c.conversation_id == conversation_id)
                    .order_by(s.messages.c.sequence.desc()).limit(501))).mappings().all()
        return {"conversation_id": conversation_id,
            "external_ticket_id": None if conv["external_ticket_id"].startswith("conversation:") else conv["external_ticket_id"],
            "external_conversation_id": conv["external_conversation_id"], "external_user_id": user,
            "workflows": [{"workflow_id": x["id"], "ticket_id": None, "state": x["state"],
                           "next_action": service.next_action(x), "revision": x["revision"]} for x in flows],
            "messages": [x["payload"] for x in reversed(messages[:500])], "messages_truncated": len(messages) > 500,
            "pending_approvals": [{k: x[k] for k in ("id", "workflow_id", "status", "arguments_hash", "quote_ref", "revision", "summary")}
                                  | {"expires_at": stamp(x["expires"])} for x in approvals],
            "snapshot_cursor": conv["latest_event_id"]}
