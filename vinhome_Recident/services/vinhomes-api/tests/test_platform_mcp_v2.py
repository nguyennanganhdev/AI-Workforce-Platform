"""Disposable PostgreSQL and MCP transport checks; no Agent/model/embedding calls."""
import asyncio
import hashlib
import json
from datetime import datetime,timedelta,timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from test_resident_contract import TENANT,sql,database as database
from test_account_administration import door,sign_in
from vinhomes_api.platform_access import TOOLS
from vinhomes_api.password_auth import password_hash

BOOTSTRAP='isolated-mcp-bootstrap-discovery-token-0123456789'


@pytest.fixture
def handed(database,monkeypatch):
    monkeypatch.setenv('VINHOMES_API_PLATFORM_MCP_TOKEN',BOOTSTRAP)
    monkeypatch.setenv('VINHOMES_API_PLATFORM_URL','')
    monkeypatch.setenv('VINHOMES_API_MCP_ALLOWED_HOSTS','testserver')
    ticket=sql(database,"select id from tickets where tenant_id=$1 and status in ('open','triaging') order by created_at limit 1",TENANT)[0]['id']
    sql(database,"""insert into platform_links(ticket_id,tenant_id,channel_id,user_id,management_ref)
        select t.id,t.tenant_id,t.channel_id,t.requester_user_id,mu.code from tickets t
        join management_units mu on mu.id=t.management_unit_id and mu.tenant_id=t.tenant_id where t.id=$1
        on conflict(ticket_id) do update set status='open'""",ticket)
    token='vhm_'+str(uuid4())
    grant=sql(database,"""insert into platform_mcp_grants(tenant_id,ticket_id,management_ref,token_hash,tools,expires_at)
        select tenant_id,ticket_id,management_ref,$2,$3,now()+interval '1 hour' from platform_links where ticket_id=$1 returning id""",
        ticket,hashlib.sha256(token.encode()).hexdigest(),list(TOOLS))[0]['id']
    return ticket,token,grant


def rpc(client,token,method,params=None):
    return client.post('/mcp',headers={'Authorization':'Bearer '+token,'Accept':'application/json, text/event-stream'},
                       json={'jsonrpc':'2.0','id':1,'method':method,'params':params or {}})


def call(client,token,name,args,failed=False):
    response=rpc(client,token,'tools/call',{'name':name,'arguments':args})
    assert response.status_code==200,response.text
    data=response.json();assert 'error' not in data,data
    result=data['result'];assert bool(result.get('isError'))==failed,result
    value=json.loads(result['content'][0]['text'])
    assert result['structuredContent']==value
    assert value['schema_version']=='vinhomes-mcp-v2' and value['correlation_id']
    if failed:assert value['error']['code'] and isinstance(value['error']['retryable'],bool)
    return value


def version(database,ticket):
    return sql(database,'select version from tickets where id=$1',ticket)[0]['version']


def test_bootstrap_is_discovery_only_and_catalog_has_seven_tools(database,handed):
    ticket,token,_=handed
    with door(database) as client:
        tools=rpc(client,BOOTSTRAP,'tools/list').json()['result']['tools']
        assert {t['name'] for t in tools}==set(TOOLS)
        assert 'confirmation' in next(t for t in tools if t['name']=='vh_ticket_get')['outputSchema']['properties']
        assert call(client,BOOTSTRAP,'vh_ticket_get',{'ticket_id':str(ticket)},True)['error']['code']=='TICKET_GRANT_REQUIRED'
        result=call(client,token,'vh_ticket_get',{'ticket_id':str(ticket)})
        assert result['ticket_id']==str(ticket) and result['ticket_version']==version(database,ticket)
        assert not result['confirmation']['ticket_closed']


@pytest.mark.parametrize('change',["revoked_at=now()","expires_at=now()-interval '1 second'"])
def test_revoked_or_expired_bearer_is_denied(database,handed,change):
    _,token,grant=handed
    sql(database,'update platform_mcp_grants set '+change+' where id=$1',grant)
    with door(database) as client:
        assert rpc(client,token,'tools/list').status_code==401


def test_grants_bind_ticket_route_tools_and_revalidate(database,handed):
    ticket,token,grant=handed
    with door(database) as client:
        assert call(client,token,'vh_ticket_get',{'ticket_id':str(uuid4())},True)['error']['code']=='TICKET_SCOPE_FORBIDDEN'
        sql(database,'update platform_mcp_grants set tools=$2 where id=$1',grant,['vh_ticket_get'])
        assert call(client,token,'vh_ticket_add_note',{'ticket_id':str(ticket),'client_reference':str(uuid4()),'note':'Kiểm thử'},True)['error']['code']=='TICKET_SCOPE_FORBIDDEN'
        sql(database,"update platform_mcp_grants set management_ref='other-route' where id=$1",grant)
        assert rpc(client,token,'tools/list').status_code==401


