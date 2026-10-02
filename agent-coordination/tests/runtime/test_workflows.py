"""Real local composition/storage; all external producers are explicit test doubles."""
import asyncio
import hashlib
from contextlib import asynccontextmanager
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from adapters.backend.errors import AdapterError
from adapters.backend.messages import fingerprint
from config import ServiceConfig
from groupchat.models import AgentOutput,Participant
from groupchat.ports import Invocation
from persistence.budget import ScopedBudgets
from persistence.sqlite import DevelopmentStore
from runtime.composition import ProductionBindings,build
from runtime.contributions import Contributions,StaffContribution
from runtime.reporting import ReportArtifacts,ReportConsumer
from runtime.service import REQUIRED,create_app,Worker
from runtime.workflows import ContributionCommand,ReportCommand,Workflows
from support.fakes import make_context
from tests.runtime.test_contributions_reports import contribution,report_config,StaffBackend
from tests.runtime.test_releases_remote import Producer,invocation

REPO=Path(__file__).resolve().parents[3]


def command(kind,payload,*,identity='workflow-message',ctx=None):
    ctx=ctx or make_context()
    if kind=='contribution' and payload['operation']=='submit':
        value=payload['contribution'].copy()
        for field in ('tenant_id','workspace_id','ticket_id','ticket_generation','run_id'):
            value[field]=getattr(ctx,field)
        payload=payload|{'contribution':value}
    model=ContributionCommand if kind=='contribution' else ReportCommand
    return model(schema_version='coordination-workflow-proposal-1',message_id=identity,context=ctx,
                 ticket_version='v1',source_message_id='real-message',payload=payload).model_dump(mode='json')


class Authority:
    revoked=False
    stale=False
    wrong_hash=False
    actor=None
    async def verify_workflow(self,kind,cmd,wire,auth,fence):
        if self.revoked or self.stale or auth!='verified-source': return None
        actor=self.actor or ('staff' if kind=='contribution' and cmd.payload.operation=='submit' else
                             'supervisor' if kind=='contribution' else 'management')
        return dict(context=cmd.context.model_dump(mode='json'),message_id=cmd.message_id,
            source_message_id=cmd.source_message_id,ticket_version=cmd.ticket_version,
            payload_hash='wrong' if self.wrong_hash else fingerprint(wire),fence=fence,actor_kind=actor,
            actor_id='staff' if actor=='staff' else 'manager',authorization_reference='signed-ref',remote_fence_enforced=True)
    async def workflow_authentication(self,proof,auth):return {'scope':proof.context,'fence':proof.fence,'actor':proof.actor_kind}
    async def report_invocation(self,cmd,auth,op,fence,instruction,artifact_hash):
        i=invocation(cmd.context.ticket_id)
        return replace(i,context=cmd.context,operation_id=op,fence=fence,instruction=instruction,
            participant=i.participant.model_copy(update={'role':'report'}),artifact_hash=artifact_hash)


class Staff(StaffBackend):
    lost=False
    status_value='review_pending'
    status_version=1
    async def verify_staff_contribution(self,value,auth):
        assert auth['scope'].tenant_id==value.tenant_id
        proof=await super().verify_staff_contribution(value,'verified-source')
        return proof|{'corrects_revision':value.revision-1,'correction_allowed':self.status_value=='changes_requested'}
    async def submit_contribution(self,value,proof):
        result=await super().submit_contribution(value,proof)
        self.receipt=result
        if self.lost: raise TimeoutError()
        return result
    async def reconcile_contribution(self,value,proof): return getattr(self,'receipt',None)
    async def authorize_staff_request(self,cmd,auth):
        return {'payload_hash':fingerprint(cmd.model_dump(mode='json')),'work_outcome':'work_completed','staff_id':cmd.payload.staff_id}
    async def request_staff_contribution(self,cmd,proof):
        self.calls+=1
        return {'request_id':'backend-request','payload_hash':proof['payload_hash'],'status':'requested'}
    async def reconcile_staff_request(self,*args):return None
    async def authorize_contribution_status(self,cmd,auth): return {'payload_hash':fingerprint(cmd.model_dump(mode='json'))}
    async def contribution_status(self,cmd,proof):
        return {'tenant_id':cmd.context.tenant_id,'workspace_id':cmd.context.workspace_id,
            'contribution_id':cmd.payload.contribution_id,'revision':cmd.payload.revision,'version':self.status_version,'status':self.status_value}


