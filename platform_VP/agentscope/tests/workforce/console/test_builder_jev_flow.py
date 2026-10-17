"""Vietnamese Builder acceptance cases. All classifiers and generators are scripted.

No provider keys, HTTP requests or paid calls are used. Scores below exercise
application decisions, not the semantic accuracy of the real Jev model.
"""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from agentscope.app._agent_spec import (
    AgentSpec,
    SpecRule,
    SpecTest,
    SpecTool,
    spec_hash,
)
from agentscope.app._router import _builder_flow as flow
from agentscope.app._router import _workforce_console as console
from agentscope.app._service import _builder_decisions as decisions
from agentscope.app._service._agent_studio import materialize
from agentscope.app._service._publish_gate import EVALUATOR, seal_report
from agentscope.app.storage import (
    AgentData,
    AgentRecord,
    AsyncSQLAlchemyStorage,
    ChatModelConfig,
)
from agentscope.classifier import BinaryAnswer, ClassifierResponse, ClassifierUsage
from agentscope.message import AssistantMsg
from fastapi import HTTPException

SCOPE = decisions.BuilderScope(
    owner_id="u", tenant_id="tenant", domain_id="vinhomes", area_id="op2"
)
CONFIG = ChatModelConfig(
    type="openai_credential", credential_id="offline", model="scripted", parameters={}
)
TOOL = console.BuilderTool(
    id="m:get_ticket",
    mcp_id="m",
    mcp_name="vinhomes",
    tool_name="get_ticket",
    description="Đọc trạng thái phiếu kỹ thuật",
    input_schema={"type": "object", "properties": {"id": {"type": "string"}}},
    read_only=True,
    requires_consent=False,
    catalog_revision=1,
)
KNOWLEDGE = {
    "kb": {
        "kb_id": "kb",
        "name": "Nội quy",
        "description": "Quy trình xử lý sự cố",
        "revision": "1",
    }
}
SKILLS = {
    "sk": {
        "skill_id": "sk",
        "name": "tiep-nhan",
        "description": "Tiếp nhận phiếu kỹ thuật",
        "markdown": "# Quy trình\nTra cứu phiếu",
        "revision": "1",
    }
}


def report_for(spec):
    results = [
        {
            "test_id": t.id,
            "passed": True,
            "model_evaluated": True,
            "judge": {"passed": True},
            "checks": [],
            "error": None,
        }
        for t in spec.tests
    ]
    return seal_report(
        spec,
        {
            "spec_hash": spec_hash(spec),
            "evaluator": EVALUATOR,
            "ran_at": datetime.now(UTC).isoformat(),
            "total": len(results),
            "passed": len(results),
            "pass_rate": 1.0,
            "errors": 0,
            "results": results,
        },
    )


def existing(*, agent_id="old", state="published", owner="u", tools=False):
    spec = AgentSpec(
        name="Chuyên viên kỹ thuật",
        goal="Tra cứu tình trạng xử lý sự cố kỹ thuật",
        rules=[SpecRule(text="Không tự ý đóng phiếu", locked=True)],
        tests=[
            SpecTest(
                scenario=f"Cư dân hỏi trạng thái {n}",
                expected="Đọc kết quả đã xác minh",
                safety_critical=n == 0,
            )
            for n in range(3)
        ],
        tools=[
            SpecTool(
                tool_id=TOOL.id,
                mcp_id=TOOL.mcp_id,
                tool_name=TOOL.tool_name,
                read_only=True,
            )
        ]
        if tools
        else [],
    )
    record = AgentRecord(
        id=agent_id,
        user_id=owner,
        data=AgentData(
            name=spec.name,
            context_config=console._FIXED_CONTEXT,
            react_config=console._FIXED_REACT,
            builder_scope=SCOPE.model_dump(),
        ),
    )
    if state == "published":
        materialize(
            record,
            spec,
            author="manager",
            note="Offline fixture",
            evaluation=report_for(spec),
        )
    else:
        record.data.spec = spec.model_dump(mode="json")
        record.data.draft_spec = spec.model_dump(mode="json")
    return record


