"""Session regressions reproduced without a provider or model credential."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest

from agentscope.app._service._model import runtime_model_config
from agentscope.app._shared_context import SharedContextService
from agentscope.app.storage import ChatModelConfig


def test_luna_policy_overrides_every_purpose_without_expensive_fallback(monkeypatch):
    monkeypatch.setenv("WORKFORCE_MODEL_NAME", "gpt-6-luna")
    original = ChatModelConfig(type="openai_credential", credential_id="stored",
        model="gpt-5.5", parameters={"max_tokens": 32000, "reasoning_effort": "high", "temperature": 0.7})
    selected = runtime_model_config(original)
    assert selected.model == "gpt-6-luna"
    assert selected.parameters["max_tokens"] == 16384
    # Reasoning stays on (agent effort); get_model drops it on Chat Completions.
    assert selected.parameters["reasoning_effort"] == "low"
    assert selected.parameters["thinking_enable"] is True
    assert "temperature" not in selected.parameters
    assert original.model == "gpt-5.5"


def test_partner_snapshot_projection_replaces_old_versions_keeps_evidence():
    items=[]
    for version in range(1,31):
        result={"ticket_id":"ticket-1","ticket_version":version,"snapshot_seq":version,
            "ticket_status":"assigned","staff_name":"Trần Bình"}
        items.append({"id":f"item-{version}","task_id":"task","kind":"fact",
            "authority":"tool_verified","source_event_ids":[f"event-{version}"],
            "text":json.dumps({"state":"success","tool_call":{"name":"vh_ticket_get","input":'{"ticket_id":"ticket-1"}'},
                "tool_result":{"metadata":{"external_evidence":True},"output":[{"type":"text","text":f'E{version}: '+json.dumps(result,ensure_ascii=False)}]}})})
    original=json.dumps(items)
    projected=SharedContextService._compact_tool_facts(items)
    assert len(projected)==1
    assert 'E30' in projected[0]['text']
    assert projected[0]['source_event_ids']==['event-30']
    assert len(projected[0]['superseded_source_event_ids'])==29
    assert json.dumps(items)==original
    stale=json.loads(items[-1]['text'])
    stale['tool_result']['output'][0]['text']='E99: '+json.dumps({"ticket_id":"ticket-1","ticket_version":30,"snapshot_seq":1,"ticket_status":"open"})
    projected=SharedContextService._compact_tool_facts([*items,{**items[-1],"id":"stale","text":json.dumps(stale),"source_event_ids":["stale"]}])
    assert 'E30' in projected[0]['text']
    assert 'E99' not in projected[0]['text']


def test_partner_snapshot_null_cursor_is_the_same_full_read():
    items = []
    for version, arguments in ((1, {"ticket_id": "T1"}),
                               (2, {"ticket_id": "T1", "history_before_seq": None}),
                               (3, {"ticket_id": "T1", "history_before_seq": 7})):
        value = {"ticket_id": "T1", "ticket_version": version, "snapshot_seq": version}
        items.append({"id": f"item-{version}", "task_id": "task", "kind": "fact",
            "authority": "tool_verified", "source_event_ids": [f"event-{version}"],
            "text": json.dumps({"state": "success", "tool_call": {"name": "vh_ticket_get",
                "input": json.dumps(arguments)}, "tool_result": {"metadata": {"external_evidence": True},
                "output": [{"type": "text", "text": f"E{version}: " + json.dumps(value)}]}})})
    projected = SharedContextService._compact_tool_facts(items)
    assert len(projected) == 2  # The historical page must remain separate.
    assert projected[0]['source_event_ids'] == ['event-2']
    assert projected[0]['superseded_source_event_ids'] == ['event-1']
    assert projected[1]['source_event_ids'] == ['event-3']


@pytest.mark.asyncio
async def test_handoff_represented_by_current_review_ledger_is_not_repeated():
    from team_shared_context_test import _Storage
    from agentscope.app.message_bus import InMemoryMessageBus
    storage = _Storage()
    service = SharedContextService(storage, InMemoryMessageBus())
    customer = await service.append_event(user_id='u', team_id='t', kind='customer_message', content='Check result')
    handoff = await service.append_event(user_id='u', team_id='t', kind='handoff', content='Read E22 before replying')
    record = await storage.get_team_shared_context('u', 't')
    task = record.state.tasks[customer.task_id]
    service._branch(task, 'worker').reason = handoff.content
    packet = service._packet_value(record, record.state.events, mode='task', task_id=customer.task_id)
    assert handoff.id not in [e['id'] for e in packet['recent_events']]
    assert packet['authoritative_state']['tasks'][0]['collaboration']['worker']['reason'] == handoff.content
    assert len(record.state.events) == 2
    service._branch(task, 'worker').reason = 'A different instruction'
    packet = service._packet_value(record, record.state.events, mode='task', task_id=customer.task_id)
    assert handoff.id in [e['id'] for e in packet['recent_events']]


@pytest.mark.asyncio
async def test_management_middleware_has_read_tools_and_no_resident_delivery():
    from agentscope.app.workforce.integrations.unified._case import ManagementCaseMiddleware
    read=SimpleNamespace(name="vh_ticket_get",is_read_only=True)
    write=SimpleNamespace(name="vh_work_order_dispatch",is_read_only=False)
    middleware=ManagementCaseMiddleware([read,write])
    assert [t.name for t in await middleware.list_tools()]==['vh_ticket_get']
    handler=AsyncMock(return_value='reply')
    schemas=[{'type':'function','function':{'name':name}} for name in ['vh_ticket_get','vh_work_order_dispatch','CaseSay','CaseFinalize','TeamSay']]
    await middleware.on_model_call(SimpleNamespace(),{'tools':schemas,'messages':[]},handler)
    assert [s['function']['name'] for s in handler.call_args.kwargs['tools']]==['vh_ticket_get']
    handler.reset_mock()
    denied=await middleware.on_check_permission(None,{'tool_call':SimpleNamespace(name='vh_work_order_dispatch')},handler)
    assert denied.behavior.value=='deny'
    handler.assert_not_called()


def test_internal_agent_role_is_not_a_staff_claim():
    from agentscope.app._evidence_claims import unsupported_claim_anchors
    assert unsupported_claim_anchors('Agent Kỹ thuật cần kiểm tra.', []) == ()
    assert 'name:trần bình' in unsupported_claim_anchors('Đã giao cho Trần Bình.', [])


@pytest.mark.asyncio
@pytest.mark.parametrize("mention,target", [("@Worker ", "worker"), ("", "leader")])
async def test_manager_console_does_not_answer_or_approve_as_resident(mention, target):
    from team_say_shared_context_test import _Storage
    from agentscope.app._router._chat import chat
    from agentscope.app._router._schema import ChatRequest
    from agentscope.app._service._access import ResourceAccessService
    from agentscope.app._team_turn import start_team_turn, get_team_turn
    from agentscope.app.message_bus import InMemoryMessageBus, MessageBusKeys
    from agentscope.app.storage import SessionRecord
    from agentscope.message import UserMsg

    storage = _Storage()
    source = storage.sessions['leader-session']
    source.state.middle_context.update(workflow_id='workflow',partner_agent_versions={'worker':7})
    storage.upsert_message = AsyncMock()
    async def upsert_session(**kw):
        record=SessionRecord(id=kw['session_id'],user_id=kw['user_id'],agent_id=kw['agent_id'],config=kw['config'],state=kw['state'])
        storage.sessions[record.id]=record
        return record
    storage.upsert_session=upsert_session
    bus=InMemoryMessageBus()
    before=await start_team_turn(bus,'ticket-1',reply_owner_session_id='leader-session',reply_owner_agent_id='leader',customer_session_id='leader-session',mode='leader')
    registry=SimpleNamespace(get=lambda _:None,spawn=lambda coro,**_:queued.append(coro))
    queued=[]
    async def run(**kwargs):
        assert await bus.is_locked(MessageBusKeys.session_lock('leader-session'))
    service=SimpleNamespace(run=AsyncMock(side_effect=run))
    request=ChatRequest(agent_id='leader',session_id='leader-session',input=UserMsg(name='user',content=mention+'Xác nhận'))
    with patch('agentscope.app._router._chat.pending_chat_actions',side_effect=AssertionError('BQL must not grant resident consent')):
        await chat(request,user_id='u',chat_service=service,chat_run_registry=registry,message_bus=bus,storage=storage,shared_context_storage=storage,
                   resource_access_service=ResourceAccessService(storage, None))
        await queued[0]
    call=service.run.call_args.kwargs
    manager=storage.sessions[call['session_id']]
    assert call['agent_id']==target
    assert manager.team_id is None
    assert manager.state.middle_context['management_case_session_id']=='leader-session'
    assert call['input_msg'].metadata['actor']=='management'
    assert (await get_team_turn(bus,'ticket-1')).turn_id==before.turn_id


@pytest.mark.asyncio
async def test_shared_packet_indexes_partner_history_without_model_call():
    from team_shared_context_test import _Storage, _MeasuredModel
    from agentscope.app._shared_context import SharedContextConfig
    from agentscope.app.message_bus import InMemoryMessageBus
    from agentscope.app.storage import ContextDelta
    storage=_Storage()
    service=SharedContextService(storage,InMemoryMessageBus(),config=SharedContextConfig(packet_max_tokens=4000,history_budget_tokens=500))
    model=_MeasuredModel(fail_summary=True)
    for index in range(12):
        fact=f'vh_ticket_get {{"ticket_id":"T1"}}\nE{index+1}: '+('exact business evidence ' * 20)
        await service.append_event(user_id='u',team_id='t',kind='external_event',content=fact,delta=ContextDelta(add_confirmed_facts=(fact,)))
    packet,tokens=await service.prepare_packet(model=model,user_id='u',team_id='t')
    after=await storage.get_team_shared_context('u','t')
    assert tokens<=4000
    assert model.summary_calls==0
    assert len(after.state.events)==12
    assert 'Raw sources' in packet
    assert after.state.metrics.compactions==1


@pytest.mark.asyncio
async def test_partner_input_uses_current_turn_and_durable_packet_preserves_transcript():
    from team_shared_context_test import _Storage, _MeasuredModel
    from agentscope.app.message_bus import InMemoryMessageBus
    from agentscope.app.middleware import SharedContextIsolationMiddleware
    from agentscope.message import AssistantMsg, UserMsg, SystemMsg
    from agentscope.state import AgentState
    history=[UserMsg(name='customer',content='OLD_PAYLOAD ' * 10000)]
    current=UserMsg(name='customer',content='Latest resident request')
    reply=AssistantMsg(name='Leader',content='Verified current result')
    state=AgentState(session_id='s',context=[*history,current,reply])
    middleware=SharedContextIsolationMiddleware('task',SharedContextService(_Storage(),InMemoryMessageBus()),'u',None,
        prior_context=history,packet_attachment='Durable facts and summary',project_private_history=True)
    captured=AsyncMock(return_value=SimpleNamespace(usage=None))
    await middleware.on_model_call(SimpleNamespace(state=state,name='Leader'),{
        'messages':[SystemMsg(name='policy',content='Policy'),*state.context],
        'tools':[],'current_model':_MeasuredModel()},captured)
    sent=' '.join(m.get_text_content() for m in captured.call_args.kwargs['messages'])
    assert 'OLD_PAYLOAD' not in sent
    assert 'Latest resident request' in sent
    assert 'Durable facts and summary' in sent
    assert state.context[0].get_text_content()==history[0].get_text_content()


@pytest.mark.asyncio
async def test_late_leader_wakeup_never_calls_model_or_resident_delivery():
    from agentscope.app.workforce.integrations.unified._case import PartnerCaseMiddleware
    case=SimpleNamespace(trigger_id=AsyncMock(return_value='unknown'))
    middleware=PartnerCaseMiddleware(case,[])
    model=AsyncMock()
    response=await middleware.on_model_call(None,{'tools':[],'messages':[]},model)
    model.assert_not_called()
    assert response.content


@pytest.mark.asyncio
async def test_luna_tool_call_wire_format_with_local_transport_only(monkeypatch):
    import httpx
    from agentscope.credential import OpenAICredential
    from agentscope.model import OpenAIChatModel
    from agentscope.message import UserMsg
    monkeypatch.setenv('WORKFORCE_MODEL_NAME','gpt-6-luna')
    config=runtime_model_config(ChatModelConfig(type='openai_credential',credential_id='unused',model='old',parameters={}))
    requests=[]
    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200,json={'id':'offline','object':'chat.completion','created':1,'model':'gpt-6-luna',
            'choices':[{'index':0,'finish_reason':'tool_calls','message':{'role':'assistant','content':None,'tool_calls':[
                {'id':'local-call','type':'function','function':{'name':'TeamSay','arguments':'{"kind":"question","to":"Peer","content":"Verify evidence"}'}}]}}],
            'usage':{'prompt_tokens':10,'completion_tokens':4,'total_tokens':14}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        model=OpenAIChatModel(credential=OpenAICredential(api_key='offline-placeholder',base_url='https://offline.invalid/v1'),
            model=config.model,parameters=OpenAIChatModel.Parameters(**config.parameters),stream=False,
            client_kwargs={'http_client':client})
        response=await model(messages=[UserMsg(name='worker',content='Ask peer')],tools=[{
            'type':'function','function':{'name':'TeamSay','description':'Internal coordination','parameters':{'type':'object','properties':{}}}}])
    assert requests[0]['model']=='gpt-6-luna'
    # The policy asks for reasoning; Chat Completions with tools sends none.
    assert config.parameters['reasoning_effort']=='low'
    assert requests[0]['reasoning_effort']=='none'
    assert requests[0]['max_completion_tokens']==16384
    assert response.content[0].name=='TeamSay'
