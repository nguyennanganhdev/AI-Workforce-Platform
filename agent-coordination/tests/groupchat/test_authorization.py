from groupchat.models import (
    AddParticipant,
    ParticipantSpec,
    Query,
)
from support.fakes import make_context
from support.harness import room_args as args


async def test_history_check_before_join_and_late_member_gets_history(harness):
    _, opened = await harness.open()
    one = await harness.service.execute(harness.turn(opened.data))
    cmd = harness.command(
        AddParticipant(
            **args(one.data),
            participant=ParticipantSpec(agent_version_id="C-v1", role="any-role"),
        )
    )
    harness.resolver.history_allowed = False
    assert (await harness.service.execute(cmd)).error.code == "HISTORY_DENIED"
    assert len(harness.state.records[harness.ctx.scope()].snapshot.participants) == 2
    harness.resolver.history_allowed = True
    joined = await harness.service.execute(cmd)
    done = await harness.service.execute(harness.turn(joined.data, "C-v1"))
    assert len(harness.agents.calls[-1].transcript) == 2
    assert done.data.turns_used == 2
    mismatch = cmd.model_copy(deep=True)
    mismatch.idempotency_key = "new"
    mismatch.payload.expected_room_version = done.data.room_version
    assert (await harness.service.execute(mismatch)).error.code == "VERSION_MISMATCH"


async def test_auth_before_replay_queries_scope_and_revocation(harness):
    cmd, opened = await harness.open()
    harness.resolver.revoked = True
    assert (await harness.service.execute(cmd)).error.code == "FORBIDDEN"
    assert (
        await harness.service.query(
            Query(request_id="q", context=harness.ctx, room_id=opened.data.room_id)
        )
    ).error.code == "FORBIDDEN"
    harness.resolver.revoked = False
    other = make_context("OTHER")
    assert (
        await harness.service.query(
            Query(request_id="q", context=other, room_id=opened.data.room_id)
        )
    ).error.code == "NOT_FOUND"
    wrong = harness.ctx.model_copy(update={"tenant_id": "intruder"})
    assert (
        await harness.service.query(
            Query(request_id="q", context=wrong, room_id=opened.data.room_id)
        )
    ).error.code == "FORBIDDEN"


async def test_same_ticket_cannot_create_second_room_by_changing_workspace(harness):
    cmd, _opened = await harness.open()
    cmd.context.workspace_id = "other-workspace"
    cmd.idempotency_key = "other-workspace-key"
    result = await harness.service.execute(cmd)
    assert result.error.code == "SCOPE_MISMATCH"
    assert len(harness.state.records) == 1


async def test_query_dependency_errors_are_sanitized(harness):
    _, opened = await harness.open()

    async def unavailable(*args):
        raise RuntimeError("secret credential details")

    harness.resolver.authorize = unavailable
    result = await harness.service.query(
        Query(request_id="q", context=harness.ctx, room_id=opened.data.room_id)
    )
    assert result.error.code == "DEPENDENCY_UNAVAILABLE"
    assert "secret" not in result.model_dump_json()
