import json
from types import SimpleNamespace
import httpx
import pytest
from adapters.backend.errors import AdapterError
from adapters.openbot import SSEDecoder,RunStream,OpenbotAdapter
from config import ServiceConfig,ProviderConfig
from persistence.sqlite import DevelopmentStore
from persistence.budget import Budget
from runtime.service import create_app,Components,REQUIRED
from runtime.model import ProviderModel


def test_sse_every_byte_utf8_crlf_and_multiline():
    wire=': comment\r\ndata: {"type":\r\ndata: "TEXT_MESSAGE_CONTENT", "delta":"rò nước"}\r\n\r\n'.encode()
    decoder=SSEDecoder();events=[]
    for byte in wire: events+=decoder.feed(bytes([byte]))
    events+=decoder.feed(b'',final=True)
    assert events==[{'type':'TEXT_MESSAGE_CONTENT','delta':'rò nước'}]
    with pytest.raises(AdapterError,match='truncated_sse'): SSEDecoder().feed(b'data: {}',final=True)


def test_stream_requires_correlated_complete_tools():
    stream=RunStream('thread','run')
    with pytest.raises(AdapterError,match='correlation'): stream.consume({'type':'RUN_STARTED','threadId':'wrong','runId':'run'})
    stream.consume({'type':'RUN_STARTED','threadId':'thread','runId':'run'})
    stream.consume({'type':'TOOL_CALL_START','toolCallId':'c','toolCallName':'read'})
    stream.consume({'type':'TOOL_CALL_ARGS','toolCallId':'c','delta':'{}'})
    with pytest.raises(AdapterError,match='incomplete_run'): stream.consume({'type':'RUN_FINISHED','threadId':'thread','runId':'run'})
    stream.consume({'type':'TOOL_CALL_END','toolCallId':'c'})
    stream.consume({'type':'RUN_FINISHED','threadId':'thread','runId':'run'})
    assert stream.calls['c']['args']=='{}'
    with pytest.raises(AdapterError,match='late_stream'): stream.consume({'type':'TEXT_MESSAGE_END'})


async def test_service_missing_components_never_acks(monkeypatch):
    monkeypatch.setenv('COORDINATION_INGRESS_TOKEN','x'*32)
    app=create_app(ServiceConfig())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        assert (await client.get('/health')).status_code==200
        assert (await client.get('/ready')).status_code==503
        assert (await client.post('/v2/reception',json={})).status_code==401
        assert (await client.post('/v2/reception',json={},headers={'Authorization':'Bearer '+'x'*32})).status_code==503


async def test_service_ack_requires_actual_durable_accept(tmp_path,monkeypatch):
    monkeypatch.setenv('COORDINATION_INGRESS_TOKEN','x'*32)
    store=DevelopmentStore(tmp_path/'f.sqlite')
    class Ingress:
        async def accept(self,kind,wire,headers):
            await store.accept('event',wire)
            return {'durable':True,'id':'event'}
    async def ready(): return dict.fromkeys(REQUIRED,True)
    components=Components(Ingress(),None,ready,None)  # ASGI test does not run lifespan
    app=create_app(ServiceConfig(),components)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        headers={'Authorization':'Bearer '+'x'*32}
        assert (await client.post('/v2/events',json={'body':1},headers=headers)).status_code==202
        assert (await client.post('/v2/events',json={'body':2},headers=headers)).status_code==409
    claim=await DevelopmentStore(store.path).claim('restarted-worker')
    assert claim.payload=={'body':1}


async def test_real_provider_boundary_reserves_repairs_and_pins_config(tmp_path,monkeypatch):
    monkeypatch.setenv('TEST_MODEL_KEY','never-logged')
    cfg=ProviderConfig(provider='openai-compatible',model='test',base_url='https://model.test/v1',key_env='TEST_MODEL_KEY',
        allowed_models=['test'],timeout=1,output_tokens=100,input_bytes=10000)
    store=DevelopmentStore(tmp_path/'f.sqlite')
    captured=[]
    def response(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200,json={'model':'test','choices':[{'message':{'content':'{"kind":"pause","reason":"checked"}'}}], 'usage':{'total_tokens':30}})
    client=httpx.AsyncClient(transport=httpx.MockTransport(response))
    model=ProviderModel(cfg,Budget(store,scope='run',token_limit=10000),store,client=client)
    for _ in range(2): await model.generate({'schema':{},'data':'rò nước'})
    assert all(c['model']=='test' for c in captured)
    with store.connection() as db:
        assert db.execute('SELECT count(*) FROM ledger').fetchone()[0]==2
        assert all(row[0]==30 for row in db.execute('SELECT used FROM ledger'))
    await model.close()


def test_config_rejects_unauthorized_model_and_dev_override():
    args=dict(provider='openai-compatible',model='forbidden',base_url='https://test/v1',key_env='TEST_KEY',allowed_models=['allowed'],timeout=1,output_tokens=10,input_bytes=100)
    with pytest.raises(ValueError): ProviderConfig(**args)
    args.update(model='allowed',mode='development')
    with pytest.raises(ValueError): ServiceConfig(mode='production',supervisor=ProviderConfig(**args))


async def test_model_restart_cannot_change_run_effective_config(tmp_path,monkeypatch):
    monkeypatch.setenv('TEST_MODEL_KEY','test-credential')
    store=DevelopmentStore(tmp_path/'f.sqlite')
    config=ProviderConfig(provider='openai-compatible',model='a',base_url='https://model.test/v1',key_env='TEST_MODEL_KEY',
        allowed_models=['a','b'],timeout=1,output_tokens=100,input_bytes=10000)
    calls=[]
    def response(request):
        calls.append(request)
        return httpx.Response(200,json={'model':'a','choices':[{'message':{'content':'{"kind":"pause","reason":"x"}'}}]})
    a=ProviderModel(config,Budget(store,scope='run',token_limit=10000),store,client=httpx.AsyncClient(transport=httpx.MockTransport(response)))
    await a.generate({'data':'x'})
    await a.close()
    changed=config.model_copy(update={'model':'b'})
    b=ProviderModel(changed,Budget(store,scope='run',token_limit=10000),store,client=httpx.AsyncClient(transport=httpx.MockTransport(response)))
    with pytest.raises(AdapterError,match='conflict'):await b.generate({'data':'x'})
    assert len(calls)==1
    await b.close()