class ScriptedClassifier:
    def __init__(self, answers=None, failure=None):
        self.answers, self.failure = answers or {}, failure
        self.calls = []
        self.client = SimpleNamespace(aclose=AsyncMock())

    async def __call__(self, *, state, questions):
        self.calls.append((state, questions))
        if self.failure:
            raise self.failure
        return ClassifierResponse(
            model="jev-1.13.0",
            content={k: BinaryAnswer(self.answers.get(k, 0.05)) for k in questions},
            usage=ClassifierUsage(
                input_tokens=120, output_tokens=len(questions), time=0.001
            ),
        )


def classifier(storage, answers=None, failure=None):
    value = decisions.BuilderClassifier(object(), storage, SCOPE, "conversation")
    value.model = ScriptedClassifier(answers, failure)
    value.url = "https://offline.invalid/v1"
    return value


@pytest.fixture
async def storage(tmp_path):
    async with AsyncSQLAlchemyStorage(
        f"sqlite+aiosqlite:///{(tmp_path / 'builder.sqlite').as_posix()}"
    ) as value:
        yield value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "label,same,covers,state,expected",
    [
        ("cùng nghiệp vụ khác cách diễn đạt", 0.95, 0.95, "published", "reuse"),
        (
            "cùng tên nhưng thu phí thay vì xử lý kỹ thuật",
            0.05,
            0.05,
            "published",
            "create",
        ),
        ("thêm năng lực cập nhật phiếu", 0.95, 0.05, "published", "revise"),
        ("agent đang có bản nháp", 0.95, 0.95, "draft", "resume"),
        ("nghiệp vụ còn giao nhau", 0.5, 0.5, "published", "clarify"),
    ],
)
async def test_vietnamese_identity_decisions(
    storage, label, same, covers, state, expected
):
    plans = [console.PlannedAgent(name="Kỹ thuật", objective=label)]
    result = await decisions.decide_identities(
        plans,
        [existing(state=state)],
        classifier(storage, {"same_0_0": same, "covers_0_0": covers}),
    )
    assert result[0].action == expected
    assert result[0].agent_id == (
        "old" if expected in ("reuse", "revise", "resume") else None
    )


@pytest.mark.asyncio
async def test_jev_offline_never_creates_a_clone_and_records_failed_usage(storage):
    value = classifier(storage, failure=TimeoutError())
    result = await decisions.decide_identities(
        [console.PlannedAgent(name="Kỹ thuật", objective="Tra cứu phiếu")],
        [existing()],
        value,
    )
    assert result[0].action == "clarify"
    assert value.status.state == "unavailable"
    rows = await storage.list_model_calls("u", since="2020-01-01T00:00:00+00:00")
    assert rows[0]["status"] == "failed"
    assert rows[0]["cost_usd"] is None
    assert rows[0]["input_tokens"] is None


@pytest.mark.asyncio
async def test_ambiguous_candidates_and_duplicate_plan_entries_need_clarification(
    storage,
):
    plans = [console.PlannedAgent(name="Kỹ thuật", objective="Tra cứu phiếu")]
    result = await decisions.decide_identities(
        plans,
        [existing(agent_id="a"), existing(agent_id="b")],
        classifier(storage, {"same_0_0": 0.95, "same_0_1": 0.95}),
    )
    assert result[0].action == "clarify" and result[0].candidate_ids == ["a", "b"]
    result = await decisions.decide_identities(
        plans * 2, [], classifier(storage, {"pair_1_0": 0.95})
    )
    assert all(d.action == "clarify" for d in result)


