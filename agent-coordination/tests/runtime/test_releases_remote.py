import json
from pathlib import Path
from types import SimpleNamespace
import httpx
import pytest
from agents.releases import ReleaseConsumer,ReleasedSession
from adapters.openbot import OpenbotAdapter
from adapters.agentscope_remote import AgentScopeRemoteAdapter
from adapters.backend.errors import AdapterError
from groupchat.models import AgentOutput,Participant
from groupchat.ports import Invocation
from persistence.sqlite import DevelopmentStore
from persistence.budget import Budget
from support.fakes import make_context


def invocation(ticket='TEST-1'):
    ctx=make_context(ticket)
    p=Participant(agent_version_id='technical-v1',role='advisor',platform_agent_id='a',member_id='member-'+ticket,
        binding_id='bind-'+ticket,binding_generation=1,framework_agent_id='technical',framework_reference='ref-'+ticket)
    return Invocation('op-'+ticket,1,ctx,'room-'+ticket,p,'child-'+ticket,(),'Kiểm tra dữ kiện',groupchat_version_id='group-v1')


def release(i):
    return dict(tenant_id=i.context.tenant_id,workspace_id=i.context.workspace_id,ticket_id=i.context.ticket_id,
        ticket_generation=i.context.ticket_generation,groupchat_version_id='group-v1',agent_version_id=i.participant.agent_version_id,
        member_id=i.participant.member_id,binding_id=i.participant.binding_id,binding_generation=i.participant.binding_generation,framework_reference=i.participant.framework_reference,
        source_run_id=i.source_run_id,thread_id='thread-'+i.context.ticket_id,evaluated=True,admin_approved=True,published=True,revoked=False,
        prompt_hash='prompt-v1',config_hash='cfg-v1',knowledge_grants=[],capabilities=['technical'],model='allowed',
        runtime='openbot-chat-completions',endpoint='https://bot.test/ag-ui',credential_env='TEST_BOT_KEY',
        tool_descriptors=[{'name':'read','description':'read authorized facts','parameters':{'type':'object','properties':{},'additionalProperties':False}}],output_tokens=100)


class Producer:
    def __init__(self): self.revoked=False;self.hash='cfg-v1'
    async def resolve_released_session(self,i):
        r=release(i);r['revoked']=self.revoked;r['config_hash']=self.hash
        return r


async def test_pin_isolation_new_run_rollback_and_revoke(tmp_path):
    store=DevelopmentStore(tmp_path/'f.sqlite');producer=Producer();loader=ReleaseConsumer(producer,store)
    a,b=invocation(),invocation('TEST-2')
    ar,br=await loader.for_invocation(a),await loader.for_invocation(b)
    assert ar.thread_id!=br.thread_id
    wrong=ReleasedSession.model_validate(release(a))
    with pytest.raises(AdapterError,match='scope_mismatch'): wrong.validate(b)
    producer.hash='rollback-v0'
    with pytest.raises(AdapterError,match='pin_changed'): await loader.for_invocation(a)
    c=invocation('NEW')
    assert (await loader.for_invocation(c)).config_hash=='rollback-v0'
    producer.revoked=True
    with pytest.raises(ValueError): await loader.for_invocation(c)
    with pytest.raises(ValueError): ReleasedSession.model_validate(release(a)|{'published':False})
    with pytest.raises(ValueError): ReleasedSession.model_validate(release(a)|{'model':'gpt-5.6-luna'})


