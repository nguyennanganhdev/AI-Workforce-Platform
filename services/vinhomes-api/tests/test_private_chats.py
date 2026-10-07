"""Private chat isolation and one-shot external writes under the restricted database role."""
from uuid import uuid4, UUID
from fastapi.testclient import TestClient
from test_resident_contract import TENANT, sql
from test_resident_contract import database as database
from test_v3_agent_database import demo_client
from test_v3_coordination import publish_specialist, TOKEN, SERVICE, BASE
from vinhomes_api.main import create_app
from vinhomes_api.v3_config import V3Settings


def test_private_history_has_no_admin_override_and_replay_preserves_routing(database):
    agent, _ = publish_specialist(database, 'Private adviser '+uuid4().hex, [])
    with demo_client(database, 'management') as manager:
        create = {'room_id':'management-room','request_id':uuid4().hex}
        made = manager.post('/personal-chats',json=create)
        assert made.status_code == 201,made.text
        chat = made.json()['id']
        assert manager.post('/personal-chats',json=create).json()['id']==chat
        message = {'text':'Câu hỏi riêng về tài liệu','mention_agent_id':agent,'client_message_id':uuid4().hex}
        sent = manager.post('/personal-chats/'+chat+'/messages',json=message)
        assert sent.status_code == 201,sent.text
        assert manager.post('/personal-chats/'+chat+'/messages',json=message).json()['id']==sent.json()['id']
        assert manager.post('/personal-chats/'+chat+'/messages',json={**message,'mention_agent_id':None}).status_code==409
        detail = manager.get('/personal-chats/'+chat)
        assert detail.status_code==200,detail.text
        assert any(m['body']['text']==message['text'] for m in detail.json()['messages'])
        assert not any(m['body'].get('text')==message['text'] for m in manager.get('/rooms/management-room/messages').json()['items'])
    with demo_client(database,'admin') as admin:
        assert admin.get('/personal-chats/'+chat).status_code==404
        assert admin.get('/rooms/'+chat+'/messages').status_code==404
        assert not admin.get('/personal-chats').json()['items']
        assert admin.post('/personal-chats',json={'room_id':'management-room','request_id':uuid4().hex}).status_code==403
        assert admin.post('/rooms/management-room/agents',json={'name':'Forbidden author','instructions':'x','idempotency_key':uuid4().hex}).status_code==403
    with demo_client(database,'technical') as staff:
        assert staff.get('/personal-chats/'+chat).status_code==404


def test_source_selection_suspension_exact_confirmation_and_no_replay(database,monkeypatch):
    from vinhomes_api import v3_connections
    called=[]
    async def host(path,payload,**kwargs):
        if path=='/tools': return {'tools':[{'name':'create_event','description':'Tạo lịch với nội dung và thời gian đã chọn','effect':'write','inputSchema':{'type':'object'}}]}
        if path=='/call':
            called.append(payload)
            return {'text':'Lịch đã được tạo.','isError':False,'truncated':False}
        return {'ok':True}
    monkeypatch.setattr(v3_connections,'host',host)
    with demo_client(database,'management') as manager:
        response=manager.post('/rooms/management-room/connections',json={'title':'Calendar '+uuid4().hex[:8],'url':'https://calendar.example/mcp','allowed_tools':['create_event']})
        assert response.status_code==201,response.text
        server=response.json()['id']
    agent,_=publish_specialist(database,'Calendar adviser '+uuid4().hex,[],tools=({'server_id':server,'name':server+'.create_event'},))
    settings=V3Settings('127.0.0.1',8000,database['runtime'],TENANT,None,None,demo_mode=True,coordination_service_token=TOKEN)
    with TestClient(create_app(settings),client=('127.0.0.1',50000),headers={'X-Demo-Actor':'management'}) as manager:
        chat=manager.post('/personal-chats',json={'room_id':'management-room','request_id':uuid4().hex}).json()['id']
        def turn():
            sent=manager.post('/personal-chats/'+chat+'/messages',json={'text':'Tạo lịch họp lúc 18 giờ','mention_agent_id':agent,'client_message_id':uuid4().hex})
            assert sent.status_code==201,sent.text
            snapshot=manager.post(BASE+f"/room-mentions/{sent.json()['id']}/{agent}/turn",headers=SERVICE)
            assert snapshot.status_code==200,snapshot.text
            return snapshot.json()
        snapshot=turn()
        args={'title':'Họp cư dân','starts_at':'2026-10-08T18:00:00+07:00'}
        call={'run_id':snapshot['run_id'],'tool':server+'.create_event','arguments':args}
        assert manager.post(BASE+'/tools/call',headers=SERVICE,json=call).json()['status']=='FORBIDDEN'
        assert not called
        enabled=manager.put('/personal-chats/'+chat+'/sources',json={'server_id':server,'enabled':True})
        assert enabled.status_code==200,enabled.text
        waiting=manager.post(BASE+'/tools/call',headers=SERVICE,json=call)
        assert waiting.status_code==200,waiting.text
        assert waiting.json()['status']=='AWAITING_CONFIRMATION' and not called
        confirmation=waiting.json()['data']['confirmation']['id']
        row=sql(database,'select arguments,status from vh_external_call_confirmations where id=$1',UUID(confirmation))[0]
        assert row['status']=='pending'
        with demo_client(database,'admin') as admin:
            assert admin.post('/rooms/'+chat+'/external-calls/'+confirmation+'/decision',json={'decision':'approve'}).status_code==404
            assert admin.patch('/admin/connections/'+server+'/status',json={'status':'suspended','reason':'Kiểm tra an toàn'}).status_code==200
        endpoint='/rooms/'+chat+'/external-calls/'+confirmation+'/decision'
        assert manager.post(endpoint,json={'decision':'approve'}).status_code==403 and not called
        with demo_client(database,'admin') as admin:
            assert admin.patch('/admin/connections/'+server+'/status',json={'status':'active'}).status_code==200
        done=manager.post(endpoint,json={'decision':'approve'})
        assert done.status_code==200,done.text
        assert done.json()['status']=='succeeded' and called[0]['arguments']==args and len(called)==1
        assert manager.post(endpoint,json={'decision':'approve'}).status_code==409 and len(called)==1
        assert any(c['status']=='succeeded' and c['id']==confirmation for c in manager.get('/rooms/'+chat+'/external-calls').json()['items'])
