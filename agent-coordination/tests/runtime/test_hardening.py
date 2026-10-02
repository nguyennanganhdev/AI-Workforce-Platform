"""Fault injection through real composition/file store; producers remain doubles."""
import asyncio
import hashlib
import json
from contextlib import asynccontextmanager
from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest
from adapters.backend.errors import AdapterError
from adapters.backend.events import ResolvedEvent
from adapters.backend.messages import fingerprint
from config import ProviderConfig,ServiceConfig
from persistence.budget import Budget
from persistence.sqlite import DevelopmentStore
from runtime.composition import build
from runtime.download import BoundedHTTPDownload
from runtime.model import ProviderModel
from runtime.reporting import ReportArtifacts
from runtime.service import create_app,REQUIRED
from supervisor.models import SupervisorState,AuthorityView
from support.fakes import make_context
from tests.runtime.test_workflows import bindings,command,Reports,prepare_export,REPO
from tests.runtime.test_contributions_reports import contribution
from tests.runtime.test_releases_remote import invocation,Producer
from agents.releases import ReleaseConsumer
from adapters.openbot import OpenbotAdapter


async def work_composition(tmp_path,now,*,policy_none=False):
    b,store,auth,staff=await bindings(tmp_path,now=now)
    ctx=make_context()
    class Verifier:
        async def resolve(self,event,authentication):
            if authentication!='verified-source':raise AdapterError('event_not_authorized')
            return ResolvedEvent(ctx.model_dump(mode='json',exclude_none=True))
    class Validator:
        def validate(self,*args):pass # explicit unfrozen producer schema double
    class Authority:
        async def inspect(self,state):return AuthorityView(context=ctx,state_version=state.version)
    b.event_verifier=Verifier();b.backend_client.validator=Validator();b.authority=Authority()
    b.event_types={'test.work.completed':'work.completed'}
    event=dict(event_id='work-event',event_type='test.work.completed',schema_version='1',tenant_id=ctx.tenant_id,
        aggregate_id='work',aggregate_version=1,occurred_at='2026-10-02T00:00:00+07:00',correlation_id='corr',causation_id='cause',
        payload=dict(assignment_id='assigned',assignment_version=1,result_id='result',result_version=1,summary='Verified work',
                     before_file_ids=['before'],after_file_ids=['after']))
    # This crash/replay fixture represents a verified work already checkpointed
    # and subsequently completed through Backend QC. Replay must not reopen it.
    state=SupervisorState(context=ctx,groupchat_version_id='group-v1',turn_policy={},phase='completed',
        result=event['payload'],events={event['event_id']:fingerprint(event)},aggregate_versions={'work':1})
    await store.commit(state,None)
    raw=command('contribution',dict(operation='request',staff_id='staff',task_id='task',work_order_id='work',
        requested_fields=['procedure','actual_cost'],message='Xác nhận sau work'),identity='stable-request')
    staff.policy_calls=0;staff.request_calls=0;staff.request_receipt=None;staff.lost_request=False
    async def policy(*args):staff.policy_calls+=1;return None if policy_none else raw
    async def request(cmd,proof):
        staff.request_calls+=1
        staff.request_receipt={'request_id':'request','payload_hash':proof['payload_hash'],'status':'requested'}
        if staff.lost_request:raise TimeoutError('after remote apply')
        return staff.request_receipt
    async def reconcile(*args):return staff.request_receipt
    staff.staff_request_for_work=policy;staff.request_staff_contribution=request;staff.reconcile_staff_request=reconcile
    return b,store,staff,event


