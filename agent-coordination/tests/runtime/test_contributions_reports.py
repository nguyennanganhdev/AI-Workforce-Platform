import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from adapters.backend.errors import AdapterError
from adapters.backend.messages import fingerprint
from persistence.sqlite import DevelopmentStore
from runtime.contributions import Contributions
from runtime.reporting import ReportArtifacts,ReportConsumer
from runtime.backend import BackendAuthority
from supervisor.models import SupervisorState,Action
from support.fakes import make_context


REPO=Path(__file__).resolve().parents[3]


def contribution():
    return dict(contribution_id='c1',tenant_id='tenant',workspace_id='workspace',ticket_id='ticket',ticket_generation=1,
        run_id='run',task_id='task',work_order_id='work',source_message_id='real-message',author_id='staff',revision=1,
        evidence_ids=['evidence'],procedure='Quy trình đề xuất',actual_cost=None,currency=None)


class StaffBackend:
    def __init__(self): self.actor='staff';self.calls=0
    async def verify_staff_contribution(self,value,auth):
        if auth!='verified-source': return None
        return dict(actor_kind=self.actor,author_id=value.author_id,work_order_id=value.work_order_id,
            tenant_id=value.tenant_id,workspace_id=value.workspace_id,revision=value.revision,verified_evidence_ids=value.evidence_ids,payload_hash=fingerprint(value.model_dump(mode='json')))
    async def submit_contribution(self,value,proof):
        self.calls+=1
        return dict(contribution_id=value.contribution_id,revision=value.revision,status='review_pending')
    async def reconcile_contribution(self,value,proof): return None


async def test_d07_staff_proof_duplicate_and_agent_cannot_confirm(tmp_path):
    backend=StaffBackend();store=DevelopmentStore(tmp_path/'f.sqlite');consumer=Contributions(backend,store)
    raw=contribution()
    receipt=await consumer.submit(raw,'verified-source')
    assert receipt['status']=='review_pending'
    assert await Contributions(backend,DevelopmentStore(store.path)).submit(raw,'verified-source')==receipt
    assert backend.calls==1
    with pytest.raises(AdapterError,match='conflict'): await consumer.submit(raw|{'procedure':'changed'},'verified-source')
    backend.actor='agent'
    with pytest.raises(AdapterError,match='not_verified'): await consumer.submit(raw|{'contribution_id':'c2'},'verified-source')
    with pytest.raises(AdapterError,match='not_verified'): await consumer.submit(raw,'forged-source')


async def test_d07_unknown_submit_not_replayed(tmp_path):
    backend=StaffBackend()
    async def lost(value,proof): backend.calls+=1;raise TimeoutError()
    backend.submit_contribution=lost
    consumer=Contributions(backend,DevelopmentStore(tmp_path/'f.sqlite'))
    with pytest.raises(TimeoutError): await consumer.submit(contribution(),'verified-source')
    with pytest.raises(AdapterError,match='outcome_unknown'): await consumer.submit(contribution(),'verified-source')
    assert backend.calls==1


def report_config():
    return json.loads((REPO/'agent-report/examples/management-a.json').read_text())


def test_d08_consumes_existing_artifacts_and_checks_scope_lineage_missing():
    artifacts=ReportArtifacts(REPO,development=True)
    raw=report_config()
    # Example is wrapper? Resolve actual config without inventing new template.
    config=raw.get('config',raw)
    parsed=artifacts.validate_config(config,{'scope_ids':config['scope_ids'],'metric_ids':config['metrics']})
    auth=dict(report_request_id='report',workspace_id='workspace',scope_ids=config['scope_ids'],source_ids=['source'])
    metric=config['metrics'][0]
    snapshot=dict(report_request_id='report',workspace_id='workspace',source_message_id='real-message',snapshot_id='snapshot',
        scope_ids=config['scope_ids'],period=config['period'],template_version=config['template_version'],as_of='2026-10-02T00:00:00+07:00',
        status='partial',sources=[],metrics=[{'id':metric,'version':config['metric_versions'][metric],'status':'missing','value':None,'source_ids':[],'unit':dict(ticket_volume='tickets',sla='percent',assignments='assignments',outcomes='work_orders')[metric]}])
    assert artifacts.validate_snapshot(snapshot,parsed,auth)['metrics'][0]['value'] is None
    with pytest.raises(AdapterError,match='must_be_null'):
        artifacts.validate_snapshot(snapshot|{'metrics':[snapshot['metrics'][0]|{'value':0}]},parsed,auth)
    with pytest.raises(AdapterError,match='scope_forbidden'):
        artifacts.validate_snapshot(snapshot|{'workspace_id':'other'},parsed,auth)
    with pytest.raises(AdapterError,match='complete_has_missing'):
        artifacts.validate_snapshot(snapshot|{'status':'complete'},parsed,auth)
    # Proposal metric catalog is preserved, never silently promoted to published.
    assert artifacts.metrics['status'].startswith('proposal_')