class Reports:
    cancelled=False
    cancel_calls=0
    result_calls=0
    wrong_scope=False
    revoked=False
    def __init__(self,ctx):
        self.ctx=ctx
        self.artifact_hash=ReportArtifacts(REPO,development=True).artifact_hash
    def authorization(self,config=None):
        config=config or report_config();config=config.get('config',config)
        snapshot=self.snapshot(config)
        return dict(snapshot_id=snapshot['snapshot_id'],as_of=snapshot['as_of'],snapshot_hash=fingerprint(snapshot),
            tenant_id=self.ctx.tenant_id,workspace_id='foreign' if self.wrong_scope else self.ctx.workspace_id,
            report_request_id='report',scope_ids=config['scope_ids'],metric_ids=config['metrics'],source_ids=[])
    async def authorize_report(self,config,auth):
        if self.revoked: raise AdapterError('report_forbidden')
        return self.authorization(config)
    async def authorize_report_request(self,request,auth):
        if self.revoked:return None
        return self.authorization()|{'report_request_id':request}
    async def create_report_request(self,intent,auth):return intent|{'report_request_id':'report'}
    async def reconcile_report_request(self,*args):return None
    async def fetch_report_snapshot(self,config,auth):return self.snapshot(config)
    def snapshot(self,config):
        return dict(report_request_id='report',workspace_id=self.ctx.workspace_id,source_message_id='real-message',
            snapshot_id='snapshot',scope_ids=config['scope_ids'],period=config['period'],template_version=config['template_version'],
            as_of='2026-10-02T00:00:00+07:00',status='empty',metrics=[],sources=[])
    async def persist_report_result(self,intent,auth):
        self.result_calls+=1;return intent|{'result_id':'canonical-result'}
    async def reconcile_report_result(self,intent,auth):return intent|{'result_id':'canonical-result'}
    async def export_report(self,intent,auth):return intent|{'artifact_id':'artifact','content_sha256':hashlib.sha256(b'authorized report content').hexdigest()}
    async def reconcile_report_export(self,*args):return None
    async def cancel_report(self,intent,auth):self.cancel_calls+=1;return intent|{'status':'cancel_requested'}
    async def reconcile_report_cancel(self,intent,auth):return intent|{'status':'cancelled' if self.cancelled else 'cancel_requested'}
    async def report_status(self,request,auth):return dict(report_request_id=request,workspace_id=self.ctx.workspace_id,version=1,status='partial')
    async def authorize_report_artifact(self,artifact,auth):
        return None if self.revoked else self.authorization()|{'artifact_id':artifact,'artifact_hash':self.artifact_hash,
            'content_sha256':hashlib.sha256(b'authorized report content').hexdigest()}
    @asynccontextmanager
    async def stream_report_artifact(self,artifact,auth):
        async def chunks():yield b'authorized report content'
        yield chunks()


class Delegation:
    async def durable_reference(self,*args):return 'durable-reference'
    async def from_reference(self,reference):
        assert reference=='durable-reference';return 'verified-source'


class Model:
    async def close(self):pass
    async def generate(self,*args):raise AssertionError('D07 must not call Supervisor model')


class WorkflowReleases(Producer):
    async def resolve_released_session(self,i):
        value=await super().resolve_released_session(i)
        if i.participant.role=='report':
            value.update(capabilities=['report'],report_artifact_hash=i.artifact_hash)
        return value


async def bindings(tmp_path,*,now=None,authority=None,staff=None,reports=None):
    store=DevelopmentStore(tmp_path/'framework.sqlite',clock=(lambda:now[0]) if now else __import__('time').time)
    authority=authority or Authority();staff=staff or Staff()
    async def ready():return dict.fromkeys(REQUIRED,True) # test-only producer attestation
    async def close():pass
    b=ProductionBindings(backend_client=SimpleNamespace(validator=None),authority=None,event_verifier=None,
        reception_authentication=None,resolver=SimpleNamespace(supervisor_group=None),release_producer=WorkflowReleases(),
        tool_boundary=None,supervisor_store=store,room_store=store,inbox=store,records=store,
        supervisor_model=Model(),remote_budget=ScopedBudgets(store,token_limit=100000),
        delegation=Delegation(),worker_authentication=Delegation(),readiness=ready,close=close,
        groupchat_version_id='group-v1',event_types={},workflow_authority=authority,contribution_producer=staff,
        report_producer=reports,report_artifacts=ReportArtifacts(REPO,development=True) if reports else None)
    return b,store,authority,staff