@pytest.mark.parametrize('window',['before_decision','before_ack','none'])
async def test_work_event_crash_replay_intent_and_ack(tmp_path,window):
    now=[100.];b,store,staff,event=await work_composition(tmp_path,now,policy_none=window=='none');c=build(b)
    with pytest.raises(AdapterError):await c.ingress.accept('event',event,'forged')
    await c.ingress.accept('event',event,'verified-source')
    put=store.put_once;ack=store.ack;failed=False
    async def fault_put(namespace,*args):
        nonlocal failed
        if window=='before_decision' and namespace=='staff_work_decision' and not failed:
            failed=True;raise RuntimeError('before durable intent')
        return await put(namespace,*args)
    async def fault_ack(claim):
        nonlocal failed
        if window in ('before_ack','none') and claim.payload['kind']=='event' and not failed:
            failed=True;raise RuntimeError('before inbox ACK')
        return await ack(claim)
    store.put_once=fault_put;store.ack=fault_ack
    with pytest.raises(RuntimeError):await c.worker.once()
    with store.connection() as db:
        assert db.execute("SELECT status FROM inbox WHERE key LIKE '%event%'").fetchone()==('pending',)
        count=db.execute("SELECT count(*) FROM inbox WHERE key LIKE '%contribution%'").fetchone()[0]
        assert count==(1 if window=='before_ack' else 0)
        assert db.execute('SELECT count(*) FROM acknowledgements').fetchone()[0]==0
    now[0]+=6
    assert await c.worker.once() # verified work replay, enqueue before ACK
    if window!='none':assert await c.worker.once()
    assert not await c.worker.once()
    assert staff.request_calls==(0 if window=='none' else 1)
    with store.connection() as db:
        assert db.execute('SELECT tenant,id FROM acknowledgements').fetchall()==[(make_context().tenant_id,event['event_id'])]
    assert staff.policy_calls==(2 if window=='before_decision' else 1)
    assert (await store.load(make_context())).phase=='completed'
    if window=='none':
        assert staff.request_receipt is None
    else:
        submit=command('contribution',{'operation':'submit','contribution':contribution()},identity='staff-submit')
        await c.ingress.accept('contribution',submit,'verified-source');await c.worker.once()
        status=command('contribution',{'operation':'status','contribution_id':'c1','revision':1},identity='status')
        assert (await c.workflows.execute('contribution',status,'verified-source',fence=1))['status']=='review_pending'
        staff.status_value='changes_requested';staff.status_version=2
        status['message_id']='correction-status'
        assert (await c.workflows.execute('contribution',status,'verified-source',fence=1))['status']=='changes_requested'
        corrected=command('contribution',{'operation':'submit','contribution':contribution()|{'revision':2}},identity='corrected')
        await c.ingress.accept('contribution',corrected,'verified-source');await c.worker.once()
        assert (await store.load(make_context())).phase=='completed'
    await c.close()


async def test_d07_remote_apply_lost_receipt_and_two_composed_workers(tmp_path):
    now=[100.];b,store,staff,event=await work_composition(tmp_path,now);c=build(b)
    await c.ingress.accept('event',event,'verified-source');await c.worker.once()
    staff.lost_request=True
    started=asyncio.Event();finish=asyncio.Event();original=staff.request_staff_contribution
    async def delayed(*args):started.set();await finish.wait();return await original(*args)
    staff.request_staff_contribution=delayed
    first=asyncio.create_task(c.worker.once());await started.wait()
    other=build(b);assert not await other.worker.once()
    finish.set()
    with pytest.raises(TimeoutError):await first
    now[0]+=6
    assert await other.worker.once() # remote receipt reconciliation, same command
    assert staff.request_calls==1
    await c.close();await other.close()


async def test_lost_lease_during_d07_remote_apply_no_late_write_takeover_reconciles(tmp_path):
    now=[100.];b,store,staff,event=await work_composition(tmp_path,now);c=build(b)
    await c.ingress.accept('event',event,'verified-source');await c.worker.once()
    applied=asyncio.Event();finish=asyncio.Event();original=staff.request_staff_contribution
    async def delayed(*args):
        receipt=await original(*args);applied.set();await finish.wait();return receipt
    staff.request_staff_contribution=delayed
    first=asyncio.create_task(c.worker.once());await applied.wait();now[0]+=31
    takeover=await store.claim('takeover');assert takeover.fence==2
    finish.set()
    with pytest.raises(AdapterError,match='stale_fence'):await first
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM records WHERE namespace='staff_request_receipt'").fetchone()[0]==0
    await store.release(takeover)
    assert await c.worker.once();assert staff.request_calls==1
    await c.close()


async def test_expired_lease_cannot_enqueue_or_commit_room(tmp_path):
    now=[100.];store=DevelopmentStore(tmp_path/'f.sqlite',clock=lambda:now[0]);await store.accept('job',{})
    claim=await store.claim('w',1)
    with store.lease_scope(claim):
        now[0]+=2
        with pytest.raises(AdapterError,match='stale_fence'):await store.accept('late',{})
        with pytest.raises(AdapterError,match='stale_fence'):await store.renew(claim)
    assert await store.claim('takeover')


