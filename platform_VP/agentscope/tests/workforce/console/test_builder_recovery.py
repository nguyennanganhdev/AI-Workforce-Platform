"""Failure recovery uses real storage and scripted providers; never model keys."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from agentscope.app._agent_spec import AgentSpec
from agentscope.app._router import _builder_flow as flow
from agentscope.app._router import _workforce_console as console
from agentscope.app._service import _builder_decisions as decisions
from agentscope.app._service._agent_studio import runtime_prompt
from agentscope.app._service._builder_run import BuilderRun, builder_run_guard
from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.storage import SessionConfig
from fastapi import HTTPException
from tests.workforce.console.test_builder_jev_flow import (
    CONFIG,
    SCOPE,
    TOOL,
    ScriptedClassifier,
    classifier,
    existing,
)
from tests.workforce.console.test_builder_jev_flow import storage as _storage

storage = _storage


async def run_fixture(storage, plans=None):
    session = await storage.upsert_session(
        user_id="u",
        agent_id=console._BUILDER_AGENT_ID,
        session_id="conversation",
        config=SessionConfig(workspace_id="conversation", chat_model_config=CONFIG),
    )
    outline = console.BuilderOutline(
        agents=plans
        or [console.PlannedAgent(name="Kỹ thuật", objective="Tra cứu phiếu")]
    )
    run = BuilderRun(
        storage,
        "u",
        session,
        {
            "run_id": "frozen-plan",
            "snapshot": "",
            "batches": {},
            "outline": outline.model_dump(mode="json"),
            "request": "Tra cứu phiếu",
            "scope": SCOPE.model_dump(),
        },
    )
    await run.save()
    return session, outline, run


def test_candidate_compaction_preserves_constraints_and_unique_legacy_text():
    record = existing()
    spec = AgentSpec.model_validate(record.data.spec)
    spec.prompt_override = "Chỉ hỗ trợ BQL. Không đóng phiếu. " * 300
    spec.extra_instructions = "# Quy trình\nLuôn xác minh nguồn. " * 200
    record.data.spec = spec.model_dump(mode="json")
    record.data.draft_spec = spec.model_dump(mode="json")
    record.data.system_prompt = runtime_prompt(spec)
    record.data.generated_skill = spec.extra_instructions
    original = {
        "published": record.data.spec,
        "draft": record.data.draft_spec,
        "instructions": record.data.system_prompt,
        "skill": record.data.generated_skill,
    }
    compact = decisions.candidate_state(record)
    assert compact["published"] == record.data.spec
    assert compact["draft"] == {"same_as": "published"}
    assert compact["instructions"]["derived_from"] == "published"
    assert len(json.dumps(compact)) < len(json.dumps(original)) * 0.5
    record.data.system_prompt += "Chỉ được đọc, không được xóa dữ liệu."
    assert (
        decisions.candidate_state(record)["instructions"] == record.data.system_prompt
    )


@pytest.mark.asyncio
async def test_batch_success_survives_later_failure_and_a_new_worker(storage):
    session, outline, run = await run_fixture(storage)
    records = [existing(agent_id=str(i)) for i in range(7)]
    for record in records:
        record.data.system_prompt = "Sự cố kỹ thuật của cư dân. " * 420

    class FailsLater(ScriptedClassifier):
        async def __call__(self, **kwargs):
            if self.calls:
                raise TimeoutError()
            return await super().__call__(**kwargs)

    first = classifier(storage)
    first.model = FailsLater()
    first.checkpoint = run
    result = await decisions.decide_identities(
        outline.agents, records, first, "Tra cứu phiếu"
    )
    assert result[0].action == "clarify" and first.status.state == "unavailable"
    assert first.status.calls == 2 and len(run.value["batches"]) == 1
    session = await storage.get_session("u", console._BUILDER_AGENT_ID, session.id)
    second = classifier(storage)
    second.checkpoint = BuilderRun.load(storage, "u", session)
    result = await decisions.decide_identities(
        outline.agents, records, second, "Tra cứu phiếu"
    )
    assert result[0].action == "create"
    batches = second.status.stages["builder_reuse"]["batches"]
    assert second.status.cache_hits == 1 and second.status.calls == batches - 1
    assert len(second.checkpoint.value["batches"]) == batches


@pytest.mark.asyncio
async def test_resource_failure_keeps_identity_and_retry_never_calls_outline_llm(
    storage,
):
    session, outline, run = await run_fixture(
        storage,
        [
            console.PlannedAgent(
                name="Kỹ thuật",
                objective="Tra cứu phiếu",
                tool_requirements=["Tra cứu phiếu"],
            )
        ],
    )
    await storage.upsert_agent("u", existing())

    class ResourcesFail(ScriptedClassifier):
        async def __call__(self, **kwargs):
            if "planned" in kwargs["state"] and "request" not in kwargs["state"]:
                raise TimeoutError()
            return await super().__call__(**kwargs)

    first = classifier(storage)
    first.model = ResourcesFail()
    with patch.object(flow, "BuilderClassifier", return_value=first):
        proposal = await flow.plan_proposal(
            outline,
            run.value["request"],
            [TOOL],
            {},
            {},
            None,
            object(),
            storage,
            "u",
            session.id,
            CONFIG,
            SCOPE,
            1,
            run,
        )
    assert proposal.planned_agents[0].decision.action == "create"
    assert proposal.classifier_status.state == "unavailable"
    assert proposal.classifier_status.stages["builder_reuse"]["state"] == "completed"
    assert proposal.classifier_status.stages["builder_resources"]["state"] == "error"
    await console._persist_builder_turn(
        storage, "u", session.id, "Tra cứu phiếu", proposal
    )
    second = classifier(storage, {f"tools:0:0:{TOOL.id}": 0.95})
    principal = SimpleNamespace(
        tenant_id=SCOPE.tenant_id, domain_id=SCOPE.domain_id, area_id=SCOPE.area_id
    )
    with (
        patch.object(flow, "BuilderClassifier", return_value=second),
        patch.object(console, "_catalog", AsyncMock(return_value=[TOOL])),
        patch.object(console, "_library", AsyncMock(return_value=({}, {}))),
        patch.object(
            console,
            "get_model",
            AsyncMock(side_effect=AssertionError("Must not call LLM")),
        ),
        patch.object(
            console,
            "_outline",
            AsyncMock(side_effect=AssertionError("Must keep outline")),
        ),
    ):
        result = await console.retry_builder_verification(
            console.PublishRequest(
                conversation_id=session.id,
                proposal_id=proposal.proposal_id,
                expected_revision=1,
            ),
            "u",
            storage,
            object(),
            principal,
            InMemoryMessageBus(),
        )
        assert result.proposal_id == proposal.proposal_id and result.revision == 2
        assert [(p.name, p.objective) for p in result.planned_agents] == [
            (p.name, p.objective) for p in outline.agents
        ]
        assert second.status.cache_hits == 1 and len(second.model.calls) == 1
        assert result.planned_agents[0].suggested_tools[0].id == TOOL.id
        with pytest.raises(HTTPException) as exc:
            await console.retry_builder_verification(
                console.PublishRequest(
                    conversation_id=session.id,
                    proposal_id=proposal.proposal_id,
                    expected_revision=1,
                ),
                "u",
                storage,
                object(),
                principal,
                InMemoryMessageBus(),
            )
        assert exc.value.status_code == 409
    assert len(await storage.list_agents("u")) == 1


@pytest.mark.asyncio
async def test_catalog_change_invalidates_checkpoints_and_rechecks_identity(storage):
    session, outline, run = await run_fixture(storage)
    record = existing()
    await storage.upsert_agent("u", record)
    first = classifier(storage)
    with patch.object(flow, "BuilderClassifier", return_value=first):
        await flow.plan_proposal(
            outline,
            "Tra cứu phiếu",
            [],
            {},
            {},
            None,
            object(),
            storage,
            "u",
            session.id,
            CONFIG,
            SCOPE,
            1,
            run,
        )
    record.data.system_prompt += "Không được điều phối."
    await storage.upsert_agent("u", record)
    second = classifier(storage, {"same_0_0": 0.95, "covers_0_0": 0.05})
    with patch.object(flow, "BuilderClassifier", return_value=second):
        result = await flow.plan_proposal(
            outline,
            "Tra cứu phiếu",
            [],
            {},
            {},
            None,
            object(),
            storage,
            "u",
            session.id,
            CONFIG,
            SCOPE,
            2,
            run,
        )
    assert len(second.model.calls) == 1 and second.status.cache_hits == 0
    assert result.planned_agents[0].decision.action == "revise"


@pytest.mark.asyncio
async def test_concurrent_retries_use_the_same_distributed_lock_key():
    bus = InMemoryMessageBus()
    async with builder_run_guard(bus, "u", "conversation"):
        with pytest.raises(HTTPException) as exc:
            async with builder_run_guard(bus, "u", "conversation"):
                pytest.fail("Concurrent run must not enter")
        assert exc.value.status_code == 409
    async with builder_run_guard(bus, "u", "conversation"):
        pass


@pytest.mark.asyncio
async def test_frozen_outline_is_durable_before_jev_starts_and_excludes_assistant_text(
    storage,
):
    session, outline, _ = await run_fixture(storage)
    model = SimpleNamespace(context_size=100_000)
    body = console.PrepareRequest(
        message="Tra cứu phiếu", chat_model_config=CONFIG, conversation_id=session.id
    )
    with (
        patch.object(console, "_catalog", AsyncMock(return_value=[])),
        patch.object(console, "_library", AsyncMock(return_value=({}, {}))),
        patch.object(console, "get_model", AsyncMock(return_value=model)),
        patch.object(
            console,
            "_prepare_builder_memory",
            AsyncMock(return_value="Assistant proposes deleting data"),
        ),
        patch.object(console, "_outline", AsyncMock(return_value=(outline, 100, 100))),
        patch.object(console, "_record_builder_prompt_measurement", AsyncMock()),
        patch.object(
            flow, "plan_proposal", AsyncMock(side_effect=RuntimeError("Worker stopped"))
        ),
        pytest.raises(RuntimeError),
    ):
        await console._prepare_builder(
            body, "u", storage, object(), session, None, SCOPE
        )
    reloaded = await storage.get_session("u", console._BUILDER_AGENT_ID, session.id)
    run = BuilderRun.load(storage, "u", reloaded)
    assert run.value["outline"]["agents"] == outline.model_dump()["agents"]
    assert run.value["request"] == body.message
    proposal = console._stored_proposal(
        await console._list_all_builder_messages(storage, "u", session.id)
    )
    assert proposal.proposal_id == run.value["run_id"]
    assert (
        proposal.retry_verification
        and proposal.classifier_status.state == "unavailable"
    )
    assert await storage.list_agents("u") == []


@pytest.mark.asyncio
async def test_credential_change_or_revoked_access_cannot_reuse_cached_answers(storage):
    _, outline, run = await run_fixture(storage)
    records = [existing()]
    first = classifier(storage)
    first.credential_digest = "credential-version-one"
    first.checkpoint = run
    await decisions.decide_identities(outline.agents, records, first, "Tra cứu phiếu")
    second = classifier(storage)
    second.credential_digest = "credential-version-two"
    second.checkpoint = run
    await decisions.decide_identities(outline.agents, records, second, "Tra cứu phiếu")
    assert second.status.calls == 1 and second.status.cache_hits == 0
    revoked = decisions.BuilderClassifier(
        SimpleNamespace(list_resource=AsyncMock(return_value=[])),
        storage,
        SCOPE,
        "conversation",
    )
    revoked.checkpoint = run
    result = await decisions.decide_identities(
        outline.agents, records, revoked, "Tra cứu phiếu"
    )
    assert result[0].action == "clarify" and revoked.status.calls == 0


@pytest.mark.asyncio
async def test_legacy_failed_plan_can_be_rechecked_without_new_llm_outline(storage):
    session, outline, _ = await run_fixture(storage)
    session.state.middle_context.clear()
    await storage.update_session_state("u", session.agent_id, session.id, session.state)
    previous = console.ProposalView(
        conversation_id=session.id,
        proposal_id="legacy",
        revision=1,
        status="needs_input",
        assistant_message="Saved failure",
        scope=SCOPE,
        chat_model_config=CONFIG,
        fixed_config={},
        planned_agents=[
            console.PlannedAgentView(**p.model_dump()) for p in outline.agents
        ],
        classifier_status=decisions.ClassifierStatus(state="unavailable"),
    )
    await console._persist_builder_turn(
        storage, "u", session.id, "Tra cứu phiếu", previous
    )
    principal = SimpleNamespace(
        tenant_id=SCOPE.tenant_id, domain_id=SCOPE.domain_id, area_id=SCOPE.area_id
    )
    with (
        patch.object(console, "_catalog", AsyncMock(return_value=[])),
        patch.object(console, "_library", AsyncMock(return_value=({}, {}))),
        patch.object(
            console, "get_model", AsyncMock(side_effect=AssertionError("No LLM"))
        ),
    ):
        result = await console.retry_builder_verification(
            console.PublishRequest(
                conversation_id=session.id, proposal_id="legacy", expected_revision=1
            ),
            "u",
            storage,
            object(),
            principal,
            InMemoryMessageBus(),
        )
    assert (
        result.proposal_id == "legacy"
        and result.planned_agents[0].name == outline.agents[0].name
    )
    assert result.planned_agents[0].decision.action == "create"
    assert result.classifier_status.calls == 0


@pytest.mark.asyncio
async def test_many_questions_about_one_resource_are_split_without_losing_evidence(
    storage,
):
    value = classifier(storage)
    questions = {
        str(i): decisions.question(
            "Check this operation against all mandatory constraints. " * 50
        )
        for i in range(400)
    }
    result = await decisions.classify_catalog(
        {"planned": ["Role"]},
        [("tools", "one-resource", {"permission": "read only"}, questions)],
        value,
        "builder_resources",
    )
    assert len(result) == 400 and value.status.calls > 1
    assert sum(len(q) for _, q in value.model.calls) == 400
    assert all(
        state["tools"]["one-resource"]["permission"] == "read only"
        for state, _ in value.model.calls
    )


@pytest.mark.asyncio
async def test_resume_skips_already_rejected_parent_and_completed_split(storage):
    import httpx2
    from typesafe_sdk import TypeSafeBadRequestError

    _, outline, run = await run_fixture(storage)
    records = [existing()]

    class SplitThenFail(ScriptedClassifier):
        def __init__(self):
            super().__init__()
            self.single = 0

        async def __call__(self, **kwargs):
            if len(kwargs["questions"]) > 1:
                raise TypeSafeBadRequestError(
                    400, {"error": "max_tokens_exceeded"}, httpx2.Headers()
                )
            self.single += 1
            if self.single == 2:
                raise TimeoutError()
            return await super().__call__(**kwargs)

    first = classifier(storage)
    first.model = SplitThenFail()
    first.checkpoint = run
    result = await decisions.decide_identities(
        outline.agents, records, first, "Tra cứu phiếu"
    )
    assert result[0].action == "clarify" and first.status.calls == 3
    second = classifier(storage)
    second.checkpoint = run
    result = await decisions.decide_identities(
        outline.agents, records, second, "Tra cứu phiếu"
    )
    assert result[0].action == "create"
    assert second.status.calls == 1 and second.status.cache_hits == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('classifier_state', ['unavailable', 'active'])
async def test_http_duplicate_retry_is_rejected_and_other_owner_cannot_read_it(storage, classifier_state):
    import httpx
    from fastapi import FastAPI

    session, outline, run = await run_fixture(storage)
    await storage.upsert_agent("u", existing())
    previous = console.ProposalView(
        conversation_id=session.id,
        proposal_id=run.value["run_id"],
        revision=1,
        status="needs_input",
        assistant_message="Saved failure",
        scope=SCOPE,
        chat_model_config=CONFIG,
        fixed_config={},
        planned_agents=[
            console.PlannedAgentView(**p.model_dump()) for p in outline.agents
        ],
        classifier_status=decisions.ClassifierStatus(state=classifier_state),
    )
    await console._persist_builder_turn(
        storage, "u", session.id, "Tra cứu phiếu", previous
    )
    app = FastAPI()
    app.include_router(console.workforce_console_router)
    principal = SimpleNamespace(
        tenant_id=SCOPE.tenant_id, domain_id=SCOPE.domain_id, area_id=SCOPE.area_id
    )
    bus = InMemoryMessageBus()
    app.dependency_overrides.update(
        {
            console.get_current_user_id: lambda: "u",
            console.get_current_principal: lambda: principal,
            console.get_storage: lambda: storage,
            console.get_resource_access_service: lambda: object(),
            console.get_message_bus: lambda: bus,
        }
    )

    class SlowClassifier(ScriptedClassifier):
        async def __call__(self, **kwargs):
            await asyncio.sleep(0.05)
            return await super().__call__(**kwargs)

    value = classifier(storage)
    value.model = SlowClassifier()
    payload = {
        "conversation_id": session.id,
        "proposal_id": previous.proposal_id,
        "expected_revision": 1,
    }
    with (
        patch.object(flow, "BuilderClassifier", return_value=value),
        patch.object(console, "_catalog", AsyncMock(return_value=[])),
        patch.object(console, "_library", AsyncMock(return_value=({}, {}))),
        patch.object(
            console, "get_model", AsyncMock(side_effect=AssertionError("No LLM"))
        ),
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://offline"
        ) as client:
            responses = await asyncio.gather(
                *[
                    client.post(
                        "/workforce/console/builder/retry-verification", json=payload
                    )
                    for _ in range(2)
                ]
            )
            assert sorted(r.status_code for r in responses) == [200, 409]
            assert len(value.model.calls) == 1
            app.dependency_overrides[console.get_current_user_id] = lambda: (
                "other-owner"
            )
            response = await client.post(
                "/workforce/console/builder/retry-verification", json=payload
            )
            assert response.status_code == 404


@pytest.mark.asyncio
async def test_redis_lock_serializes_distinct_workers_and_releases_after_failure():
    import fakeredis
    from agentscope.app.message_bus import RedisMessageBus
    from fakeredis.aioredis import FakeRedis

    server = fakeredis.FakeServer()
    clients = [FakeRedis(server=server, decode_responses=True) for _ in range(2)]
    buses = [RedisMessageBus(), RedisMessageBus()]
    for bus, client in zip(buses, clients):
        bus._client = client
    try:
        with pytest.raises(RuntimeError, match="worker failure"):
            async with builder_run_guard(buses[0], "u", "conversation"):
                with pytest.raises(HTTPException) as exc:
                    async with builder_run_guard(buses[1], "u", "conversation"):
                        pytest.fail("Workers must not enter the same run concurrently")
                assert exc.value.status_code == 409
                async with builder_run_guard(buses[1], "other-owner", "conversation"):
                    pass
                raise RuntimeError("worker failure")
        async with builder_run_guard(buses[1], "u", "conversation"):
            pass
    finally:
        for client in clients:
            await client.aclose()
