"""CSKH context, source provenance and query retry contracts. Offline HTTP/model fixtures only."""
import asyncio
import json

import httpx

from src.agent.prompt import system_prompt
from src.agent.tools import Toolbox, SPECS
from src.agent.loop import run_agent


class Backend:
    def authorization(self,context):return {'Authorization':'Bearer test-delegation'}


def test_service_introduction_uses_only_available_categories_and_capabilities():
    prompt=system_prompt({'name':'Test'},[],None,[{'code':'technical','name':'Technical'},
        {'code':'security','name':'An ninh demo'}])
    facts=json.loads(prompt.split('BỐI CẢNH (từ hệ thống, đáng tin):\n')[1])
    assert [c['name'] for c in facts['danh_muc_dich_vu']]==['Kỹ thuật','An ninh']
    assert len(facts['kha_nang_ung_dung'])==3
    assert 'chỉ gọi file_request khi có nhóm phù hợp' in prompt
    assert 'status=reference' in prompt
    assert len(SPECS)==5


def test_retrying_search_keeps_citations_bound_to_their_original_passages():
    replies=iter(['Nội quy xe','Dịch vụ cư dân'])
    def answer(request):
        title=next(replies)
        return httpx.Response(200,json={'insufficientSources':False,'hits':[
            {'rank':1,'title':title,'text':'Thông tin '+title,'unverified':False,
             'provenance':{'status':'reference','issues':['not_reviewed']}}]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as client:
            box=Toolbox(Backend(),client,'http://api',{'channelId':'test'}, {'id':'test'},None,{'homes':[]},[])
            first=await box.call('search_knowledge',{'query':'câu hỏi dài'})
            second=await box.call('search_knowledge',{'query':'dịch vụ cư dân'})
            a,b=first['passages'][0],second['passages'][0]
            assert a['rank']!=b['rank']
            assert box.passages[a['rank']]['title']=='Nội quy xe'
            assert box.passages[b['rank']]['title']=='Dịch vụ cư dân'
            assert b['provenance']['status']=='reference'
    asyncio.run(run())


def test_reference_information_is_labelled_in_the_resident_reply():
    class Model:
        calls=0
        async def complete(self,messages,tools):
            self.calls+=1
            if self.calls==1:return {'content':None,'tool_calls':[{'id':'read','type':'function',
                'function':{'name':'search_knowledge','arguments':'{"query":"dịch vụ cư dân"}'}}]}
            return {'content':json.dumps({'reply':'Bạn có thể tra cứu thông tin tiện ích trong khu.','sources':[1]},ensure_ascii=False)}
    def answer(request):
        return httpx.Response(200,json={'insufficientSources':False,'hits':[
            {'rank':1,'title':'Dịch vụ cư dân','text':'Thông tin tiện ích trong khu.','unverified':False,
             'provenance':{'status':'reference','issues':['missing_source']}}]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as client:
            box=Toolbox(Backend(),client,'http://api',{'channelId':'test'}, {'id':'test'},None,{'homes':[]},[])
            reply=await run_agent(Model(),box,'system',[{'role':'resident','text':'có dịch vụ gì'}])
            assert 'Nguồn tham khảo: Dịch vụ cư dân' in reply
            assert 'cần xác nhận thông tin hiện hành' in reply
    asyncio.run(run())


def test_http_turn_persists_experience_without_calling_a_provider(monkeypatch,tmp_path):
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from src.runtime import service
    from src.runtime.model import ModelConfig
    saved=[]
    def answer(request):
        assert request.url.path.endswith('/replies')
        saved.append(json.loads(request.content))
        return httpx.Response(201,json={'id':'stored'})
    monkeypatch.setattr(service,'httpx',SimpleNamespace(AsyncClient=lambda: httpx.AsyncClient(transport=httpx.MockTransport(answer))))
    async def wording(backend,client,model,knowledge,context,message,telemetry):
        telemetry['citations']=[{'title':'Nguồn tham khảo','excerpt':'Nội dung.','status':'reference'}]
        return 'Phản hồi kiểm thử.',None
    monkeypatch.setattr(service,'agent_turn',wording)
    settings=service.Settings(backend_url='http://fixture',service_token='s'*32,state_path=str(tmp_path/'unused'),
        agent='loop',model=ModelConfig(model='unused',api_key='none'))
    with TestClient(service.create_app(settings,model=object()),headers={'Authorization':'Bearer '+'s'*32}) as client:
        response=client.post('/v1/turns',json={'user_id':'resident','channel_id':'chat','message':{'id':'message','text':'hello'},
            'delegation':{'token':'fixture','expiresAt':0,'context':{'tenantId':'tenant','runId':'run','bindingId':'channel:chat','principalId':'resident'}}})
    assert response.status_code==200 and response.json()['reply']=='Phản hồi kiểm thử.'
    assert saved[0]['citations'][0]['title']=='Nguồn tham khảo'
    assert saved[0]['latency_ms']>=0 and saved[0]['reply_to_id']=='message'


def test_provider_failure_is_reported_as_failure_even_when_fallback_was_delivered(monkeypatch,tmp_path):
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from src.runtime import service
    from src.runtime.model import ModelConfig
    saved=[]
    def answer(request):
        saved.append(json.loads(request.content))
        return httpx.Response(201,json={'id':'stored'})
    monkeypatch.setattr(service,'httpx',SimpleNamespace(AsyncClient=lambda: httpx.AsyncClient(transport=httpx.MockTransport(answer))))
    async def unavailable(*args):
        raise RuntimeError('synthetic provider failure')
    monkeypatch.setattr(service,'agent_turn',unavailable)
    settings=service.Settings(backend_url='http://fixture',service_token='s'*32,state_path=str(tmp_path/'unused'),
        agent='loop',model=ModelConfig(model='unused',api_key='none'))
    with TestClient(service.create_app(settings,model=object()),headers={'Authorization':'Bearer '+'s'*32}) as client:
        response=client.post('/v1/turns',json={'user_id':'resident','channel_id':'chat','message':{'id':'message','text':'hello'},
            'delegation':{'token':'fixture','expiresAt':0,'context':{'tenantId':'tenant','runId':'run','bindingId':'channel:chat','principalId':'resident'}}})
    assert response.status_code==200
    assert response.json()['status']=='failed' and response.json()['error_code']=='RECEPTION_TURN_FAILED'
    assert len(saved)==1 and saved[0]['text']==service.FAILED_REPLY