async def test_d08_download_reauthorizes_revoke(tmp_path):
    from tests.runtime.test_workflows import Reports,prepare_export
    backend=Reports(make_context());consumer=ReportConsumer(ReportArtifacts(REPO,development=True),backend,DevelopmentStore(tmp_path/'f.sqlite'))
    await prepare_export(consumer,'owner')
    assert await consumer.download('artifact','owner',expected_request='report')==b'authorized report content'
    backend.revoked=True
    with pytest.raises(AdapterError,match='forbidden'): await consumer.download('artifact','owner',expected_request='report')


async def test_authority_reconcile_rejects_previous_attempt_and_unfenced_not_applied():
    state=SupervisorState(context=make_context(),groupchat_version_id='g',turn_policy={})
    action=Action(action_id='op',channel='backend',operation='op',wire={},plan_version=1,dispatch_attempt=2)
    class Operations:
        attempt=1;fenced=True
        async def call(self,*args): return {'action_id':'op','dispatch_attempt':self.attempt,'outcome':'not_applied','old_sender_fenced':self.fenced}
    operations=Operations();authority=BackendAuthority(operations,'trusted')
    with pytest.raises(AdapterError,match='attempt_mismatch'): await authority.reconcile(state,action)
    operations.attempt=2;operations.fenced=False
    with pytest.raises(AdapterError,match='fence_missing'): await authority.reconcile(state,action)
    operations.fenced=True
    assert (await authority.reconcile(state,action)).outcome=='not_applied'


async def test_d08_request_retry_real_source_cancel_not_confirmed_and_revoke(tmp_path):
    artifacts=ReportArtifacts(REPO,development=True);config=report_config();config=config.get('config',config)
    class Backend:
        calls=0;revoked=False
        async def authorize_report(self,c,auth):
            if self.revoked: raise AdapterError('report_forbidden')
            return {'workspace_id':'workspace','scope_ids':c['scope_ids'],'metric_ids':c['metrics']}
        async def create_report_request(self,intent,auth):
            self.calls+=1
            return {**intent,'report_request_id':'canonical-report'}
        async def authorize_report_request(self,request,auth): return None if self.revoked else {'workspace_id':'workspace'}
        async def cancel_report(self,intent,auth): return {**intent,'status':'cancel_requested'}
    backend=Backend();consumer=ReportConsumer(artifacts,backend,DevelopmentStore(tmp_path/'f.sqlite'))
    with pytest.raises(AdapterError,match='source_message_required'): await consumer.submit(config,'','owner')
    result=await consumer.submit(config,'source-message','owner')
    assert await consumer.submit(config,'source-message','owner')==result and backend.calls==1
    assert (await consumer.cancel(result['report_request_id'],'owner'))['status']=='cancel_requested'
    backend.revoked=True
    with pytest.raises(AdapterError,match='forbidden'): await consumer.submit(config,'source-message','owner')


async def test_d08_export_lost_receipt_is_not_blindly_retried(tmp_path):
    artifacts=ReportArtifacts(REPO,development=True);config=report_config();config=config.get('config',config)
    metric=config['metrics'][0]
    auth=dict(report_request_id='report',workspace_id='workspace',scope_ids=config['scope_ids'],metric_ids=config['metrics'],source_ids=[])
    snapshot=dict(report_request_id='report',workspace_id='workspace',source_message_id='source',snapshot_id='snapshot',
        scope_ids=config['scope_ids'],period=config['period'],template_version=config['template_version'],as_of='2026-10-02T00:00:00+07:00',
        status='empty',metrics=[],sources=[])
    class Backend:
        calls=0
        async def authorize_report(self,*args):return auth
        async def fetch_report_snapshot(self,*args):return snapshot
        async def authorize_report_request(self,*args):return auth
        async def export_report(self,*args):self.calls+=1;raise TimeoutError()
        async def reconcile_report_export(self,*args):return None
    backend=Backend();consumer=ReportConsumer(artifacts,backend,DevelopmentStore(tmp_path/'f.sqlite'))
    await consumer.prepare(config,'owner')
    key,_,_=await consumer.pinned('report','owner')
    await consumer.records.put_once('report_result_receipt',key,{'result_id':'test-canonical-result'})
    with pytest.raises(TimeoutError):await consumer.export('report','owner')
    with pytest.raises(AdapterError,match='outcome_unknown'):await consumer.export('report','owner')
    assert backend.calls==1