async def test_d07_composition_durable_ingress_restart_unknown_and_terminal_unchanged(tmp_path):
    now=[100.];staff=Staff();staff.lost=True
    b,store,authority,_=await bindings(tmp_path,now=now,staff=staff)
    c=build(b)
    raw=command('contribution',{'operation':'submit','contribution':contribution()})
    ctx=make_context()
    from supervisor.models import SupervisorState
    state=SupervisorState(context=ctx,groupchat_version_id='group-v1',turn_policy={},phase='completed')
    await store.commit(state,None)
    await c.ingress.accept('contribution',raw,'verified-source')
    assert (await store.load(ctx)).phase=='completed'
    with pytest.raises(TimeoutError):await c.worker.once()
    assert staff.calls==1
    with store.connection() as db:assert db.execute('SELECT status FROM inbox').fetchone()==('pending',)
    await c.close();now[0]+=6
    restarted=build(b)
    assert await restarted.worker.once() # reconcile receipt, never second submit
    assert staff.calls==1 and (await store.load(ctx)).phase=='completed'
    with store.connection() as db:assert db.execute('SELECT status FROM inbox').fetchone()==('done',)
    authority.revoked=True
    with pytest.raises(AdapterError,match='not_authorized'):
        await restarted.ingress.accept('contribution',raw,'verified-source')
    await restarted.close()


@pytest.mark.parametrize('condition',['actor','version','hash','unbound'])
async def test_workflow_rejects_invalid_proof_before_durable_ack(tmp_path,condition):
    b,store,authority,staff=await bindings(tmp_path)
    if condition=='actor':authority.actor='supervisor'
    elif condition=='version':authority.stale=True
    elif condition=='hash':authority.wrong_hash=True
    else:b.workflow_authority=None
    c=build(b)
    raw=command('contribution',{'operation':'submit','contribution':contribution()})
    with pytest.raises(AdapterError):await c.ingress.accept('contribution',raw,'verified-source')
    assert await store.claim('w') is None and staff.calls==0
    await c.close()


async def test_staff_request_review_correct_and_revoke_are_separate_workflow(tmp_path):
    b,store,authority,staff=await bindings(tmp_path);c=build(b)
    request=command('contribution',dict(operation='request',staff_id='staff',task_id='task',work_order_id='work',
        requested_fields=['procedure','actual_cost'],message='Vui lòng xác nhận procedure, chi phí thực tế và evidence'))
    await c.ingress.accept('contribution',request,'verified-source');await c.worker.once()
    assert staff.calls==1
    raw=command('contribution',{'operation':'submit','contribution':contribution()},identity='submit')
    await c.ingress.accept('contribution',raw,'verified-source');await c.worker.once()
    status=command('contribution',{'operation':'status','contribution_id':'c1','revision':1},identity='status')
    assert (await c.workflows.execute('contribution',status,'verified-source',fence=1))['status']=='review_pending'
    correction=command('contribution',{'operation':'submit','contribution':contribution()|{'revision':2,'actual_cost':'120000','currency':'VND'}},identity='correct')
    with pytest.raises(AdapterError,match='correction_denied'):await c.workflows.execute('contribution',correction,'verified-source',fence=1)
    staff.status_value='changes_requested';staff.status_version=2
    assert (await c.workflows.execute('contribution',status|{'message_id':'status-2'},'verified-source',fence=1))['status']=='changes_requested'
    assert (await c.workflows.execute('contribution',correction,'verified-source',fence=1))['revision']==2
    staff.status_value='revoked';staff.status_version=3
    assert (await c.workflows.execute('contribution',status|{'message_id':'status-3'},'verified-source',fence=1))['status']=='revoked'
    with pytest.raises(ValueError):StaffContribution.model_validate(contribution()|{'procedure':'  '})
    await c.close()


