"""Small transaction-local audit writer for administration without a ticket."""

import json
from uuid import uuid4
from sqlalchemy import text


async def audit(
    db,
    actor: str,
    event: str,
    target_type: str,
    target_id: str,
    payload: dict[str, object],
) -> None:
    await db.execute(
        text("""
        insert into audit_events(tenant_id,actor_user_id,initiator_kind,initiator_id,event_type,target_type,target_id,payload,correlation_id)
        values (nullif(current_setting('app.tenant_id',true),'')::uuid,:actor,'person',:actor,:event,:type,:target,cast(:payload as jsonb),:correlation)
    """),
        {
            "actor": actor,
            "event": event,
            "type": target_type,
            "target": target_id,
            "payload": json.dumps(payload, default=str),
            "correlation": uuid4(),
        },
    )