def test_scope_filters_owner_domain_area_and_team_agents():
    other_owner = existing(owner="other")
    other_area = existing(agent_id="other-area")
    other_area.data.builder_scope["area_id"] = "op3"
    team = existing(agent_id="team")
    team.source = "team"
    assert [
        r.id
        for r in decisions.scoped_agents(
            [other_owner, existing(), other_area, team], SCOPE
        )
    ] == ["old"]


@pytest.mark.asyncio
async def test_jev_selects_tool_kb_skill_and_reports_missing_operation(storage):
    plans = [
        console.PlannedAgent(
            name="Kỹ thuật",
            objective="Tiếp nhận phiếu kỹ thuật",
            tool_requirements=["Tra cứu phiếu", "Đóng phiếu"],
            knowledge_requirements=["Nội quy xử lý"],
        )
    ]
    value = classifier(
        storage,
        {f"tools:0:0:{TOOL.id}": 0.95, "knowledge:0:0:kb": 0.9, "skills:0:0:sk": 0.95},
    )
    result = await decisions.select_resources(
        plans, flow.resources([TOOL], KNOWLEDGE, SKILLS), value
    )
    assert result == [
        {
            "tools": [TOOL.id],
            "knowledge": ["kb"],
            "skills": ["sk"],
            "missing_tools": ["Đóng phiếu"],
            "missing_knowledge": [],
        }
    ]
    assert value.status.calls == 1 and value.status.questions == 4
    assert value.status.input_tokens == 120 and value.status.latency_ms >= 0
    assert value.status.cost_usd is None


async def planned(
    storage, *, records=(), requirements=(), answers=None, knowledge=None, skills=None
):
    for record in records:
        await storage.upsert_agent("u", record)
    outline = console.BuilderOutline(
        agents=[
            console.PlannedAgent(
                name="Kỹ thuật",
                objective="Tra cứu và xử lý phiếu kỹ thuật",
                tool_requirements=list(requirements),
            )
        ]
    )
    value = classifier(storage, answers)
    with patch.object(flow, "BuilderClassifier", return_value=value):
        return await flow.plan_proposal(
            outline,
            "Cư dân cần tra cứu phiếu kỹ thuật",
            [TOOL],
            knowledge or {},
            skills or {},
            object(),
            object(),
            storage,
            "u",
            "conversation",
            CONFIG,
            SCOPE,
            1,
        )


async def generated(storage, proposal):
    def author(*args):
        return (
            console.BuilderGeneration(
                agents=[
                    console.GeneratedAgent(
                        name="Kỹ thuật",
                        objective="Tra cứu phiếu",
                        system_prompt="Chỉ báo tình trạng phiếu sau khi đọc dữ liệu đã xác minh. "
                        * 3,
                        skill_name="ky-thuat",
                        skill_markdown="# Quy trình\nTra cứu tình trạng phiếu trước khi trả lời cư dân.",
                        tests=[
                            console.GeneratedTest(
                                scenario=f"Tra cứu phiếu {n}",
                                expected="Trả lời theo kết quả tool",
                                safety_critical=n == 0,
                            )
                            for n in range(3)
                        ],
                    )
                ]
            ),
            100,
            100,
        )

    body = console.PrepareRequest(
        message="Đồng ý",
        chat_model_config=CONFIG,
        confirm_outline=True,
        expected_revision=proposal.revision,
        expected_proposal_id=proposal.proposal_id,
    )
    with patch.object(console, "_generate", AsyncMock(side_effect=author)):
        return await flow.generate_proposal(
            proposal,
            body,
            "Đồng ý",
            [TOOL],
            proposal.resource_catalog["knowledge"],
            proposal.resource_catalog["skills"],
            object(),
            storage,
            "u",
            SCOPE,
        )


