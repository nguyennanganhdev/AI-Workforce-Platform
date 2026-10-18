"""Retained immutable publications and storage CAS, with no provider calls."""

import asyncio

import pytest
from tests.workforce.console.test_p0_publish import agent_record, evaluated_spec

from agentscope.app._service._agent_studio import materialize, pinned_view
from agentscope.app.storage import AsyncSQLAlchemyStorage
from agentscope.app.storage._base import AgentRevisionConflict


def test_fifty_two_publications_keep_first_spec_prompt_and_report():
    spec, report = evaluated_spec("First")
    record = agent_record(spec, report)
    first = record.data.versions[0].copy()
    for number in range(2, 53):
        new_spec, evaluation = evaluated_spec(f"Version {number}")
        materialize(record, new_spec, author="manager", note="regression", evaluation=evaluation)
    pinned = pinned_view(record, 1)
    assert len(record.data.versions) == 52
    assert pinned.data.name == "First"
    assert pinned.data.published_version == 1
    assert pinned.data.evaluation == report
    assert record.data.versions[0] == first
    pinned.data.evaluation["results"][0]["answer"] = "changed copy"
    assert record.data.versions[0] == first
    with pytest.raises(ValueError, match="unavailable"):
        pinned_view(record, 999)


@pytest.mark.asyncio
async def test_concurrent_sql_publish_has_one_winner_and_retains_first_version(tmp_path):
    url = f"sqlite+aiosqlite:///{(tmp_path / 'agents.sqlite').as_posix()}"
    async with AsyncSQLAlchemyStorage(url) as storage:
        spec, report = evaluated_spec("First")
        record = agent_record(spec, report)
        await storage.upsert_agent("u", record)
        a = await storage.get_agent("u", record.id)
        b = await storage.get_agent("u", record.id)
        for candidate, name in ((a, "A"), (b, "B")):
            next_spec, next_report = evaluated_spec(name)
            materialize(candidate, next_spec, author="manager", note=name, evaluation=next_report)
        result = await asyncio.gather(storage.upsert_agent("u", a), storage.upsert_agent("u", b), return_exceptions=True)
        assert sum(isinstance(item, AgentRevisionConflict) for item in result) == 1
        current = await storage.get_agent("u", record.id)
        assert current.data.published_version == 2
        assert pinned_view(current, 1).data.evaluation == report
        tampered = current.model_copy(deep=True)
        tampered.data.versions[0]["system_prompt"] = "overwrite"
        with pytest.raises(AgentRevisionConflict, match="IMMUTABLE"):
            await storage.upsert_agent("u", tampered)


@pytest.mark.asyncio
async def test_redis_writers_use_a_shared_cas_token():
    import fakeredis.aioredis

    from agentscope.app.storage import RedisStorage

    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    first, second = RedisStorage(), RedisStorage()
    first._client = second._client = client
    spec, report = evaluated_spec("First")
    record = agent_record(spec, report)
    await first.upsert_agent("u", record)
    a, b = await first.get_agent("u", record.id), await second.get_agent("u", record.id)
    for candidate, name in ((a, "A"), (b, "B")):
        next_spec, next_report = evaluated_spec(name)
        materialize(candidate, next_spec, author="manager", note=name, evaluation=next_report)
    answers = await asyncio.gather(first.upsert_agent("u", a), second.upsert_agent("u", b), return_exceptions=True)
    assert sum(isinstance(answer, AgentRevisionConflict) for answer in answers) == 1
    current = await second.get_agent("u", record.id)
    assert len(current.data.versions) == current.data.published_version == 2
    assert pinned_view(current, 1).data.evaluation == report
    await client.aclose()