async def test_report_download_request_hash_size_mid_fetch_and_close_revoke(tmp_path):
    reports=Reports(make_context());b,store,_,_=await bindings(tmp_path,reports=reports);c=build(b)
    await prepare_export(c.workflows.reports,'owner')
    consumer=c.workflows.reports.for_context(make_context())
    with pytest.raises(AdapterError):await consumer.download('artifact','owner',expected_request='other-report')
    with pytest.raises(AdapterError,match='limit'):await consumer.download('artifact','owner',expected_request='report',limit=2)
    @asynccontextmanager
    async def revoked_stream(*args):
        async def chunks():
            yield b'authorized '
            reports.revoked=True
            yield b'report content'
        yield chunks()
    reports.stream_report_artifact=revoked_stream
    with pytest.raises(AdapterError):await consumer.download('artifact','owner',expected_request='report')
    reports.revoked=False
    @asynccontextmanager
    async def close_revoke(*args):
        async def chunks():yield b'authorized report content'
        try:yield chunks()
        finally:reports.revoked=True
    reports.stream_report_artifact=close_revoke
    with pytest.raises(AdapterError):await consumer.download('artifact','owner',expected_request='report')
    reports.revoked=False
    @asynccontextmanager
    async def wrong_bytes(*args):
        async def chunks():yield b'corrupt file'
        yield chunks()
    reports.stream_report_artifact=wrong_bytes
    with pytest.raises(AdapterError,match='hash_mismatch'):await consumer.download('artifact','owner',expected_request='report')
    await c.close()


@pytest.mark.parametrize('headers', [{},{'content-length':'1'},{'transfer-encoding':'chunked'},{'content-encoding':'gzip'}])
async def test_http_download_bound_no_or_false_length_chunked_and_compression(headers):
    class Chunks(httpx.AsyncByteStream):
        def __init__(self):self.reads=0;self.closed=False
        async def __aiter__(self):
            for _ in range(100):self.reads+=1;yield b'x'*65536
        async def aclose(self):self.closed=True
    source=Chunks()
    client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,headers=headers,stream=source)))
    adapter=BoundedHTTPDownload(client,limit=70000)
    with pytest.raises(AdapterError):
        async with adapter.stream('https://report.test/evidenced-file',{'Authorization':'test'}) as chunks:
            async for _ in chunks:pass
    assert source.reads<=2 and source.closed
    await client.aclose()


async def test_http_download_deadline_closes_upstream():
    class Slow(httpx.AsyncByteStream):
        closed=False
        async def __aiter__(self):await asyncio.sleep(1);yield b'x'
        async def aclose(self):self.closed=True
    source=Slow();client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,stream=source)))
    with pytest.raises(TimeoutError):
        async with BoundedHTTPDownload(client,deadline=.01).stream('https://report.test/file',{}) as chunks:
            async for _ in chunks:pass
    assert source.closed;await client.aclose()


def test_artifacts_missing_hash_and_environment_configuration(tmp_path,monkeypatch):
    with pytest.raises(AdapterError,match='missing'):ReportArtifacts(tmp_path,expected_hash='wrong')
    with pytest.raises(AdapterError,match='pin_required'):ReportArtifacts(REPO)
    with pytest.raises(AdapterError,match='hash_mismatch'):ReportArtifacts(REPO,expected_hash='wrong')
    dev=ReportArtifacts(REPO,development=True)
    monkeypatch.setenv('COORDINATION_REPORT_ROOT',str(REPO));monkeypatch.setenv('COORDINATION_REPORT_HASH',dev.artifact_hash)
    assert ReportArtifacts.from_environment().artifact_hash==dev.artifact_hash


async def test_provider_request_output_cap_whole_deadline_and_unknown_quota(tmp_path,monkeypatch):
    monkeypatch.setenv('TEST_MODEL_KEY','test-only')
    cfg=ProviderConfig(provider='openai-compatible',model='test',base_url='https://model.test/v1',key_env='TEST_MODEL_KEY',
        allowed_models=['test'],timeout=.01,output_tokens=10,input_bytes=10000)
    store=DevelopmentStore(tmp_path/'f.sqlite');budget=Budget(store,scope='run',token_limit=10000);calls=[]
    async def slow(req):calls.append(json.loads(req.content));await asyncio.sleep(1)
    model=ProviderModel(cfg,budget,store,client=httpx.AsyncClient(transport=httpx.MockTransport(slow)))
    with pytest.raises(TimeoutError):await model.generate({'synthetic':'rò nước'})
    assert calls[0]['max_tokens']==10
    with store.connection() as db:
        bound,used,status=db.execute('SELECT bound,used,status FROM ledger').fetchone()
        assert bound>1024 and used is None and 'unknown' in status
    with pytest.raises(ValueError):ProviderConfig(**(cfg.model_dump()|{'hard_cost_required':True}))
    await model.close()


