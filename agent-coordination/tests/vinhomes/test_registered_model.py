import json
import httpx
import pytest
from vinhomes.publish import answer


@pytest.mark.asyncio
async def test_selected_model_uses_its_credential_and_stops_at_write_confirmation():
    requests=[]
    def provider(request):
        body=json.loads(request.content)
        requests.append(body)
        assert request.url==httpx.URL('https://chosen.example/v1/chat/completions')
        assert request.headers['Authorization']=='Bearer chosen-key'
        return httpx.Response(200,json={'model':'chosen-model','choices':[{'message':{'content':None,'tool_calls':[
            {'id':'c1','type':'function','function':{'name':'calendar__create','arguments':'{"title":"Họp"}'}}]}}]})
    calls=[]
    async def invoke(name,args):
        calls.append((name,args))
        return {'status':'AWAITING_CONFIRMATION','data':{'confirmation':{'id':'confirm'}}}
    async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as client:
        said,called=await answer(client,'Chỉ thực hiện thao tác được cấp.',{'name':'case','instruction':'Tạo lịch','ticket':{}},
            [{'name':'calendar__create','description':'Tạo lịch','parameters':{'type':'object'}}],{},
            endpoint='https://unused.example/ag-ui',token='unused',invoke_tool=invoke,
            model_config={'model_name':'chosen-model','provider':'custom','base_url':'https://chosen.example/v1','api_key':'chosen-key'})
    assert requests[0]['model']=='chosen-model' and 'max_tokens' in requests[0]
    assert len(requests)==1 and calls==[('calendar.create',{'title':'Họp'})] and called==['calendar.create']
    assert 'chờ bạn cho phép' in said


@pytest.mark.asyncio
async def test_selected_model_preserves_read_continuation_and_plain_answer():
    requests=[]
    def provider(request):
        body=json.loads(request.content); requests.append(body)
        if len(requests)==1:
            message={'content':None,'tool_calls':[{'id':'c1','type':'function','function':{'name':'reports__read','arguments':'{}'}}]}
        else: message={'content':'Có 17 hóa đơn đã phát hành.'}
        return httpx.Response(200,json={'model':'selected','choices':[{'message':message}]})
    async def invoke(name,args): return {'status':'OK','data':{'invoice_count':17}}
    async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as client:
        said,called=await answer(client,'Dùng số liệu thật.',{'name':'case','instruction':'Có bao nhiêu hóa đơn?','ticket':{}},
            [{'name':'reports__read','description':'Báo cáo','parameters':{'type':'object'}}],{},token='unused',invoke_tool=invoke,
            model_config={'model_name':'selected','provider':'openai','base_url':'https://chosen.example/v1','api_key':'key'})
    assert said=='Có 17 hóa đơn đã phát hành.' and called==['reports.read']
    assert requests[1]['messages'][-1]['role']=='tool' and '17' in requests[1]['messages'][-1]['content']