@pytest.mark.asyncio
async def test_generation_shows_diff_before_saving_and_preserves_same_identity_rules(
    storage,
):
    record = existing()
    proposal = await planned(
        storage, records=[record], answers={"same_0_0": 0.95, "covers_0_0": 0.05}
    )
    result = await generated(storage, proposal)
    assert result.status == "needs_input" and result.agents[0].action == "revise"
    assert result.agents[0].target_agent_id == record.id
    assert result.agents[0].diff
    spec = AgentSpec.model_validate(result.agents[0].spec)
    assert spec.name == record.data.name and spec.rules[0].locked
    assert "Không tự ý đóng phiếu" in spec.prompt_override
    assert len(spec.tests) == 6
    assert (await storage.get_agent("u", record.id)).data.draft_spec is None
    assert len(await storage.list_agents("u")) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    ["tool_schema", "kb_revision", "skill_revision", "agent_revision", "scope"],
)
async def test_stale_resource_or_agent_catalog_blocks_generation(storage, change):
    proposal = await planned(
        storage,
        knowledge=KNOWLEDGE,
        skills=SKILLS,
        answers={"knowledge:0:0:kb": 0.9, "skills:0:0:sk": 0.9},
    )
    tools, knowledge, skills, scope = (
        [TOOL.model_copy(deep=True)],
        {**KNOWLEDGE},
        {**SKILLS},
        SCOPE,
    )
    if change == "tool_schema":
        tools[0].input_schema = {"type": "array"}
    elif change == "kb_revision":
        knowledge = {}
    elif change == "skill_revision":
        skills = {}
    elif change == "agent_revision":
        await storage.upsert_agent("u", existing())
    else:
        scope = SCOPE.model_copy(update={"area_id": "op3"})
    with pytest.raises(HTTPException) as exc:
        await flow.check_plan(
            proposal, 1, tools, knowledge, skills, storage, "u", scope
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_missing_external_operation_blocks_but_optional_knowledge_is_advisory(
    storage,
):
    proposal = await planned(storage, requirements=["Đóng phiếu"], answers={})
    with pytest.raises(HTTPException):
        await flow.check_plan(proposal, 1, [TOOL], {}, {}, storage, "u", SCOPE)
    proposal = await planned(storage)
    proposal.planned_agents[0].missing_knowledge = ["Nội quy tùy chọn"]
    await flow.check_plan(proposal, 1, [TOOL], {}, {}, storage, "u", SCOPE)
    proposal.planned_agents[0].knowledge_required = True
    with pytest.raises(HTTPException):
        await flow.check_plan(proposal, 1, [TOOL], {}, {}, storage, "u", SCOPE)


async def fake_evaluate(item, *args):
    spec = AgentSpec.model_validate(item.spec)
    item.evaluation.update(
        passed=True, model_report=report_for(spec), publish_blocker=""
    )


@pytest.mark.asyncio
async def test_two_conversations_cannot_create_the_same_business_from_one_snapshot(
    storage,
):
    first = await generated(storage, await planned(storage))
    second = first.model_copy(
        deep=True,
        update={"conversation_id": "another-conversation", "proposal_id": "second"},
    )
    with (
        patch.object(
            flow, "current_resources", AsyncMock(return_value=([TOOL], {}, {}))
        ),
        patch.object(console, "_evaluate_proposed_agent", side_effect=fake_evaluate),
    ):
        results = await asyncio.gather(
            flow.evaluate_proposal(first, storage, "u", object(), None),
            flow.evaluate_proposal(second, storage, "u", object(), None),
            return_exceptions=True,
        )
    assert sum(isinstance(r, HTTPException) for r in results) == 1
    assert len(await storage.list_agents("u")) == 1
    assert first.status == "ready" or second.status == "ready"


@pytest.mark.asyncio
async def test_review_eval_publish_appends_version_and_preserves_id(storage):
    record = existing()
    first_version = record.data.versions[0]
    proposal = await generated(
        storage,
        await planned(
            storage, records=[record], answers={"same_0_0": 0.95, "covers_0_0": 0.05}
        ),
    )
    workspace = SimpleNamespace(add_skill_archive=AsyncMock())
    manager = SimpleNamespace(get_workspace=AsyncMock(return_value=workspace))
    session = SimpleNamespace(
        id="primary", config=SimpleNamespace(workspace_id="workspace")
    )
    with (
        patch.object(
            flow, "current_resources", AsyncMock(return_value=([TOOL], {}, {}))
        ),
        patch.object(console, "_evaluate_proposed_agent", side_effect=fake_evaluate),
    ):
        await flow.evaluate_proposal(proposal, storage, "u", object(), None)
        current = await storage.get_agent("u", record.id)
        assert current.data.published_version == 1 and current.data.draft_spec
        msg = AssistantMsg(
            name="builder",
            content="ready",
            structured_output={
                "workforce_builder_proposal": proposal.model_dump(mode="json")
            },
        )
        with (
            patch.object(storage, "get_session", AsyncMock(return_value=session)),
            patch.object(
                console, "_list_all_builder_messages", AsyncMock(return_value=[msg])
            ),
            patch.object(console, "_primary_session", AsyncMock(return_value=session)),
            patch.object(flow, "apply_bindings", AsyncMock()),
        ):
            result = await flow.publish_proposal(
                console.PublishRequest(
                    conversation_id="conversation",
                    proposal_id=proposal.proposal_id,
                    expected_revision=proposal.revision,
                ),
                SimpleNamespace(),
                "u",
                storage,
                manager,
                SCOPE,
            )
    current = await storage.get_agent("u", record.id)
    assert result.agents[0].agent_id == record.id
    assert current.data.published_version == 2 and current.data.draft_spec is None
    assert current.data.versions[0] == first_version
    assert len(await storage.list_agents("u")) == 1


@pytest.mark.asyncio
async def test_all_reused_skips_generation_and_returns_existing_agent_without_writes(
    storage,
):
    record = existing()
    proposal = await planned(
        storage, records=[record], answers={"same_0_0": 0.95, "covers_0_0": 0.95}
    )
    before = (await storage.get_agent("u", record.id)).model_dump()
    with patch.object(
        console,
        "_generate",
        AsyncMock(side_effect=AssertionError("Reuse must not generate")),
    ):
        body = console.PrepareRequest(
            message="Dùng agent cũ",
            chat_model_config=CONFIG,
            expected_revision=1,
            expected_proposal_id=proposal.proposal_id,
        )
        ready = await flow.generate_proposal(
            proposal,
            body,
            "Dùng agent cũ",
            [TOOL],
            {},
            {},
            object(),
            storage,
            "u",
            SCOPE,
        )
    assert ready.status == "ready" and ready.agents[0].reuse_agent_id == record.id
    message = AssistantMsg(
        name="builder",
        content="reuse",
        structured_output={"workforce_builder_proposal": ready.model_dump(mode="json")},
    )
    with (
        patch.object(
            flow, "current_resources", AsyncMock(return_value=([TOOL], {}, {}))
        ),
        patch.object(storage, "get_session", AsyncMock(return_value=object())),
        patch.object(
            console, "_list_all_builder_messages", AsyncMock(return_value=[message])
        ),
    ):
        result = await flow.publish_proposal(
            console.PublishRequest(
                conversation_id="conversation",
                proposal_id=ready.proposal_id,
                expected_revision=ready.revision,
            ),
            SimpleNamespace(),
            "u",
            storage,
            object(),
            SCOPE,
        )
    assert result.agents[0].reused is True
    assert (await storage.get_agent("u", record.id)).model_dump() == before


@pytest.mark.asyncio
async def test_confirm_cannot_regenerate_a_reserved_new_identity(storage):
    proposal = await generated(storage, await planned(storage))
    with (
        patch.object(
            console,
            "_generate",
            AsyncMock(side_effect=AssertionError("No second generation")),
        ),
        pytest.raises(HTTPException) as exc,
    ):
        await generated(storage, proposal)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_library_skill_is_reused_and_generation_cannot_override_grants(storage):
    proposal = await planned(
        storage,
        requirements=["Tra cứu phiếu"],
        skills=SKILLS,
        answers={f"tools:0:0:{TOOL.id}": 0.9, "skills:0:0:sk": 0.95},
    )
    generated_proposal = await generated(storage, proposal)
    item = generated_proposal.agents[0]
    assert [s["skill_id"] for s in item.library_skills] == ["sk"]
    assert item.skill_markdown == ""  # A generated duplicate skill is discarded.
    assert [t.id for t in item.selected_tools] == [TOOL.id]
    assert item.spec["tools"][0]["requires_consent"] is False
    from agentscope.app._agent_spec import render_prompt

    prompt = render_prompt(AgentSpec.model_validate(item.spec))
    assert "BUILDER_LIBRARY_SNAPSHOTS" in prompt and "Tra cứu phiếu" in prompt


@pytest.mark.asyncio
async def test_resource_fallback_is_visible_and_does_not_decide_identity(storage):
    value = classifier(storage, failure=TimeoutError())
    outline = console.BuilderOutline(
        agents=[
            console.PlannedAgent(
                name="Kỹ thuật",
                objective="Tra cứu phiếu",
                tool_requirements=["Tra cứu phiếu"],
            )
        ]
    )
    fallback = [
        {
            "tools": [TOOL.id],
            "knowledge": [],
            "skills": [],
            "missing_tools": [],
            "missing_knowledge": [],
        }
    ]
    with (
        patch.object(flow, "BuilderClassifier", return_value=value),
        patch.object(flow, "llm_resources", AsyncMock(return_value=fallback)),
    ):
        proposal = await flow.plan_proposal(
            outline,
            "Tra cứu phiếu",
            [TOOL],
            {},
            {},
            object(),
            object(),
            storage,
            "u",
            "conversation",
            CONFIG,
            SCOPE,
            1,
        )
    assert proposal.classifier_status.state == "fallback"
    assert proposal.resource_selection == "hybrid"
    assert (
        proposal.planned_agents[0].decision.action == "create"
    )  # Empty scoped catalog is known.


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.1, 1.1, True])
async def test_invalid_classifier_probabilities_cannot_create_duplicates(
    storage, value
):
    result = await decisions.decide_identities(
        [console.PlannedAgent(name="Kỹ thuật", objective="Tra cứu phiếu")],
        [existing()],
        classifier(storage, {"same_0_0": value}),
    )
    assert result[0].action == "clarify"


