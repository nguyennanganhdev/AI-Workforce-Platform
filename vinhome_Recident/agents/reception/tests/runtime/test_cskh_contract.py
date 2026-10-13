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