async def test_two_workers_same_revision_no_duplicate_side_effect(tmp_path):
    store=DevelopmentStore(tmp_path/'f.sqlite');staff=Staff()
    a=Contributions(staff,store);b=Contributions(staff,DevelopmentStore(store.path))
    value=StaffContribution.model_validate(contribution())
    auth={'scope':make_context().model_copy(update={'tenant_id':value.tenant_id})}
    # Yield while applying, so another worker sees intent without a receipt.
    original=staff.submit_contribution
    started=asyncio.Event();release=asyncio.Event()
    async def delayed(*args):started.set();await release.wait();return await original(*args)
    staff.submit_contribution=delayed
    first=asyncio.create_task(a.submit(value,auth));await started.wait()
    with pytest.raises(AdapterError,match='outcome_unknown'):await b.submit(value,auth)
    release.set();await first
    assert staff.calls==1


async def test_d08_composed_released_remote_narrative_export_and_revoke(tmp_path,monkeypatch):
    monkeypatch.setenv('TEST_BOT_KEY','test-secret')
    ctx=make_context();reports=Reports(ctx)
    b,store,authority,_=await bindings(tmp_path,reports=reports);c=build(b)
    config=report_config();config=config.get('config',config)
    prepare=command('report',{'operation':'prepare','report_request_id':'report','config':config},identity='prepare')
    await c.ingress.accept('report',prepare,'verified-source');await c.worker.once()
    export=command('report',{'operation':'export','report_request_id':'report'},identity='export')
    with pytest.raises(AdapterError,match='result_required'):await c.workflows.execute('report',export,'verified-source',fence=1)
    requests=[]
    def stream(request):
        wire=json.loads(request.content);requests.append(wire)
        content=json.loads(wire['messages'][0]['content']);prompt=json.loads(content['instruction'])
        output=AgentOutput(content=json.dumps({'snapshot_id':prompt['snapshot_id'],'narrative':prompt['narrative']}))
        events=[{'type':'RUN_STARTED','threadId':wire['threadId'],'runId':wire['runId']},
            {'type':'TEXT_MESSAGE_START','messageId':'m','role':'assistant'},
            {'type':'TEXT_MESSAGE_CONTENT','messageId':'m','delta':output.model_dump_json()},
            {'type':'TEXT_MESSAGE_END','messageId':'m'},
            {'type':'RUN_FINISHED','threadId':wire['threadId'],'runId':wire['runId']}]
        return httpx.Response(200,headers={'content-type':'text/event-stream'},content=''.join('data: '+json.dumps(e)+'\n\n' for e in events))
    # Actual AgentScope adapter, release loader, SSE parser; transport is test-only.
    remote=c.workflows.remote.remote;await remote.client.aclose()
    remote.client=httpx.AsyncClient(transport=httpx.MockTransport(stream))
    run=command('report',{'operation':'run','report_request_id':'report'},identity='run')
    await c.ingress.accept('report',run,'verified-source');await c.worker.once()
    assert len(requests)==1 and reports.result_calls==1
    # Same operation with fresh command/fence does not execute remote again.
    await c.workflows.execute('report',run|{'message_id':'run-duplicate'},'verified-source',fence=2)
    assert len(requests)==1 and reports.result_calls==1
    assert (await c.workflows.execute('report',export,'verified-source',fence=1))['artifact_id']=='artifact'
    reports.revoked=True
    with pytest.raises(AdapterError):await c.workflows.execute('report',export|{'message_id':'after-revoke'},'verified-source',fence=1)
    await c.close()


async def test_cancel_waits_for_backend_confirmation_and_no_duplicate_cancel(tmp_path):
    now=[100.];reports=Reports(make_context())
    b,store,authority,_=await bindings(tmp_path,now=now,reports=reports);c=build(b)
    raw=command('report',{'operation':'cancel','report_request_id':'report'})
    await c.ingress.accept('report',raw,'verified-source');await c.worker.once()
    with store.connection() as db:assert db.execute('SELECT status FROM inbox').fetchone()==('pending',)
    reports.cancelled=True;now[0]+=6
    await c.worker.once()
    with store.connection() as db:assert db.execute('SELECT status FROM inbox').fetchone()==('done',)
    assert reports.cancel_calls==1
    await c.close()