def test_builder_scope_is_derived_from_authenticated_manager():
    from agentscope.app.auth import AuthPrincipal

    principal = AuthPrincipal(
        user_id="u",
        tenant_id="t",
        domain_id="d",
        area_id="a",
        session_id="s",
        token_id="tok",
    )
    assert console._builder_scope("u", principal).area_id == "a"
    resident = AuthPrincipal(
        user_id="u", tenant_id="t", session_id="s", token_id="tok", role="RESIDENT"
    )
    with pytest.raises(HTTPException) as exc:
        console._builder_scope("u", resident)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_exact_price_snapshot_accounts_for_classifier_calls(storage, monkeypatch):
    from agentscope.app import _model_ledger

    monkeypatch.setattr(
        _model_ledger,
        "price_snapshot",
        lambda call: {
            "input_per_million": 1,
            "cached_input_per_million": 0,
            "output_per_million": 2,
        },
    )
    value = classifier(storage)
    await value.call(
        {"text": "Tra cứu phiếu"},
        {"q": decisions.question("Is this a ticket lookup?")},
        "builder_resources",
    )
    assert value.status.cost_usd == "0.000122"
    rows = await storage.list_model_calls("u", since="2020-01-01T00:00:00+00:00")
    assert rows[0]["cost_complete"] is True
    assert "Tra cứu phiếu" not in str(
        rows
    )  # No prompts/skill bodies/credentials in the ledger.


