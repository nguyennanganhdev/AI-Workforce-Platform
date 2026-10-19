import asyncio
import copy
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from agentscope.agent import ContextConfig, ReActConfig
from agentscope.app._agent_spec import AgentSpec, SpecTest, spec_hash
from agentscope.app._router import _workforce_console as console
from agentscope.app._service._agent_studio import materialize, record_test_run, set_draft
from agentscope.app._service._publish_gate import EVALUATOR, publication_blocker, publish_blocker, seal_report, trusted_publication
from agentscope.app.storage import AgentData, AgentRecord, ChatModelConfig
from agentscope.message import AssistantMsg


def evaluated_spec(name="Agent"):
    spec = AgentSpec(name=name, tests=[SpecTest(id=f"test-{n}", scenario=f"Question {n}", expected="Safe response",
                                              safety_critical=n == 0) for n in range(5)])
    report = {"spec_hash": spec_hash(spec), "evaluator": EVALUATOR, "ran_at": datetime.now(UTC).isoformat(),
              "total": 5, "passed": 5, "pass_rate": 1., "errors": 0, "model_error": None,
              "results": [{"test_id": test.id, "passed": True, "model_evaluated": True,
                           "judge": {"passed": True}, "checks": [], "error": None} for test in spec.tests]}
    return spec, seal_report(spec, report)


def agent_record(spec, report=None):
    record = AgentRecord(user_id="u", data=AgentData(name=spec.name,
                         context_config=ContextConfig(), react_config=ReActConfig()))
    if report:
        materialize(record, spec, author="manager", note="tested", evaluation=report)
    return record


def test_static_readiness_cannot_publish_and_report_is_immutable():
    spec, report = evaluated_spec()
    assert not publish_blocker(spec, report)
    for invalid in (None, {"passed": True, "score": 1.}, {**report, "spec_hash": "wrong"},
                    {**report, "total": 4}, {**report, "results": report["results"][:-1]}):
        assert publish_blocker(spec, invalid)
    changed = copy.deepcopy(report); changed["results"][0]["answer"] = "tampered"
    assert publish_blocker(spec, changed)
    changed_spec = spec.model_copy(deep=True); changed_spec.goal = "Different behavior"
    assert publish_blocker(changed_spec, report)


def test_safety_failure_blocks_even_at_eighty_percent():
    spec, report = evaluated_spec()
    report["results"][0].update(passed=False, judge={"passed": False})
    report.update(passed=4, pass_rate=.8)
    report = seal_report(spec, report)
    assert not report["publishable"]
    assert "an toàn" in publish_blocker(spec, report)


def test_safety_case_blocks_on_a_violation_not_on_wording():
    spec, report = evaluated_spec()
    wording = [{"name": "task_completion", "passed": False}, {"name": "evidence", "passed": True},
               {"name": "scope_safety", "passed": True}, {"name": "tool_use", "passed": True}]
    report["results"][0].update(passed=False, judge={"passed": False, "criteria": wording})
    report.update(passed=4, pass_rate=.8)
    assert not publish_blocker(spec, seal_report(spec, report))
    for violated in ("scope_safety", "evidence"):
        candidate = copy.deepcopy(report)
        for criterion in candidate["results"][0]["judge"]["criteria"]:
            criterion["passed"] = criterion["name"] != violated
        assert "an toàn" in publish_blocker(spec, seal_report(spec, candidate))
    failed_check = copy.deepcopy(report)
    failed_check["results"][0]["checks"] = [{"type": "must_not_include", "passed": False}]
    assert "an toàn" in publish_blocker(spec, seal_report(spec, failed_check))


def test_gate_counts_tool_use_as_advice_like_the_evaluator():
    spec, report = evaluated_spec()
    advisory = {"passed": False, "criteria": [{"name": "task_completion", "passed": True},
                                               {"name": "tool_use", "passed": False}]}
    report["results"][1]["judge"] = advisory
    assert not publish_blocker(spec, seal_report(spec, report))
    named = spec.model_copy(deep=True)
    named.tests[1].expect_tool = "search_hotels"
    report["spec_hash"] = spec_hash(named)
    assert "không khớp" in publish_blocker(named, seal_report(named, report))


def test_no_judge_error_or_configuration_only_report_can_publish():
    spec, report = evaluated_spec()
    for field, value in [("model_evaluated", False), ("error", "model unavailable"), ("judge", None)]:
        candidate = copy.deepcopy(report); candidate["results"][2][field] = value
        assert publish_blocker(spec, seal_report(spec, candidate))
    no_safety = spec.model_copy(deep=True)
    no_safety.tests[0].safety_critical = False
    assert publish_blocker(no_safety, report)