async def test_openbot_money_cap_without_remote_bound_fails_before_network(tmp_path,monkeypatch):
    monkeypatch.setenv('TEST_BOT_KEY','test-only');store=DevelopmentStore(tmp_path/'f.sqlite');calls=[]
    adapter=OpenbotAdapter(ReleaseConsumer(Producer(),store),store,None,
        Budget(store,scope='remote',token_limit=10000,cost_limit=1,price_version='test',price_per_token='.00001'),
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda req:calls.append(req))))
    with pytest.raises(AdapterError,match='remote_cost_bound_unavailable'):await adapter.invoke(invocation())
    assert not calls
    await adapter.close()


async def test_readiness_worker_failure_and_drain(tmp_path,monkeypatch):
    monkeypatch.setenv('COORDINATION_INGRESS_TOKEN','x'*32)
    b,_,_,_=await bindings(tmp_path);c=build(b);app=create_app(ServiceConfig(),c)
    async def dead():return
    c.worker.run=dead
    async with app.router.lifespan_context(app):
        await asyncio.sleep(0)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            assert (await client.get('/ready')).status_code==503
            assert (await client.get('/health')).status_code==200
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        assert (await client.get('/ready')).status_code==503


@pytest.mark.parametrize('factory',['tests:factory','tests.runtime.fixture:factory','x.tests.fixture:factory','support:factory','module:','module:factory:extra'])
def test_production_cannot_load_test_factory(factory):
    with pytest.raises(ValueError):ServiceConfig(factory=factory)


async def test_snapshot_revoke_during_fetch_not_persisted(tmp_path):
    reports=Reports(make_context());b,store,_,_=await bindings(tmp_path,reports=reports);c=build(b)
    original=reports.fetch_report_snapshot
    async def revoked(*args):
        snapshot=await original(*args);reports.revoked=True;return snapshot
    reports.fetch_report_snapshot=revoked
    from tests.runtime.test_contributions_reports import report_config
    config=report_config();config=config.get('config',config)
    with pytest.raises(AdapterError):await c.workflows.reports.prepare(config,'owner')
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM records WHERE namespace='report_snapshot'").fetchone()[0]==0
    await c.close()


async def test_live_harness_limits_and_no_authorization_no_network(tmp_path,monkeypatch):
    import importlib.util
    spec=importlib.util.spec_from_file_location('live_test_harness',REPO/'agent-coordination/scripts/live_tests.py')
    harness=importlib.util.module_from_spec(spec);spec.loader.exec_module(harness)
    config=json.loads((REPO/'agent-coordination/config.live.example.json').read_text())
    approval=json.loads((REPO/'agent-coordination/live-approval.example.json').read_text())
    result=harness.preflight(approval,config,execute=True)
    assert result['blockers'] and result['live_status']=='BLOCKED'
    assert 'explicit approval missing' in result['blockers']
    for level in ('L2','L3'):
        assert harness.preflight(approval|{'level':level},config)['blockers']
    from tests.live.l1 import LimitedModel
    class Model:
        calls=0
        async def generate(self,prompt):self.calls+=1;return '{}'
    raw=Model();limited=LimitedModel(raw,1)
    await limited.generate({})
    from supervisor.models import SupervisorError
    with pytest.raises(SupervisorError,match='live_call_limit'):await limited.generate({})
    assert raw.calls==1


