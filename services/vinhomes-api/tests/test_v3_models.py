"""Registry persistence, provider checks and access boundaries against tenant-scoped PostgreSQL."""
import asyncio
import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from uuid import UUID, uuid4
from test_resident_contract import TENANT, sql
from test_resident_contract import database as database
from test_v3_agent_database import demo_client
from vinhomes_api.v3_models import RegisterModel, runtime_config


def test_credential_references_and_urls_are_deployment_owned(monkeypatch):
    with pytest.raises(ValidationError): RegisterModel(name='m',provider='openai',credential_env='VINHOMES_API_COORDINATION_SERVICE_TOKEN')
    monkeypatch.setenv('OPENAI_API_KEY','never-return-this-key')
    monkeypatch.setenv('CUSTOM_BASE_URL','http://remote.example/v1')
    with pytest.raises(HTTPException): runtime_config({'id':'x','name':'m','provider':'custom','kind':'chat','credential_env':'OPENAI_API_KEY','base_url_env':'CUSTOM_BASE_URL'})


def test_registry_check_defaults_and_management_allowlist(database,monkeypatch):
    from vinhomes_api import v3_models
    monkeypatch.setenv('OPENAI_API_KEY','never-return-this-key')
    asked=[]
    class Provider:
        def __init__(self,**kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): return False
        async def post(self,url,headers,json):
            asked.append((url,json))
            assert headers['Authorization']=='Bearer never-return-this-key'
            if url.endswith('/embeddings'): return httpx.Response(200,json={'data':[{'embedding':[0.1]*json.get('dimensions',1536)}]})
            return httpx.Response(200,json={'choices':[{'message':{'content':'OK'}}]})
    monkeypatch.setattr(v3_models.httpx,'AsyncClient',Provider)
    body={'name':'checked-'+uuid4().hex,'provider':'openai','credential_env':'OPENAI_API_KEY','kind':'chat'}
    with demo_client(database,'management') as manager:
        assert manager.get('/admin/model-registry').status_code==403
        assert manager.post('/admin/model-registry',json=body).status_code==403
    with demo_client(database,'admin') as admin:
        added=admin.post('/admin/model-registry',json=body)
        assert added.status_code==201,added.text
        identity=added.json()['id']
        assert admin.patch('/admin/model-registry/'+identity,json={'allowed':True}).status_code==422
        assert admin.put('/admin/model-defaults/supervisor',json={'model_id':identity}).status_code==422
        checked=admin.post('/admin/model-registry/'+identity+'/check')
        assert checked.status_code==200 and checked.json()['ok']
        assert asked[-1][1]['model']==body['name']
        assert admin.patch('/admin/model-registry/'+identity,json={'allowed':True}).status_code==200
        assert admin.put('/admin/model-defaults/supervisor',json={'model_id':identity}).status_code==200
        assert admin.put('/admin/model-defaults/embedding',json={'model_id':identity}).status_code==422
        listed=admin.get('/admin/model-registry')
        assert 'never-return-this-key' not in listed.text
        assert any(row['role']=='supervisor' and row['model_id']==identity for row in listed.json()['defaults'])
        assert admin.get('/internal/coordination/v1/model-config/supervisor').status_code in (401,503)
        assert admin.get('/internal/reception/v1/model-config').status_code in (401,403,503)
        assert sql(database,'select model_id from admin_role_models where tenant_id=$1 and role=$2',TENANT,'supervisor')[0]['model_id']==UUID(identity)
    with demo_client(database,'management') as manager:
        allowed=manager.get('/models/allowed')
        assert allowed.status_code==200,allowed.text
        assert any(row['id']==identity for row in allowed.json()['items'])
        assert 'credential_env' not in allowed.text and 'never-return-this-key' not in allowed.text
    with demo_client(database,'admin') as admin:
        assert admin.patch('/admin/model-registry/'+identity,json={'allowed':False}).status_code==200
        with demo_client(database,'management') as manager:
            assert manager.delete('/admin/model-defaults/supervisor').status_code==403
        assert admin.delete('/admin/model-defaults/unknown').status_code==422
        cleared=admin.delete('/admin/model-defaults/supervisor')
        assert cleared.status_code==200 and cleared.json()['model_id'] is None
        assert not any(item['role']=='supervisor' for item in admin.get('/admin/model-registry').json()['defaults'])
        assert not sql(database,'select model_id from admin_role_models where tenant_id=$1 and role=$2',TENANT,'supervisor')
        # Repeating a clear keeps the deployment fallback and adds no duplicate change event.
        assert admin.delete('/admin/model-defaults/supervisor').status_code==200
        events=sql(database,"select payload->>'previous_model_id' as previous from audit_events where event_type='model.default_cleared' and target_id='supervisor'")
        assert events==[{'previous':identity}]
    with demo_client(database,'management') as manager:
        assert not any(row['id']==identity for row in manager.get('/models/allowed').json()['items'])


def test_embedding_dimension_guard(database,monkeypatch):
    from vinhomes_api import v3_models
    monkeypatch.setenv('OPENAI_API_KEY','embedding-test-key')
    class Provider:
        def __init__(self,**kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): return False
        async def post(self,url,headers,json): return httpx.Response(200,json={'data':[{'embedding':[0.1]*768}]})
    monkeypatch.setattr(v3_models.httpx,'AsyncClient',Provider)
    with demo_client(database,'admin') as admin:
        added=admin.post('/admin/model-registry',json={'name':'embed-'+uuid4().hex,'provider':'openai','credential_env':'OPENAI_API_KEY','kind':'embedding','dimension':768})
        assert added.status_code==201,added.text
        identity=added.json()['id']
        assert admin.post('/admin/model-registry/'+identity+'/check').json()['ok']
        assert admin.put('/admin/model-defaults/embedding',json={'model_id':identity}).status_code==409
        assert admin.patch('/admin/model-registry/'+identity,json={'allowed':True}).status_code==422


def test_admin_overview_and_audit_filter_export_agree(database):
    with demo_client(database,'management') as manager:
        assert manager.get('/admin/overview').status_code==403
    identity=str(uuid4())
    sql(database,"""insert into audit_events(tenant_id,initiator_kind,initiator_id,event_type,target_type,target_id,payload,created_at)
        values($1,'system','test-filter','model.checked','model',$2,'{"name":"Filter model","ok":false}',timestamptz '2026-03-02 10:00:00+07') returning id""",TENANT,identity)
    with demo_client(database,'admin') as admin:
        overview=admin.get('/admin/overview')
        assert overview.status_code==200,overview.text
        assert len(overview.json()['requests_per_day'])==14
        expected=sql(database,"select count(*) as count from tickets where tenant_id=$1 and status not in ('closed','cancelled')",TENANT)[0]['count']
        assert overview.json()['open_tickets']==expected
        filters={'from':'2026-03-02','to':'2026-03-02','action':'model.checked','search':'Filter model','result':'failed'}
        events=admin.get('/admin/audit-events',params=filters)
        assert events.status_code==200,events.text
        assert len(events.json()['items'])==1
        assert events.json()['items'][0]['target_label']=='Filter model' and events.json()['items'][0]['result']=='failed'
        exported=admin.get('/admin/audit-events/export',params=filters)
        assert exported.status_code==200,exported.text
        assert len(exported.content.decode('utf-8-sig').splitlines())==2
        assert admin.get('/admin/audit-events',params={**filters,'result':'success'}).json()['items']==[]
