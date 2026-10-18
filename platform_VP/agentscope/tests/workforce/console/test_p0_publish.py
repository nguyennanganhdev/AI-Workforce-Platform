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