def test_draft_change_invalidates_report_and_studio_uses_same_policy():
    from agentscope.app._router._workforce_studio import _publish_blocker
    spec, report = evaluated_spec()
    record = agent_record(spec)
    set_draft(record, spec, author="manager", note="test"); record_test_run(record, report)
    assert _publish_blocker(record, spec) == publish_blocker(spec, report) == ""
    edited = spec.model_copy(deep=True); edited.goal = "New goal"
    set_draft(record, edited, author="manager", note="edit")
    assert _publish_blocker(record, edited)
    with pytest.raises(ValueError):
        materialize(record, edited, author="manager", note="unsafe", evaluation=report)


def test_trusted_provisioning_is_explicit_and_not_a_business_publish_bypass():
    spec = AgentSpec(name="Provisioned")
    report = trusted_publication(spec, source="approved_provisioning", actor="operator", reason="Partner bootstrap")
    assert publication_blocker(spec, report)
    assert not publication_blocker(spec, report, allow_provisioning=True)
    with pytest.raises(ValueError):
        materialize(agent_record(spec), spec, author="manager", note="untrusted", evaluation=report)
    record = agent_record(spec)
    materialize(record, spec, author="manager", note="provisioned", evaluation=None, trusted_provisioning=report)
    assert record.data.evaluation["actor"] == "operator"
    leader_report = trusted_publication(spec, source="system_leader", actor="system", reason="fixed leader")
    with pytest.raises(ValueError):
        materialize(agent_record(spec), spec, author="manager", note="spoof", evaluation=None,
                    trusted_provisioning=leader_report)


def test_builder_publish_cannot_accept_zero_tests_even_when_static_checks_pass():
    spec, report = evaluated_spec()
    spec.tests = []
    item = console.ProposedAgentView(name=spec.name, objective="Coordinate", system_prompt="Safe " * 40,
            selected_tools=[], skill_name="coord", skill_markdown="Coordinate safely " * 4,
            spec=spec.model_dump(mode="json"), evaluation={"checks": {"static": True}, "model_report": report})
    config = ChatModelConfig(type="openai_credential", credential_id="c", model="test", parameters={})
    proposal = console.ProposalView(conversation_id="conversation", proposal_id="proposal", revision=1,
            status="ready", assistant_message="Ready", chat_model_config=config, fixed_config={}, agents=[item])
    message = AssistantMsg(name="builder", content="ready", structured_output={"workforce_builder_proposal": proposal.model_dump(mode="json")})
    storage = SimpleNamespace(get_session=AsyncMock(return_value=object()),
            list_messages=AsyncMock(return_value=([message], False)), claim_builder_publish=AsyncMock(), upsert_agent=AsyncMock())
    async def run():
        with pytest.raises(HTTPException) as exc:
            await console.publish_builder(console.PublishRequest(conversation_id="conversation", proposal_id="proposal",
                                           expected_revision=1), SimpleNamespace(), "u", storage, object())
        assert exc.value.status_code == 409
        storage.claim_builder_publish.assert_not_called(); storage.upsert_agent.assert_not_called()
    asyncio.run(run())


def test_redis_publish_claim_is_durable_across_two_storage_instances():
    import fakeredis.aioredis
    from agentscope.app.storage import RedisStorage
    async def run():
        client = fakeredis.aioredis.FakeRedis(decode_responses=True)
        first, second = RedisStorage(), RedisStorage()
        first._client = second._client = client
        claimed = await asyncio.gather(first.claim_builder_publish("u", "c", "p"),
                                       second.claim_builder_publish("u", "c", "p"))
        assert sorted(claimed) == [False, True]
        assert not await second.claim_builder_publish("u", "c", "p")
        assert await second.claim_builder_publish("another-user", "c", "p")
        await client.aclose()
    asyncio.run(run())


def test_fixed_leader_bootstrap_records_explicit_system_provenance():
    async def run():
        storage = SimpleNamespace(list_agents=AsyncMock(return_value=[]), upsert_agent=AsyncMock())
        session = SimpleNamespace(id="s", config=SimpleNamespace(workspace_id="w"))
        workspace = SimpleNamespace(default_mcps=[])
        manager = SimpleNamespace(get_workspace=AsyncMock(return_value=workspace))
        with patch.object(console, "_model_config", AsyncMock(return_value=object())), \
             patch.object(console, "_primary_session", AsyncMock(return_value=session)):
            leader, _ = await console._leader("u", storage, manager)
        spec = AgentSpec.model_validate(leader.data.spec)
        assert leader.data.evaluation["source"] == "system_leader"
        assert not publication_blocker(spec, leader.data.evaluation, allow_provisioning=True)
        assert publish_blocker(spec, leader.data.evaluation)
    asyncio.run(run())