async def test_remote_tool_continuation_sdk_wrapper_and_saved_result(tmp_path,monkeypatch):
    monkeypatch.setenv('TEST_BOT_KEY','test-secret')
    store=DevelopmentStore(tmp_path/'f.sqlite');loader=ReleaseConsumer(Producer(),store);requests=[];tools=[]
    def handler(request):
        wire=json.loads(request.content);requests.append(wire)
        common={'threadId':wire['threadId'],'runId':wire['runId']}
        events=[{'type':'RUN_STARTED',**common}]
        if len(requests)==1:
            events += [{'type':'TOOL_CALL_START','toolCallId':'call','toolCallName':'read'},
                {'type':'TOOL_CALL_ARGS','toolCallId':'call','delta':'{}'},{'type':'TOOL_CALL_END','toolCallId':'call'}]
        else:
            assert wire['messages'][-1]['role']=='tool'
            assert wire['messages'][-1]['toolCallId']=='call'
            events += [{'type':'TEXT_MESSAGE_START','messageId':'message','role':'assistant'},
                {'type':'TEXT_MESSAGE_CONTENT','messageId':'message','delta':'{"content":"Đề xuất từ facts","follow_up_requests":[]}'},
                {'type':'TEXT_MESSAGE_END','messageId':'message'}]
        events.append({'type':'RUN_FINISHED',**common})
        return httpx.Response(200,headers={'content-type':'text/event-stream'},content=''.join('data: '+json.dumps(e,ensure_ascii=False)+'\n\n' for e in events).encode())
    class Tools:
        async def execute_authorized(self,i,r,name,args,op,run,call):
            tools.append(op)
            return {'operation_id':op,'run_id':run,'call_id':call,'result':{'fact':None}}
    adapter=OpenbotAdapter(loader,store,Tools(),Budget(store,scope='remote',token_limit=20000),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    sdk=AgentScopeRemoteAdapter(adapter);i=invocation()
    await sdk.prepare(i)
    output=await sdk.invoke(i)
    assert output.content=='Đề xuất từ facts'
    assert len(requests)==2 and len(tools)==1
    assert await sdk.invoke(i)==output and len(requests)==2
    assert not await sdk.cancel(i)  # transport disconnect cannot assert business cancellation
    await adapter.close()


async def test_remote_apply_then_lost_response_blocks_replay(tmp_path,monkeypatch):
    monkeypatch.setenv('TEST_BOT_KEY','test-secret')
    store=DevelopmentStore(tmp_path/'f.sqlite');requests=[]
    def handler(request):
        requests.append(request)
        raise httpx.ReadTimeout('test lost after remote accepted',request=request)
    def adapter():
        return OpenbotAdapter(ReleaseConsumer(Producer(),DevelopmentStore(store.path)),store,None,
            Budget(store,scope='remote',token_limit=20000),client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    a=adapter()
    with pytest.raises(httpx.ReadTimeout): await a.invoke(invocation())
    await a.close()
    b=adapter()
    with pytest.raises(AdapterError,match='outcome_unknown'): await b.invoke(invocation())
    assert len(requests)==1
    assert not await b.cancel(invocation())
    await b.close()


async def test_takeover_fence_cannot_restart_unknown_remote_call(tmp_path,monkeypatch):
    from dataclasses import replace
    monkeypatch.setenv('TEST_BOT_KEY','test-secret')
    store=DevelopmentStore(tmp_path/'f.sqlite');requests=[]
    def handler(request):requests.append(request);raise httpx.ReadTimeout('lost',request=request)
    adapter=OpenbotAdapter(ReleaseConsumer(Producer(),store),store,None,
        Budget(store,scope='remote',token_limit=20000),client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    i=invocation()
    with pytest.raises(httpx.ReadTimeout):await adapter.invoke(i)
    with pytest.raises(AdapterError,match='outcome_unknown'):await adapter.invoke(replace(i,fence=2))
    with pytest.raises(AdapterError,match='conflict'):await adapter.invoke(replace(i,fence=2,instruction='different body'))
    assert len(requests)==1
    await adapter.close()


async def test_revoke_during_stream_blocks_result_persistence(tmp_path,monkeypatch):
    monkeypatch.setenv('TEST_BOT_KEY','test-secret')
    store=DevelopmentStore(tmp_path/'f.sqlite');producer=Producer()
    def response(request):
        wire=json.loads(request.content)
        common={'threadId':wire['threadId'],'runId':wire['runId']}
        events=[{'type':'RUN_STARTED',**common},{'type':'TEXT_MESSAGE_START','messageId':'m','role':'assistant'},
                {'type':'TEXT_MESSAGE_CONTENT','messageId':'m','delta':'{"content":"late"}'},
                {'type':'TEXT_MESSAGE_END','messageId':'m'},{'type':'RUN_FINISHED',**common}]
        producer.revoked=True
        return httpx.Response(200,headers={'content-type':'text/event-stream'},content=''.join('data: '+json.dumps(e)+'\n\n' for e in events))
    adapter=OpenbotAdapter(ReleaseConsumer(producer,store),store,None,Budget(store,scope='remote',token_limit=20000),
        client=httpx.AsyncClient(transport=httpx.MockTransport(response)))
    with pytest.raises(ValueError):await adapter.invoke(invocation())
    with store.connection() as db:assert db.execute("SELECT count(*) FROM records WHERE namespace='remote_result'").fetchone()[0]==0
    await adapter.close()
