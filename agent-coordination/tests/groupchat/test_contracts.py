"""Kiểm tra schema đã công bố, dữ liệu mẫu và chuyển đổi hợp đồng v1."""

import json
import asyncio
from pathlib import Path

import jsonschema
import pytest
from groupchat.compat import normalize_v1
from groupchat.models import (
    Command,
    ContextItem,
    MentionAgent,
    PutContext,
    PutTask,
    Query,
    Result,
    RoomError,
    ScopeState,
    TaskItem,
)
from pydantic import TypeAdapter
from support.fakes import make_context
from support.harness import room_args

SCHEMAS = Path(__file__).resolve().parents[3] / "docs/teams/dong/agent-room-schemas"
EXAMPLES = json.loads((SCHEMAS / "examples-v2.json").read_text())


def schema(name):
    return json.loads((SCHEMAS / f"{name}.schema.json").read_text())


@pytest.mark.parametrize("name,model", [
    ("command", Command), ("query", Query), ("result", Result), ("state", ScopeState),
])
def test_published_schema_matches_model(name, model):
    published = schema(name)
    jsonschema.Draft202012Validator.check_schema(published)
    assert published == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **TypeAdapter(model).json_schema(),
    }


@pytest.mark.parametrize('artifact_hash', [None, 'verified-report-artifacts'])
async def test_active_checkpoint_matches_published_schema(harness, artifact_hash):
    _, opened = await harness.open()
    harness.agents.delay = 10
    running = asyncio.create_task(harness.service.execute(harness.turn(opened.data)))
    try:
        await harness.agents.started.wait()
        state = harness.state.records[harness.ctx.scope()].model_copy(deep=True)
        state.snapshot.active_operation.artifact_hash = artifact_hash
        serialized = state.model_dump(mode='json')
        jsonschema.validate(serialized, schema('state'))
        assert ScopeState.model_validate(serialized).snapshot.active_operation.artifact_hash == artifact_hash
    finally:
        running.cancel()
        await asyncio.gather(running, return_exceptions=True)


@pytest.mark.parametrize("example_name", EXAMPLES)
def test_example_request_matches_schema_and_model(example_name):
    request = EXAMPLES[example_name]["request"]
    jsonschema.validate(request, schema("command"))
    assert (
        Command.model_validate(request).payload.operation
        == request["payload"]["operation"]
    )


@pytest.mark.parametrize("example_name", EXAMPLES)
def test_example_result_matches_schema_and_model(example_name):
    result = EXAMPLES[example_name]["result"]
    jsonschema.validate(result, schema("result"))
    assert TypeAdapter(Result).validate_python(result).status == result["status"]


def test_result_rejects_mixed_success_and_error_fields():
    result = EXAMPLES["open_room"]["result"] | {"error": {"code": "invalid"}}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(result, schema("result"))


@pytest.mark.parametrize("ticket,valid", [("TK-123", True), ("other", False)])
async def test_v1_conversion_requires_matching_authorized_context(ticket, valid):
    v1 = json.loads((SCHEMAS / "open-v1.json").read_text())

    async def mapping(label):
        return {"technical-v3": "A-v1", "security-v2": "B-v1"}[label]

    kwargs = {
        "context": make_context(ticket),
        "groupchat_version_id": "test-group-v1",
        "request_id": "req",
        "trace_id": "trace",
        "idempotency_key": "key",
        "map_version": mapping,
    }
    if not valid:
        with pytest.raises(RoomError, match="matching authorized ticket context"):
            await normalize_v1(v1, **kwargs)
        return
    command = await normalize_v1(v1, **kwargs)
    assert command.payload.version == 2
    assert [p.agent_version_id for p in command.payload.participants] == [
        "A-v1",
        "B-v1",
    ]
    assert command.context == kwargs["context"]


@pytest.mark.parametrize("operation", ["put_task", "put_context", "mention_agent"])
async def test_command_result_and_persisted_state_match_schemas(harness, operation):
    _, opened = await harness.open()
    args = room_args(opened.data)
    payloads = {
        "put_task": PutTask(
            **args,
            task=TaskItem(
                task_id="task", description="Kiểm tra", assignee_agent_version_id="B-v1"
            ),
        ),
        "put_context": PutContext(
            **args,
            item=ContextItem(
                item_id="fact",
                content="Dữ kiện ticket",
                reader_agent_version_ids=["B-v1"],
            ),
        ),
        "mention_agent": MentionAgent(
            **args, mentioned_agent_id="B", instruction="Câu hỏi"
        ),
    }
    command = harness.command(payloads[operation])
    jsonschema.validate(command.model_dump(mode="json"), schema("command"))
    result = await harness.service.execute(command)
    assert result.status == "completed"
    jsonschema.validate(result.model_dump(mode="json"), schema("result"))
    jsonschema.validate(
        harness.state.records[harness.ctx.scope()].model_dump(mode="json"),
        schema("state"),
    )