async def test_asgi_workflow_lifespan_auth_download_and_missing_binding(tmp_path,monkeypatch):
    monkeypatch.setenv('COORDINATION_INGRESS_TOKEN','x'*32)
    b,store,authority,staff=await bindings(tmp_path,reports=Reports(make_context()));c=build(b)
    # ASGI transport headers are authenticated by this explicit test adapter.
    verify=authority.verify_workflow
    async def http_verify(kind,cmd,wire,headers,fence):
        assert headers['authorization']=='Bearer '+'x'*32
        return await verify(kind,cmd,wire,'verified-source',fence)
    authority.verify_workflow=http_verify
    delegation=b.delegation
    async def delegate(proof,headers):return {'scope':proof.context,'fence':proof.fence,'actor':proof.actor_kind}
    authority.workflow_authentication=delegate
    # Worker authenticates durable refs rather than replaying raw HTTP headers.
    async def worker_http_ref(reference):return {'authorization':'Bearer '+'x'*32}
    b.worker_authentication.from_reference=worker_http_ref
    app=create_app(ServiceConfig(),c);headers={'Authorization':'Bearer '+'x'*32}
    raw=command('contribution',{'operation':'submit','contribution':contribution()})
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            assert (await client.get('/ready')).status_code==200
            assert (await client.post('/v2/contributions',json=raw)).status_code==401
            assert (await client.post('/v2/contributions',json=raw,headers=headers)).status_code==202
            for _ in range(100):
                if staff.calls:break
                await asyncio.sleep(.01)
            assert staff.calls==1
            with store.connection() as db:
                assert 'Bearer' not in db.execute('SELECT body FROM inbox').fetchone()[0]
            await prepare_export(c.workflows.reports,'verified-source')
            download=command('report',{'operation':'download','artifact_id':'artifact','report_request_id':'report'},identity='download')
            response=await client.post('/v2/report-downloads',json=download,headers=headers)
            assert response.status_code==200 and response.content==b'authorized report content'
            assert response.headers['cache-control']=='no-store'
            b.report_producer.revoked=True
            assert (await client.post('/v2/report-downloads',json=download,headers=headers)).status_code==503
    assert c.worker.stopping.is_set()
    # Absent C13/C14 never fabricates a receipt.
    b.workflow_authority=None;unbound=build(b)
    with pytest.raises(AdapterError,match='unavailable'):await unbound.ingress.accept('report',download,'verified-source')
    await unbound.close()


async def test_report_wrong_scope_narrative_and_snapshot_changes_rejected(tmp_path):
    reports=Reports(make_context());store=DevelopmentStore(tmp_path/'f.sqlite')
    consumer=ReportConsumer(ReportArtifacts(REPO,development=True),reports,store);workflow=Workflows(Authority(),store,reports=consumer)
    config=report_config();config=config.get('config',config)
    raw=command('report',{'operation':'prepare','report_request_id':'report','config':config})
    reports.wrong_scope=True
    with pytest.raises(AdapterError,match='scope_mismatch'):await workflow.execute('report',raw,'verified-source',fence=1)
    reports.wrong_scope=False
    await workflow.execute('report',raw,'verified-source',fence=1)
    with pytest.raises(AdapterError,match='narrative_mismatch'):
        await consumer.persist_narrative('report',{'snapshot_id':'snapshot','narrative':{'rows':[{'value':0}]}},'owner')
    original=reports.fetch_report_snapshot
    async def changed(*args):return (await original(*args))|{'as_of':'2026-10-03T00:00:00+07:00'}
    reports.fetch_report_snapshot=changed
    with pytest.raises(AdapterError,match='conflict'):await consumer.prepare(config,'owner')
    assert reports.result_calls==0


async def test_report_submit_status_and_scope_isolation(tmp_path):
    ctx=make_context();reports=Reports(ctx)
    b,store,authority,_=await bindings(tmp_path,reports=reports);c=build(b)
    config=report_config();config=config.get('config',config)
    submit=command('report',{'operation':'submit','config':config},identity='submit-report')
    receipt=await c.workflows.execute('report',submit,'verified-source',fence=1)
    assert receipt['source_message_id']=='real-message' and receipt['report_request_id']=='report'
    assert await c.workflows.execute('report',submit,'verified-source',fence=2)==receipt
    status=command('report',{'operation':'status','report_request_id':'report'},identity='report-status')
    assert (await c.workflows.execute('report',status,'verified-source',fence=1))['status']=='partial'
    foreign=command('report',{'operation':'status','report_request_id':'report'},ctx=ctx.model_copy(update={'workspace_id':'other-bql'}))
    with pytest.raises(AdapterError,match='scope_mismatch'):await c.workflows.execute('report',foreign,'verified-source',fence=1)
    reports.revoked=True
    with pytest.raises(AdapterError):await c.workflows.execute('report',submit,'verified-source',fence=3)
    await c.close()


