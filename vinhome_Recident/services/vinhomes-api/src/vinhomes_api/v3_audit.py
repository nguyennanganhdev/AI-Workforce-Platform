"""Small transaction-local audit writer for administration without a ticket."""

import json
from uuid import UUID, uuid4
from sqlalchemy import text


async def audit(
    db,
    actor: str,
    event: str,
    target_type: str,
    target_id: str,
    payload: dict[str, object],
) -> None:
    from .integration import CURRENT
    delegation = CURRENT.get()
    kind, initiator, correlation = "person", actor, uuid4()
    if delegation is not None:
        # The person is still the actor; the client that did it for them is the initiator.
        kind, initiator = "agent", delegation["client_id"]
        payload = {**payload, "delegationId": delegation["delegation_id"], "onBehalfOf": actor,
                   "idempotencyKey": delegation["idempotency_key"], "tool": delegation["tool"]}
        try:
            correlation = UUID(delegation["correlation_id"])
        except (ValueError, TypeError):
            pass
    await db.execute(
        text("""
        insert into audit_events(tenant_id,actor_user_id,initiator_kind,initiator_id,event_type,target_type,target_id,payload,correlation_id)
        values (nullif(current_setting('app.tenant_id',true),'')::uuid,:actor,:kind,:initiator,:event,:type,:target,cast(:payload as jsonb),:correlation)
    """),
        {
            "actor": actor,
            "kind": kind,
            "initiator": initiator,
            "event": event,
            "type": target_type,
            "target": target_id,
            "payload": json.dumps(payload, default=str),
            "correlation": correlation,
        },
    )
