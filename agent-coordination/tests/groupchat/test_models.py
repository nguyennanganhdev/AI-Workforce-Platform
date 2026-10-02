"""Các trường tùy chọn, ràng buộc đầu vào và bộ phân loại lệnh."""

import pytest
from groupchat.models import (
    Command,
    Context,
    MessageInput,
    OpenRoom,
    ParticipantSpec,
    Query,
    TurnPolicy,
)
from pydantic import ValidationError
from support.fakes import make_context


@pytest.fixture
def command_data(harness):
    return harness.command(
        OpenRoom(
            groupchat_version_id="group-v1",
            participants=[ParticipantSpec(agent_version_id="A-v1", role="advisor")],
            initial_message=MessageInput(content="Bắt đầu"),
        )
    ).model_dump()


@pytest.mark.parametrize("value", [None, "user-123"])
def test_initiating_user_accepts_null_or_valid_id(value):
    data = make_context().model_dump() | {"initiated_by_user_id": value}
    assert Context.model_validate(data).initiated_by_user_id == value


def test_initiating_user_can_be_omitted():
    data = make_context().model_dump()
    data.pop("initiated_by_user_id")
    assert Context.model_validate(data).initiated_by_user_id is None


@pytest.mark.parametrize("value", ["", "x" * 257, 123, [], {}])
def test_initiating_user_rejects_invalid_id(value):
    with pytest.raises(ValidationError):
        Context.model_validate(
            make_context().model_dump() | {"initiated_by_user_id": value}
        )


@pytest.mark.parametrize("value", [None, "command"])
def test_command_type_accepts_null_or_string(command_data, value):
    command_data["type"] = value
    assert Command.model_validate(command_data).type == value


def test_command_type_can_be_omitted(command_data):
    command_data.pop("type")
    assert Command.model_validate(command_data).type is None


@pytest.mark.parametrize("value", [123, [], {}])
def test_command_type_rejects_non_string(command_data, value):
    command_data["type"] = value
    with pytest.raises(ValidationError):
        Command.model_validate(command_data)


@pytest.mark.parametrize(
    "field", ["tenant_id", "principal_id", "ticket_id", "ticket_generation"]
)
def test_context_still_requires_authority_and_scope_fields(field):
    data = make_context().model_dump()
    data.pop(field)
    with pytest.raises(ValidationError):
        Context.model_validate(data)


@pytest.mark.parametrize(
    "delivery,recipient,valid",
    [
        ("broadcast", None, True),
        ("direct", "A-v1", True),
        ("direct", None, False),
        ("broadcast", "A-v1", False),
    ],
)
def test_message_recipient_matches_delivery(delivery, recipient, valid):
    data = {
        "content": "Nội dung",
        "delivery": delivery,
        "recipient_agent_version_id": recipient,
    }
    if valid:
        assert MessageInput(**data).recipient_agent_version_id == recipient
    else:
        with pytest.raises(ValidationError):
            MessageInput(**data)


@pytest.mark.parametrize("participants", [[], ["A-v1", "A-v1"]])
def test_open_room_rejects_empty_or_duplicate_participants(participants):
    with pytest.raises(ValidationError):
        OpenRoom(
            groupchat_version_id="group",
            initial_message=MessageInput(content="Bắt đầu"),
            participants=[
                ParticipantSpec(agent_version_id=p, role="advisor")
                for p in participants
            ],
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_turns", 0),
        ("max_turns", True),
        ("max_turns", "1"),
        ("max_turns", 10001),
        ("max_consecutive_turns", 0),
        ("timeout_seconds", 0),
        ("timeout_seconds", float("nan")),
        ("timeout_seconds", float("inf")),
    ],
)
def test_turn_policy_rejects_invalid_limits(field, value):
    with pytest.raises(ValidationError):
        TurnPolicy(**{field: value})


@pytest.mark.parametrize("operation", ["unknown", None, 123])
def test_command_rejects_unknown_operation(command_data, operation):
    command_data["payload"]["operation"] = operation
    with pytest.raises(ValidationError):
        Command.model_validate(command_data)


def test_command_rejects_unknown_fields(command_data):
    command_data["unexpected"] = True
    with pytest.raises(ValidationError):
        Command.model_validate(command_data)


@pytest.mark.parametrize(
    "field,value", [("after_sequence", -1), ("limit", 0), ("limit", 501)]
)
def test_query_rejects_invalid_pagination(field, value):
    with pytest.raises(ValidationError):
        Query(
            request_id="query", context=make_context(), room_id="room", **{field: value}
        )


def test_initiating_user_does_not_change_room_identity():
    context = make_context()
    other = context.model_copy(update={"initiated_by_user_id": "other-user"})
    assert context.same_room_scope(other)