async def test_cached_workflow_receipt_cannot_bypass_evidence_revoke(tmp_path):
    b,store,authority,staff=await bindings(tmp_path);c=build(b)
    raw=command('contribution',{'operation':'submit','contribution':contribution()})
    await c.workflows.execute('contribution',raw,'verified-source',fence=1)
    staff.actor='agent' # producer revokes the verified staff/evidence attestation
    with pytest.raises(AdapterError,match='not_verified'):await c.workflows.execute('contribution',raw,'verified-source',fence=2)
    assert staff.calls==1
    await c.close()


async def test_report_snapshot_attestation_and_report_release_pin_fail_closed(tmp_path,monkeypatch):
    monkeypatch.setenv('TEST_BOT_KEY','test-secret')
    ctx=make_context();reports=Reports(ctx)
    b,store,authority,_=await bindings(tmp_path,reports=reports);c=build(b)
    config=report_config();config=config.get('config',config)
    prepare=command('report',{'operation':'prepare','report_request_id':'report','config':config})
    original=reports.fetch_report_snapshot
    async def stale(*args):return (await original(*args))|{'as_of':'2026-09-30T00:00:00+07:00'}
    reports.fetch_report_snapshot=stale
    with pytest.raises(AdapterError,match='attestation_mismatch'):await c.workflows.execute('report',prepare,'verified-source',fence=1)
    with store.connection() as db:assert db.execute("SELECT count(*) FROM records WHERE namespace='report_snapshot'").fetchone()[0]==0
    reports.fetch_report_snapshot=original
    await c.workflows.execute('report',prepare,'verified-source',fence=1)
    # Specialist-only release cannot be substituted for published Report artifacts.
    c.workflows.remote.remote.releases.producer=Producer()
    run=command('report',{'operation':'run','report_request_id':'report'},identity='run')
    with pytest.raises(AdapterError,match='release_artifact_mismatch'):await c.workflows.execute('report',run,'verified-source',fence=1)
    assert reports.result_calls==0
    await c.close()


async def test_report_cancel_during_remote_reply_blocks_publication(tmp_path,monkeypatch):
    monkeypatch.setenv('TEST_BOT_KEY','test-secret')
    reports=Reports(make_context());b,store,authority,_=await bindings(tmp_path,reports=reports);c=build(b)
    config=report_config();config=config.get('config',config)
    prepare=command('report',{'operation':'prepare','report_request_id':'report','config':config})
    await c.workflows.execute('report',prepare,'verified-source',fence=1)
    async def stream(request):
        wire=json.loads(request.content);prompt=json.loads(json.loads(wire['messages'][0]['content'])['instruction'])
        cancelled=command('report',{'operation':'cancel','report_request_id':'report'},identity='cancel')
        assert await c.workflows.execute('report',cancelled,'verified-source',fence=2) is None
        output=AgentOutput(content=json.dumps({'snapshot_id':prompt['snapshot_id'],'narrative':prompt['narrative']}))
        common={'threadId':wire['threadId'],'runId':wire['runId']}
        events=[{'type':'RUN_STARTED',**common},{'type':'TEXT_MESSAGE_START','messageId':'m','role':'assistant'},
            {'type':'TEXT_MESSAGE_CONTENT','messageId':'m','delta':output.model_dump_json()},
            {'type':'TEXT_MESSAGE_END','messageId':'m'},{'type':'RUN_FINISHED',**common}]
        return httpx.Response(200,headers={'content-type':'text/event-stream'},content=''.join('data: '+json.dumps(e)+'\n\n' for e in events))
    remote=c.workflows.remote.remote;await remote.client.aclose()
    remote.client=httpx.AsyncClient(transport=httpx.MockTransport(stream))
    raw=command('report',{'operation':'run','report_request_id':'report'},identity='run')
    with pytest.raises(AdapterError,match='cancel_requested'):await c.workflows.execute('report',raw,'verified-source',fence=1)
    assert reports.result_calls==0 and reports.cancel_calls==1
    with pytest.raises(AdapterError,match='cancel_requested'):await c.workflows.execute('report',raw,'verified-source',fence=2)
    await c.close()