@pytest.mark.asyncio
async def test_missing_credential_is_explained_and_never_assumed_different(storage):
    access = SimpleNamespace(list_resource=AsyncMock(return_value=[]))
    value = decisions.BuilderClassifier(access, storage, SCOPE, "conversation")
    with patch.object(
        decisions,
        "JevClassifierModel",
        side_effect=AssertionError("No credential should be resolved"),
    ):
        result = await decisions.decide_identities(
            [console.PlannedAgent(name="Kỹ thuật", objective="Tra cứu phiếu")],
            [existing()],
            value,
        )
    assert result[0].action == "clarify"
    assert "TypeSafe credential" in value.status.reason
    assert value.status.calls == 0


@pytest.mark.asyncio
async def test_local_library_skill_installs_its_snapshot_without_remote_hub():
    import io
    import tarfile

    from agentscope.app._router import _workforce_studio as studio
    from agentscope.app.storage import SkillRecord

    skill = SkillRecord(
        user_id="u", name="tiep-nhan", markdown="# Tiếp nhận\nTra cứu phiếu"
    )
    storage = SimpleNamespace(get_skill=AsyncMock(return_value=skill))
    workspace = SimpleNamespace(
        list_skills=AsyncMock(return_value=[]), add_skill_archive=AsyncMock()
    )
    with patch.object(
        studio, "get_skill_hubs", AsyncMock(side_effect=AssertionError("No hub call"))
    ):
        await studio._skill_installer(SimpleNamespace(), storage, "u", "a")(
            workspace, "sk"
        )
    stream = workspace.add_skill_archive.call_args.args[0]
    content = b"".join([chunk async for chunk in stream])
    with tarfile.open(fileobj=io.BytesIO(content), mode="r:*") as archive:
        assert (
            archive.extractfile("tiep-nhan/SKILL.md").read().decode() == skill.markdown
        )
    skill.enabled = False
    with pytest.raises(HTTPException):
        await studio._skill_installer(SimpleNamespace(), storage, "u", "a")(
            workspace, "sk"
        )