def test_cas_receipts_payload_conflict_and_replay_after_close(database,handed):
    ticket,token,_=handed
    with door(database) as client:
        args={'ticket_id':str(ticket),'client_reference':str(uuid4()),'note':'Cư dân bổ sung thông tin kiểm thử.'}
        assert call(client,token,'vh_ticket_add_note',args,True)['error']['code']=='TICKET_VERSION_REQUIRED'
        assert call(client,token,'vh_ticket_add_note',{**args,'expected_ticket_version':version(database,ticket)+1},True)['error']['code']=='STALE_TICKET_VERSION'
        args['expected_ticket_version']=version(database,ticket)
        assert call(client,token,'vh_ticket_add_note',args)['status']=='confirmed'
        assert call(client,token,'vh_ticket_add_note',args)['status']=='confirmed'
        assert call(client,token,'vh_ticket_add_note',{**args,'note':'Nội dung khác'},True)['error']['code']=='REFERENCE_CONFLICT'
        sql(database,"update platform_links set status='closed' where ticket_id=$1",ticket)
        assert call(client,token,'vh_ticket_add_note',args)['status']=='confirmed'
        assert call(client,token,'vh_ticket_add_note',{**args,'client_reference':str(uuid4())},True)['status']=='failed'


def test_cancel_requires_correct_resident_source(database,handed):
    ticket,token,_=handed
    with door(database) as client:
        args={'ticket_id':str(ticket),'client_reference':str(uuid4()),'reason':'Cư dân muốn hủy.','expected_ticket_version':version(database,ticket)}
        assert call(client,token,'vh_ticket_cancel',args,True)['error']['code']=='RESIDENT_SOURCE_REQUIRED'
        assert call(client,token,'vh_ticket_cancel',{**args,'source_message_id':str(uuid4())},True)['error']['code']=='RESIDENT_SOURCE_FORBIDDEN'


def test_history_is_bounded_and_pages_do_not_repeat(database,handed):
    from vinhomes_api.work_offers import agent_event
    from vinhomes_api.platform import platform_client
    ticket,token,_=handed
    async def make_history():
        engine=create_async_engine(database['runtime'])
        try:
            async with engine.begin() as db:
                await db.execute(text("select set_config('app.tenant_id',:tenant,true)"),{'tenant':str(TENANT)})
                await platform_client(db)
                for _ in range(110):await agent_event(db,ticket,'platform','ticket.note_added',{'note':'Thử phân trang'})
        finally:await engine.dispose()
    asyncio.run(make_history())
    with door(database) as client:
        first=call(client,token,'vh_ticket_get',{'ticket_id':str(ticket)})
        cursor=first['history_page']['next_before_seq'];assert cursor
        next_page=call(client,token,'vh_ticket_get',{'ticket_id':str(ticket),'history_before_seq':cursor})
        assert len(first['milestones'])<=100
        assert not ({e['seq'] for e in first['milestones']} & {e['seq'] for e in next_page['milestones']})


def test_future_shift_lookup_is_not_a_reservation(database,handed):
    ticket,token,_=handed
    at=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
    with door(database) as client:
        result=call(client,token,'vh_staff_available',{'ticket_id':str(ticket),'appointment_at':at})
        assert result['checked_for']==at and result['reservation_confirmed'] is False
        assert result['availability_basis']=='shift_at_requested_time_and_current_load'


def test_transport_enforces_payload_and_per_grant_rate_limits(database,handed):
    _,token,_=handed
    with door(database) as client:
        assert client.post('/mcp',headers={'Authorization':'Bearer '+token},content=b'x'*(256*1024+1)).status_code==413
        for _ in range(120):
            response=rpc(client,token,'tools/list')
            if response.status_code==429:break
        assert response.status_code==429 and response.headers['retry-after']=='60'


def test_untrusted_host_is_denied_even_with_valid_bearer(database,handed):
    _,token,_=handed
    with door(database) as client:
        response=client.post('/mcp',headers={'Authorization':'Bearer '+token,'Host':'untrusted.example','Accept':'application/json, text/event-stream'},
                             json={'jsonrpc':'2.0','id':1,'method':'tools/list'})
        assert response.status_code in (400,403,421)


def test_platform_backend_automatically_gets_a_bound_grant_without_human_approval(database,handed):
    ticket,_,_=handed
    command=sql(database,"insert into platform_commands(tenant_id,ticket_id,kind,body) values($1,$2,'start_workflow','{\"text\":\"Fixture handover\"}') returning id",TENANT,ticket)[0]['id']
    body={'ticket_id':str(ticket),'external_request_id':str(command),'workflow_id':'fixture-workflow',
          'grant_request_id':str(uuid4()),'tools':['vh_ticket_get'],'ttl_seconds':3600}
    with door(database) as client:
        path='/platform/mcp-grants'
        assert client.post(path,json=body).status_code==401
        headers={'Authorization':'Bearer '+BOOTSTRAP}
        first=client.post(path,headers=headers,json=body)
        assert first.status_code==200,first.text
        issued=first.json();assert first.headers['cache-control']=='no-store'
        assert client.post(path,headers=headers,json=body).json()==issued
        assert client.post(path,headers=headers,json={**body,'tools':['vh_ticket_add_note']}).status_code==409
        assert client.post(path,headers=headers,json={**body,'grant_request_id':str(uuid4()),'external_request_id':str(uuid4())}).status_code==409
        scoped=call(client,issued['bearer_token'],'vh_ticket_get',{'ticket_id':str(ticket)})
        assert scoped['policy']['actions']['vh_work_order_dispatch']['allowed'] is False
        sql(database,"update platform_links set workflow_id='fixture-workflow' where ticket_id=$1",ticket)
        assert call(client,issued['bearer_token'],'vh_ticket_get',{'ticket_id':str(ticket)})['ticket_id']==str(ticket)
        sql(database,"update platform_links set workflow_id='different-workflow' where ticket_id=$1",ticket)
        assert rpc(client,issued['bearer_token'],'tools/list').status_code==401
        sql(database,'update platform_links set workflow_id=null where ticket_id=$1',ticket)


