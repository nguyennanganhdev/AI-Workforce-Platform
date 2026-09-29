"""Explicit v1 migration requiring externally authorized context and mapping."""

from collections.abc import Awaitable, Callable

from .models import (
    Command,
    Context,
    MessageInput,
    OpenRoom,
    ParticipantSpec,
    RoomError,
    TurnPolicy,
)


async def normalize_v1(
    payload: dict,
    *,
    context: Context,
    groupchat_version_id: str,
    request_id: str,
    trace_id: str,
    idempotency_key: str,
    map_version: Callable[[str], Awaitable[str]],
) -> Command:
    if payload.get("version") != 1 or payload.get("ticket_id") != context.ticket_id:
        raise RoomError(
            "VALIDATION_ERROR", "v1 requires matching authorized ticket context"
        )
    try:
        participants = [
            ParticipantSpec(
                agent_version_id=await map_version(p["agent_version_id"]),
                role=p["role"],
            )
            for p in payload["participants"]
        ]
        if payload["initial_message"]["type"] != "MO_DAU":
            raise RoomError("VALIDATION_ERROR", "Unsupported v1 initial message type")
        return Command(
            request_id=request_id,
            trace_id=trace_id,
            idempotency_key=idempotency_key,
            context=context,
            payload=OpenRoom(
                room_id=payload.get("room_id"),
                groupchat_version_id=groupchat_version_id,
                participants=participants,
                turn_policy=TurnPolicy.model_validate(payload.get("turn_policy", {})),
                initial_message=MessageInput(
                    content=payload["initial_message"]["content"]
                ),
            ),
        )
    except (KeyError, TypeError) as exc:
        raise RoomError(
            "VALIDATION_ERROR", "Missing required v1 data; no inferred authority"
        ) from exc