@pytest.mark.asyncio
async def test_typesafe_registration_does_not_offer_a_chat_model_or_need_a_key():
    from agentscope.app._router._model import list_models
    from agentscope.app._router._schema import ListModelsRequest
    from agentscope.credential import CredentialFactory, TypeSafeCredential

    assert (
        CredentialFactory.get_credential_class("typesafe_credential")
        is TypeSafeCredential
    )
    result = await list_models(ListModelsRequest(provider="typesafe_credential"))
    assert result.total == 0 and result.models == []


@pytest.mark.asyncio
async def test_sql_catalog_reservation_is_cross_worker_owner_scoped_and_token_bound(
    tmp_path,
):
    url = f"sqlite+aiosqlite:///{(tmp_path / 'race.sqlite').as_posix()}"
    async with (
        AsyncSQLAlchemyStorage(url) as first,
        AsyncSQLAlchemyStorage(url) as second,
    ):
        assert await first.acquire_builder_catalog("u", "first")
        assert not await second.acquire_builder_catalog("u", "second")
        assert await second.acquire_builder_catalog("other", "other")
        await second.release_builder_catalog("u", "wrong-token")
        assert not await second.acquire_builder_catalog("u", "second")
        await first.release_builder_catalog("u", "first")
        assert await second.acquire_builder_catalog("u", "second")


@pytest.mark.asyncio
async def test_redis_catalog_reservation_is_cross_worker_and_token_bound():
    import fakeredis.aioredis
    from agentscope.app.storage import RedisStorage

    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    first, second = RedisStorage(), RedisStorage()
    first._client = second._client = client
    assert await first.acquire_builder_catalog("u", "first")
    await second.release_builder_catalog("u", "wrong")
    assert not await second.acquire_builder_catalog("u", "second")
    await first.release_builder_catalog("u", "first")
    assert await second.acquire_builder_catalog("u", "second")
    await client.aclose()