def run_domain(database,fn):
    async def run():
        engine=create_async_engine(database['runtime'])
        try:
            async with engine.begin() as db:
                await db.execute(text("select set_config('app.tenant_id',:tenant,true)"),{'tenant':str(TENANT)})
                return await fn(db)
        finally:await engine.dispose()
    return asyncio.run(run())


def test_sla_risk_is_deduplicated_and_uses_existing_text_contract(database,handed):
    from vinhomes_api.jobs import sweep_tenant
    ticket,_,_=handed
    sql(database,"update tickets set created_at=now()-interval '10 days',resolution_due_at=now()-interval '1 day' where id=$1",ticket)
    # Fixture restored to an active bridge by handed; this tests only local queue writes.
    run_domain(database,sweep_tenant);run_domain(database,sweep_tenant)
    notices=sql(database,"select kind,body from platform_commands where ticket_id=$1 and body ? 'domain_notice_key'",ticket)
    assert any(r['kind']=='workflow_reply' and 'sla:breached:' in json.loads(r['body'])['domain_notice_key'] for r in notices)


def test_security_emergency_is_handed_over_once_without_granting_dispatch(database,monkeypatch):
    from vinhomes_api.platform import link_ticket
    monkeypatch.setenv('VINHOMES_API_PLATFORM_URL','http://platform.invalid')
    monkeypatch.setenv('VINHOMES_API_PLATFORM_MCP_TOKEN',BOOTSTRAP)
    monkeypatch.setenv('VINHOMES_API_MCP_ALLOWED_HOSTS','testserver')
    ticket=sql(database,"select id from tickets where tenant_id=$1 and status in ('open','triaging') order by created_at limit 1",TENANT)[0]['id']
    sql(database,"""update tickets set request_kind='incident',is_emergency=true,priority='critical',severity='critical',category_id=(
        select id from service_categories where tenant_id=$2 and code='security') where id=$1""",ticket,TENANT)
    async def hand_over(db):
        await link_ticket(db,ticket)
        await link_ticket(db,ticket)
    run_domain(database,hand_over)
    commands=sql(database,"select id,body from platform_commands where ticket_id=$1 and kind='start_workflow'",ticket)
    assert len(commands)==1
    assert 'category_code: security' in json.loads(commands[0]['body'])['text']
    body={'ticket_id':str(ticket),'external_request_id':str(commands[0]['id']),'workflow_id':'security-session',
          'grant_request_id':str(uuid4()),'tools':list(TOOLS),'ttl_seconds':3600}
    with door(database) as client:
        response=client.post('/platform/mcp-grants',headers={'Authorization':'Bearer '+BOOTSTRAP},json=body)
        assert response.status_code==200,response.text
        token=response.json()['bearer_token']
        snapshot=call(client,token,'vh_ticket_get',{'ticket_id':str(ticket)})
        policy=snapshot['policy']['actions']['vh_work_order_dispatch']
        assert policy['allowed'] is False and policy['blocked_reason']=='EMERGENCY_REQUIRES_ESCALATION'
        result=call(client,token,'vh_work_order_dispatch',{'ticket_id':str(ticket),'client_reference':str(uuid4()),
            'description':'Điều động bảo vệ kiểm thử.','expected_ticket_version':snapshot['ticket_version']},True)
        assert result['error']['code']=='EMERGENCY_REQUIRES_ESCALATION'
    assert sql(database,'select count(*) as n from work_orders where ticket_id=$1',ticket)[0]['n']==0


def test_knowledge_tool_preserves_source_review_evidence(database,handed,monkeypatch):
    import vinhomes_api.platform_work as work
    ticket,token,_=handed
    review={'status':'reference','issues':['not_reviewed']}
    expected_site=sql(database,'select site_id from tickets where id=$1',ticket)[0]['site_id']
    async def search(*args,site_id=None):
        assert site_id==expected_site
        return {'hits':[{'title':'Dịch vụ','documentId':'doc','versionId':'v1','chunkId':'chunk',
                         'section':'Dịch vụ','text':'Thông tin tham khảo.','unverified':False,'provenance':review}]}
    monkeypatch.setattr(work,'search',search)
    with door(database) as client:
        result=call(client,token,'vh_knowledge_search',{'ticket_id':str(ticket),'query':'dịch vụ cư dân'})
        assert result['passages'][0]['provenance']==review