async def test_live_l1_composition_harness_with_mock_provider_only(monkeypatch):
    from tests.live.l1 import run
    monkeypatch.setenv('TEST_MODEL_KEY','mock-only-secret')
    config=ProviderConfig(provider='openai-compatible',model='mock',base_url='https://mock.test/v1',key_env='TEST_MODEL_KEY',
        allowed_models=['mock'],timeout=1,output_tokens=100,input_bytes=50000)
    cases={'Ống nước đang rò ở căn hộ':{'kind':'open','agent_version_ids':['technical-v1']},
           'Người lạ cố vào phòng':{'kind':'open','agent_version_ids':['security-v1']},
           'Đặt vệ sinh lúc 9 giờ':{'kind':'open','agent_version_ids':['service-v1']},
           'Rò nước và cần vệ sinh sau sửa':{'kind':'open','agent_version_ids':['technical-v1','service-v1']},
           'Có vấn đề trong nhà':{'kind':'question','question':'Mô tả cụ thể hơn?'}}
    calls=[]
    def provider(request):
        wire=json.loads(request.content);calls.append(wire)
        prompt=json.loads(wire['messages'][-1]['content'])
        text=prompt['state']['facts'][0]['report']
        decision=cases.get(text,{'kind':'pause','reason':'Requires verified backend authority'})
        return httpx.Response(200,json={'model':'mock','choices':[{'message':{'content':json.dumps(decision)}}],
            'usage':{'total_tokens':100}})
    approval=dict(max_calls=10,max_tokens=200000,budget_amount='100',price_version='mock-price-v1',price_per_token='.00001',
                  deadline_seconds=30,repetitions=1)
    result=await run(approval,config,client=httpx.AsyncClient(transport=httpx.MockTransport(provider)))
    assert result['passed'], (result['failures'],[v['scores'] for v in result['observations'].values()],result['extra_cases'])
    assert result['sample_size']==10 and result['calls']==10
    assert result['known_usage_tokens']==1000 and result['unknown_usage_calls']==0
    assert all(c['max_tokens']==100 for c in calls)
    assert 'mock-only-secret' not in json.dumps(result)


async def test_blocked_job_has_operator_reason_and_input_reference(tmp_path):
    from runtime.service import Worker
    store=DevelopmentStore(tmp_path/'f.sqlite')
    await store.accept('job',{'kind':'event','wire':{'event_id':'source'}})
    async def unknown(claim):raise AdapterError('current_attempt_receipt_missing',outcome_unknown=True)
    worker=Worker(store,unknown,owner='w',max_attempts=1)
    with pytest.raises(AdapterError):await worker.once()
    saved=await store.get('recovery_blocked','job')
    assert saved=={'reason':'current_attempt_receipt_missing','fence':1,'kind':'event','input_id':'source'}
    assert await store.claim('other') is None


async def test_openbot_total_deadline_retains_unknown_reservation_and_operation(tmp_path,monkeypatch):
    monkeypatch.setenv('TEST_BOT_KEY','test-only');store=DevelopmentStore(tmp_path/'f.sqlite');calls=[]
    class Slow(httpx.AsyncByteStream):
        closed=False
        async def __aiter__(self):
            for _ in range(100):await asyncio.sleep(.01);yield b': heartbeat\n\n'
        async def aclose(self):self.closed=True
    source=Slow()
    def response(req):calls.append(req);return httpx.Response(200,headers={'content-type':'text/event-stream'},stream=source)
    adapter=OpenbotAdapter(ReleaseConsumer(Producer(),store),store,None,Budget(store,scope='remote',token_limit=20000),
        client=httpx.AsyncClient(transport=httpx.MockTransport(response)),deadline=.03)
    with pytest.raises(TimeoutError):await adapter.invoke(invocation())
    assert source.closed
    with store.connection() as db:
        used,status=db.execute('SELECT used,status FROM ledger').fetchone()
        assert used is None and 'unknown' in status
    with pytest.raises(AdapterError,match='outcome_unknown'):await adapter.invoke(replace(invocation(),fence=2))
    assert len(calls)==1
    await adapter.close()


async def test_provider_exception_cleanup_uses_budget_port_and_preserves_known_usage(tmp_path,monkeypatch):
    monkeypatch.setenv('TEST_MODEL_KEY','test-only');store=DevelopmentStore(tmp_path/'f.sqlite')
    class Records:
        # Allocated records API has no SQL connection exposed to ProviderModel.
        async def put_once(self,namespace,key,value):
            if namespace=='model_result':raise RuntimeError('result persistence unavailable')
            return await store.put_once(namespace,key,value)
    config=ProviderConfig(provider='openai-compatible',model='mock',base_url='https://mock.test/v1',key_env='TEST_MODEL_KEY',
        allowed_models=['mock'],timeout=1,output_tokens=100,input_bytes=10000)
    def response(request):return httpx.Response(200,json={'model':'mock','choices':[{'message':{'content':'{}'}}],'usage':{'total_tokens':20}})
    model=ProviderModel(config,Budget(store,scope='run',token_limit=10000),Records(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(response)))
    with pytest.raises(RuntimeError,match='persistence unavailable'):await model.generate({'synthetic':'input'})
    with store.connection() as db:
        used,status=db.execute('SELECT used,status FROM ledger').fetchone()
        assert used==20 and status.startswith('known')
    await model.close()
