"""Deletion refusals preserve external confirmations and connected credentials."""
from uuid import UUID, uuid4
from test_resident_contract import TENANT, sql
from test_resident_contract import database as database
from test_v3_agent_database import demo_client
from test_v3_coordination import publish_specialist


def test_admin_delete_keeps_confirmation_history_and_linked_accounts(database,monkeypatch):
    from vinhomes_api import v3_connections
    async def host(path,payload,**kwargs):
        if path=='/seal': return {'sealed':'test-sealed-key'}
        if path=='/tools': return {'tools':[{'name':'write_event','description':'Create event','effect':'write','inputSchema':{'type':'object'}}]}
        return {'ok':True}
    monkeypatch.setattr(v3_connections,'host',host)
    agent,version=publish_specialist(database,'History keeper '+uuid4().hex,[])
    with demo_client(database,'admin') as admin:
        made=admin.post('/admin/connections',json={'title':'Historical calendar '+uuid4().hex[:8],'url':'https://calendar.example/mcp','token':'test-key','allowed_tools':['write_event']})
        assert made.status_code==201,made.text
        identity=made.json()['id']
        credential=sql(database,'select credential_id from mcp_servers where id=$1',identity)[0]['credential_id']
        confirmation=sql(database,"""insert into vh_external_call_confirmations(tenant_id,actor_user_id,channel_id,agent_id,version_id,connection_id,tool_name,arguments,arguments_hash,status)
            values($1,'local-v3-management','management-room',$2,$3,$4,$5,'{}','test-hash','cancelled') returning id""",TENANT,agent,UUID(version),identity,identity+'.write_event')[0]['id']
        with demo_client(database,'management') as manager:
            assert manager.delete('/admin/connections/'+identity).status_code==403
        refused=admin.delete('/admin/connections/'+identity)
        assert refused.status_code==409 and 'lịch sử xác nhận' in refused.json()['detail'],refused.text
        assert sql(database,'select id from vh_external_call_confirmations where id=$1',confirmation)
        assert sql(database,'select name from mcp_tools where server_id=$1',identity)
        assert sql(database,'select revoked_at from credentials where id=$1',credential)[0]['revoked_at'] is None
        assert admin.patch('/admin/connections/'+identity+'/status',json={'status':'suspended','reason':'Ngừng sử dụng, giữ lịch sử'}).status_code==200
        assert sql(database,'select status from mcp_servers where id=$1',identity)[0]['status']=='suspended'
        assert not sql(database,"select id from audit_events where target_id=$1 and event_type='connection.removed'",identity)
        linked=admin.post('/admin/connections',json={'title':'Linked calendar '+uuid4().hex[:8],'url':'https://calendar.example/mcp','token':'test-key'})
        assert linked.status_code==201,linked.text
        server=linked.json()['id']
        key=sql(database,'select credential_id from mcp_servers where id=$1',server)[0]['credential_id']
        sql(database,"""insert into mcp_user_credentials(tenant_id,server_id,user_id,credential_id,scope)
            values($1,$2,'local-v3-management',$3,'calendar') returning server_id""",TENANT,server,key)
        response=admin.delete('/admin/connections/'+server)
        assert response.status_code==409 and 'tài khoản xác thực' in response.json()['detail'],response.text
        assert sql(database,'select credential_id from mcp_user_credentials where server_id=$1',server)[0]['credential_id']==key


def test_session_external_authority_uses_exact_question_pin(monkeypatch):
    import asyncio
    import pytest
    from fastapi import HTTPException
    from vinhomes_api import v3_connections, v3_session_sources
    version_id, session_id, message_id=uuid4(),uuid4(),uuid4()
    checked=[]
    class Result:
        def __init__(self,row): self.row=row
        def first(self): return self.row
        def mappings(self): return self
    class Database:
        async def execute(self,statement,args):
            query=str(statement)
            if "kind='personal'" in query: return Result(None)
            if 'from mcp_tools' in query: return Result({'effect':'write','destructive':False,'description':'Create event'})
            raise AssertionError('Session authority must not choose the latest room release')
    async def room(*args,**kwargs): return {'workspace_id':'workspace'}
    async def server(*args,**kwargs): return {'id':'calendar','status':'active','workspace_id':'workspace','credential_id':None,'sealed':None}
    async def authority(db,actor,channel,agent,connection,session,message):
        checked.append((actor,channel,agent,connection,session,message))
        return {'id':version_id,'config':{'mcp_tools':[{'server_id':'calendar','name':'calendar.create_event'}]}}
    monkeypatch.setattr(v3_connections,'managed_room',room)
    monkeypatch.setattr(v3_connections,'connection',server)
    monkeypatch.setattr(v3_session_sources,'session_confirmation_authority',authority)
    db=Database()
    _,_,version=asyncio.run(v3_connections.external_authority(db,'manager','room','agent','calendar','calendar.create_event',session_id=session_id,request_message_id=message_id,version_id=version_id))
    assert version['id']==version_id and checked==[('manager','room','agent','calendar',session_id,message_id)]
    with pytest.raises(HTTPException) as partial:
        asyncio.run(v3_connections.external_authority(db,'manager','room','agent','calendar','calendar.create_event',session_id=session_id))
    assert partial.value.status_code==422
    with pytest.raises(HTTPException) as mismatch:
        asyncio.run(v3_connections.external_authority(db,'manager','room','agent','calendar','calendar.create_event',session_id=session_id,request_message_id=message_id,version_id=uuid4()))
    assert mismatch.value.status_code==403


def test_registry_usage_counts_published_pins_when_the_draft_changes(database,monkeypatch):
    from vinhomes_api import v3_connections
    async def host(path,payload,**kwargs):
        if path=='/tools': return {'tools':[{'name':'search','description':'Search handbook','inputSchema':{'type':'object'}}]}
        return {'ok':True}
    monkeypatch.setattr(v3_connections,'host',host)
    suffix=uuid4().hex[:8]
    with demo_client(database,'admin') as admin:
        old=admin.post('/admin/connections',json={'title':'Pinned handbook '+suffix,'url':'https://handbook.example/mcp','allowed_tools':['search'],'read_tools':['search']})
        new=admin.post('/admin/connections',json={'title':'Draft handbook '+suffix,'url':'https://draft.example/mcp','allowed_tools':['search'],'read_tools':['search']})
        assert old.status_code==new.status_code==201
        live,draft=old.json()['id'],new.json()['id']
    name='Pinned source reader '+suffix
    agent,version=publish_specialist(database,name,[],tools=({'server_id':live,'name':live+'.search'},))
    # Draft configuration can remove the live source and add a different one. The
    # release still executes its pinned version until the next publication.
    sql(database, """update agents set configuration=jsonb_set(configuration,'{mcp_tools}',
        jsonb_build_array(jsonb_build_object('server_id',$2::text,'name',$2::text||'.search'))) where id=$1 returning id""",agent,draft)
    with demo_client(database,'admin') as admin:
        listing=admin.get('/admin/connections')
        assert listing.status_code==200,listing.text
        items={item['id']:item for item in listing.json()['items']}
        assert items[live]['usage_agents']==[{'id':agent,'name':name}]
        assert items[draft]['usage_agents']==[]
        # The usage column agrees with the delete guard based on published grants.
        assert admin.delete('/admin/connections/'+live).status_code==409
        assert admin.post('/admin/agents/'+agent+'/release/revoke',json={'note':'End source usage regression'}).status_code==200
        items={item['id']:item for item in admin.get('/admin/connections').json()['items']}
        assert items[live]['usage_agents']==items[draft]['usage_agents']==[]
