"""Replays saved JEV scores, never desired/fabricated verification answers."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from agentscope.app._router import _builder_flow as flow
from agentscope.app._router import _workforce_console as console
from agentscope.app._service import _builder_decisions as decisions
from tests.workforce.console.test_builder_jev_flow import (
    CONFIG, SCOPE, TOOL, classifier, existing, storage,
)


def captured():
    fixture = json.loads((Path(__file__).parent / 'fixtures/jev_identity_c4df.json').read_text(encoding='utf-8'))
    plans = [console.PlannedAgent.model_validate(p) for p in fixture['plans']]
    records = [existing(agent_id=f'agent-{i}') for i in range(8)]
    for record, name in zip(records, fixture['candidate_names']):
        record.data.name = name
    return fixture, plans, records


@pytest.mark.asyncio
async def test_saved_c4df_confirmed_matches_are_not_vetoed_by_weak_relations(storage):
    fixture, plans, records = captured()
    value = classifier(storage, fixture['scores'])
    result = await decisions.decide_identities(plans, records, value)
    assert [v.action for v in result] == ['revise', 'revise', 'revise']
    assert [v.agent_id for v in result] == ['agent-0', 'agent-1', 'agent-1']


@pytest.mark.asyncio
async def test_saved_c4df_combines_capabilities_updating_same_agent_once(storage):
    fixture, plans, records = captured()
    for record in records: await storage.upsert_agent('u', record)
    value = classifier(storage, fixture['scores'])
    async def resources(plans, *_):
        return [dict(tools=[],knowledge=[],skills=[],missing_tools=[],missing_knowledge=[]) for _ in plans]
    with patch.object(flow, 'BuilderClassifier', return_value=value), patch.object(flow, 'select_resources', side_effect=resources):
        proposal = await flow.plan_proposal(console.BuilderOutline(agents=plans), 'Xử lý ticket kỹ thuật', [], {}, {},
            object(), object(), storage, 'u', 'captured-c4df', CONFIG, SCOPE, 1)
    assert len(proposal.planned_agents) == 2
    assert [p.decision.agent_id for p in proposal.planned_agents] == ['agent-0', 'agent-1']
    combined = proposal.planned_agents[1]
    assert 'đổi lịch' in combined.objective.lower()
    assert 'điều phối' in combined.objective.lower()
    assert set(combined.tool_requirements) == set(plans[1].tool_requirements + plans[2].tool_requirements)
    assert len(await storage.list_agents('u')) == 8


@pytest.mark.asyncio
async def test_saved_c4df_shared_reads_and_existing_write_owner_do_not_block_review(storage):
    fixture, plans, records = captured()
    write = TOOL.model_copy(update={'id': 'm:add_note', 'tool_name': 'add_note', 'read_only': False, 'requires_consent': True})
    read_spec = dict(tool_id=TOOL.id, mcp_id='m', tool_name=TOOL.tool_name, read_only=True, requires_consent=False)
    write_spec = dict(tool_id=write.id, mcp_id='m', tool_name=write.tool_name, read_only=False, requires_consent=True)
    records[0].data.spec['tools'] = [read_spec]
    records[1].data.spec['tools'] = [read_spec, write_spec]
    for record in records: await storage.upsert_agent('u', record)
    value = classifier(storage, fixture['scores'])

    async def resources(plans, *_):
        return [dict(tools=[TOOL.id,write.id],knowledge=[],skills=[],missing_tools=[],missing_knowledge=[]),
            dict(tools=[TOOL.id],knowledge=[],skills=[],missing_tools=[],missing_knowledge=[])]

    with patch.object(flow, 'BuilderClassifier', return_value=value), patch.object(flow, 'select_resources', side_effect=resources):
        proposal = await flow.plan_proposal(console.BuilderOutline(agents=plans), 'Xử lý ticket kỹ thuật', [TOOL,write], {}, {},
            object(), object(), storage, 'u', 'captured-c4df', CONFIG, SCOPE, 1)
    assert proposal.clarification_question is None
    assert [[t.id for t in p.suggested_tools] for p in proposal.planned_agents] == [[TOOL.id], [TOOL.id,write.id]]
    assert proposal.planned_agents[0].delegated_tools[0].agent_id == 'agent-1'
    await flow.check_plan(proposal, 1, [TOOL,write], {}, {}, storage, 'u', SCOPE)
    generated = console.BuilderGeneration(agents=[console.GeneratedAgent(
        name=p.name, objective=p.objective, system_prompt='Chỉ trả lời từ kết quả đã xác minh. Phối hợp qua TeamSay khi cần.',
        tests=[console.GeneratedTest(scenario=f'Ca {n}', expected='Giữ đúng phạm vi.', safety_critical=n==0) for n in range(3)],
    ) for p in proposal.planned_agents])
    body = console.PrepareRequest(message='Duyệt', chat_model_config=CONFIG, confirm_outline=True,
        expected_revision=1, expected_proposal_id=proposal.proposal_id)
    with patch.object(console, '_generate', AsyncMock(return_value=(generated,0,0))):
        result = await flow.generate_proposal(proposal, body, 'Duyệt phương án', [TOOL,write], {}, {}, object(), storage, 'u', SCOPE)
    assert len(result.agents) == 2
    assert 'TeamSay' in result.agents[0].spec['prompt_override']
    assert result.agents[0].spec['collaborates'][0]['capability'].endswith('add_note')
    assert write.id not in [t['tool_id'] for t in result.agents[0].spec['tools']]
    assert write.id in [t['tool_id'] for t in result.agents[1].spec['tools']]


@pytest.mark.asyncio
async def test_combining_already_covered_roles_keeps_reuse_without_forcing_eval(storage):
    record = existing()
    plans = [console.PlannedAgent(name='Vai trò', objective=f'Đọc ticket {i}') for i in range(2)]
    choices = [decisions.BuilderDecision(action='reuse', agent_id=record.id) for _ in plans]
    combined, result = flow._combine_updates(plans, choices, [record])
    assert len(combined) == 1 and result[0].action == 'reuse'


@pytest.mark.asyncio
async def test_unconfirmed_candidates_still_block_new_identity(storage):
    value = classifier(storage, {'same_0_0': .57, 'verify_same_0_0': .60, 'verify_distinct_0_0': .30})
    result = await decisions.decide_identities([console.PlannedAgent(name='Nghiệp vụ', objective='Xử lý yêu cầu')], [existing()], value)
    assert result[0].action == 'clarify'


@pytest.mark.asyncio
async def test_two_affirmative_candidates_cannot_be_resolved_by_choosing_highest(storage):
    value = classifier(storage, {'same_0_0': .90, 'same_0_1': .95})
    result = await decisions.decide_identities([console.PlannedAgent(name='Kỹ thuật', objective='Đọc ticket')],
        [existing(agent_id='first'), existing(agent_id='second')], value)
    assert result[0].action == 'clarify'


@pytest.mark.asyncio
async def test_shared_read_requirements_can_be_satisfied_for_both_specialists(storage):
    plans = [console.PlannedAgent(name=f'Vai trò {i}', objective='Đọc thông tin', tool_requirements=['Đọc ticket']) for i in range(2)]
    value = classifier(storage, {f'tools:{i}:0:{TOOL.id}': .95 for i in range(2)})
    result = await decisions.select_resources(plans, flow.resources([TOOL], {}, {}), value)
    assert [r['tools'] for r in result] == [[TOOL.id], [TOOL.id]]
    assert all(not r['missing_tools'] for r in result)
