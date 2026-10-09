"""What happened in the domain, for the clients that follow it (docs/domain/HOP_DONG_TICH_HOP.md section 6).

An event carries codes and statuses, never personal data: a client that wants more asks through a tool
and is checked like anyone else.
"""

import json
from uuid import UUID, uuid4

from sqlalchemy import text

TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"
# Ticket events with these prefixes are published as they are written.
TICKET_PREFIXES = ("ticket.", "plan.", "work_order.", "work_assignment.", "water.", "triage.")


async def emit(db, topic: str, payload: dict, *, event_id: UUID | None = None, dedupe_key: str | None = None) -> bool:
    """Queue one event. True when it was queued, False when its dedupe key was already used."""
    done = await db.execute(text(f"""
        insert into event_outbox(tenant_id,event_id,topic,payload,schema_version,available_at,dedupe_key)
        values ({TENANT},:event_id,:topic,cast(:payload as jsonb),1,now(),:dedupe)
        on conflict do nothing returning id
    """), {"event_id": event_id or uuid4(), "topic": topic, "payload": json.dumps(payload, default=str), "dedupe": dedupe_key})
    return done.first() is not None


def publishable(event_type: str) -> bool:
    return event_type.startswith(TICKET_PREFIXES)