async def test_supervisor_work_observer_durably_requests_real_staff_once(tmp_path):
    b,store,authority,staff=await bindings(tmp_path);c=build(b)
    raw=command('contribution',dict(operation='request',staff_id='staff',task_id='task',work_order_id='work',
        requested_fields=['procedure','actual_cost'],message='Xác nhận procedure và actual cost sau xử lý'),identity='canonical-c13-request')
    calls=[]
    async def resolve(state,delivery,auth):
        calls.append(delivery.event_id);return raw
    staff.staff_request_for_work=resolve
    state=SimpleNamespace(context=make_context(),phase='completed',result={'result_id':'verified-work-result'})
    delivery=SimpleNamespace(message_type='work.completed',event_id='verified-work-event')
    receipt=await c.workflows.request_after_work(state,delivery,'verified-source',c.ingress)
    assert receipt['durable'] and state.phase=='completed'
    assert await c.workflows.request_after_work(state,delivery,'verified-source',c.ingress)==receipt
    assert await c.worker.once() and staff.calls==1
    assert not await c.worker.once()
    assert state.phase=='completed' and calls==['verified-work-event']
    await c.close()


def test_workflow_schema_is_generated_from_runtime_and_rejects_publish():
    from jsonschema import Draft202012Validator
    from runtime.workflows import WorkflowProof
    for name,model in [('contribution',ContributionCommand),('report',ReportCommand),('proof',WorkflowProof)]:
        schema=json.loads((REPO/'docs/teams/dong/workflow-proposals'/(name+'.schema.json')).read_text())
        assert schema==model.model_json_schema() and schema['additionalProperties'] is False
    raw=command('contribution',{'operation':'submit','contribution':contribution()})
    Draft202012Validator(ContributionCommand.model_json_schema()).validate(raw)
    with pytest.raises(ValueError):ContributionCommand.model_validate(raw|{'payload':{'operation':'publish','contribution_id':'c1'}})
    with pytest.raises(ValueError):ReportCommand.model_validate(command('report',{'operation':'status','report_request_id':'report'})|{'source_message_id':None})


async def test_equal_report_ids_in_two_tenants_do_not_share_snapshots(tmp_path):
    ctx=make_context();foreign=ctx.model_copy(update={'tenant_id':'another-tenant'})
    store=DevelopmentStore(tmp_path/'f.sqlite');artifacts=ReportArtifacts(REPO,development=True)
    a,b=ReportConsumer(artifacts,Reports(ctx),store),ReportConsumer(artifacts,Reports(foreign),store)
    config=report_config();config=config.get('config',config)
    await a.prepare(config,'owner',require_snapshot_pin=True)
    # Same workspace/request IDs in a different tenant can't read first tenant's pin.
    with pytest.raises(AdapterError,match='snapshot_required'):await b.pinned('report','owner')
    await b.prepare(config,'owner',require_snapshot_pin=True)
    with store.connection() as db:assert db.execute("SELECT count(*) FROM records WHERE namespace='report_snapshot'").fetchone()[0]==2


async def test_second_authorization_cannot_change_scope_after_initial_valid_proof(tmp_path):
    reports=Reports(make_context());b,store,authority,_=await bindings(tmp_path,reports=reports);c=build(b)
    config=report_config();config=config.get('config',config)
    original=reports.authorize_report;calls=[]
    async def inconsistent(*args):
        proof=await original(*args);calls.append(1)
        return proof if len(calls)==1 else proof|{'tenant_id':'foreign-tenant'}
    reports.authorize_report=inconsistent
    raw=command('report',{'operation':'prepare','report_request_id':'report','config':config})
    with pytest.raises(AdapterError,match='scope_mismatch'):await c.workflows.execute('report',raw,'verified-source',fence=1)
    with store.connection() as db:assert db.execute("SELECT count(*) FROM records WHERE namespace='report_snapshot'").fetchone()[0]==0
    await c.close()


async def prepare_export(reports,authentication):
    config=report_config();config=config.get('config',config)
    snapshot=await reports.prepare(config,authentication,require_snapshot_pin=True)
    key,saved,auth=await reports.pinned('report',authentication,require_snapshot_pin=True)
    draft={'snapshot_id':snapshot['snapshot_id'],'narrative':reports.artifacts.narrative(snapshot,saved['config'],auth)}
    await reports.persist_narrative('report',draft,authentication)
    return await reports.export('report',authentication)
