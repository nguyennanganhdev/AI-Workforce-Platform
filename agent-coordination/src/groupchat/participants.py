from .models import Participant, ParticipantSpec, RoomError, Snapshot


def member(room: Snapshot, version_id: str) -> Participant:
    for participant in room.participants:
        if participant.agent_version_id == version_id:
            return participant
    raise RoomError("NOT_MEMBER")


def validate_resolved(
    spec: ParticipantSpec, resolved: Participant, room: Snapshot | None
) -> None:
    if resolved.agent_version_id != spec.agent_version_id or resolved.role != spec.role:
        raise RoomError("VERSION_MISMATCH")
    if room and any(
        p.platform_agent_id == resolved.platform_agent_id for p in room.participants
    ):
        raise RoomError(
            "VERSION_MISMATCH", "Platform agent already pinned in this room"
        )
