"""Resident UX contracts on disposable PostgreSQL; no Agent or provider calls."""
from uuid import uuid4

from test_resident_contract import database as database, client, sql, CATEGORY  # noqa: F401
from test_domain_database import delegate, resident_message


def test_recoverable_chat_removal_preserves_messages_and_rejects_other_actors(database):
    with client(database) as c:
        chat,message=resident_message(c,"UX archive")
        unit=c.get('/resident/me').json()['units'][0]
        ticket=c.post(f'/resident/chats/{chat}/tickets',headers={'Idempotency-Key':str(uuid4())},json={
            'domain_id':unit['domain_id'],'building_id':unit['building_id'],'unit_id':unit['id'],
            'category_id':CATEGORY,'title':'Vòi bếp rò nước','description':'Vòi nước dưới bồn rửa bị rò.',
            'contact_name':'Cư dân kiểm thử','contact_phone':'0900000000','location':'Phòng bếp','request_kind':'incident'})
        assert ticket.status_code==201,ticket.text
        snapshot=c.get('/resident/tickets/'+ticket.json()['id']).json()
        url=f"/resident/chats/{chat}"
        assert c.delete(url).json()=={"archived":True}
        assert c.delete(url).status_code==200
        assert chat not in {r['id'] for r in c.get('/resident/chats').json()['items']}
        assert chat in {r['id'] for r in c.get('/resident/chats?archived=true').json()['items']}
        assert c.get(url+'/messages').json()['items'][0]['id']==message
        assert c.get('/resident/tickets/'+ticket.json()['id']).json()==snapshot
        with client(database,actor='security') as other:
            assert other.delete(url).status_code in (403,404)
            assert other.post(url+'/restore').status_code in (403,404)
        assert c.post(url+'/restore').json()=={"archived":False}
        assert chat in {r['id'] for r in c.get('/resident/chats').json()['items']}
        assert sql(database,'select deleted_at from channels where id=$1',chat)[0]['deleted_at'] is None


def test_public_activity_and_persisted_citations_are_bound_to_the_turn(database,monkeypatch):
    monkeypatch.setenv('RECEPTION_DELEGATION_KEY','ab'*32)
    with client(database) as c:
        chat,message=resident_message(c,"UX activity")
        endpoint=f"/resident/chats/{chat}/turn-state"
        assert c.get(endpoint).json()['status']=='queued'
        token=delegate(c,chat,message)['token']
        headers={'Authorization':'Bearer '+token}
        progress=f"/internal/reception/chats/{chat}/progress"
        assert c.post(progress,json={'stage':'searching'}).status_code==401
        assert c.post(progress,headers=headers,json={'stage':'searching','prompt':'private'}).status_code==422
        assert c.post(progress,headers=headers,json={'stage':'arbitrary_thought'}).status_code==422
        assert c.post(progress,headers=headers,json={'stage':'searching'}).status_code==200
        state=c.get(endpoint).json()
        assert state['status']=='processing' and state['steps'][0]['stage']=='searching'
        assert set(state['steps'][0])=={'stage','at'}
        other,_=resident_message(c,"Other chat")
        assert c.post(f'/internal/reception/chats/{other}/progress',headers=headers,json={'stage':'context'}).status_code==403
        body={'text':'Thông tin tham khảo.','reply_to_id':message,'latency_ms':1500,
              'citations':[{'title':'Tiện ích','excerpt':'Thông tin từ tài liệu.','status':'reference'}]}
        reply=c.post(f'/internal/reception/chats/{chat}/replies',headers=headers,json=body)
        assert reply.status_code==201,reply.text
        assert c.post(f'/internal/reception/chats/{chat}/replies',headers=headers,json=body).json()==reply.json()
        assert c.get(endpoint).json()['status']=='completed'
        items=c.get(f'/resident/chats/{chat}/messages').json()['items']
        assert items[-1]['reply_to_id']==message
        info=items[-1]['body']['reception']
        assert info['latencyMs']==1500 and info['citations'][0]['status']=='reference'
        assert info['steps'][0]['stage']=='searching'
        notices=[n for n in c.get('/my/notifications').json()['items'] if n['message_id']==reply.json()['id']]
        assert len(notices)==1 and notices[0]['channel_id']==chat and notices[0]['read_at'] is None
        assert c.post(f'/resident/chats/{chat}/read',json={'sequence':items[-1]['seq']}).status_code==200
        assert next(n for n in c.get('/my/notifications').json()['items'] if n['id']==notices[0]['id'])['read_at']


def test_read_notifications_only_marks_explicit_owned_ids(database):
    with client(database) as c:
        chat,_=resident_message(c,"Notifications")
        # Seed delivery rows only; no request or provider is invoked.
        ids=[uuid4(),uuid4()]
        for id in ids:
            sql(database,"""insert into notification_deliveries(id,tenant_id,user_id,channel,dedupe_key,payload,status,available_at)
                values($1,'11111111-1111-5111-a111-111111111111','local-v3-resident','in_app',$2,'{}','pending',now()) returning id""",id,str(id))
        foreign=uuid4()
        sql(database,"""insert into notification_deliveries(id,tenant_id,user_id,channel,dedupe_key,payload,status,available_at)
            values($1,'11111111-1111-5111-a111-111111111111','local-v3-security','in_app',$2,'{}','pending',now()) returning id""",foreign,str(foreign))
        assert c.post('/my/notifications/read',json={'ids':[str(foreign)]}).json()['items']==[]
        assert sql(database,'select read_at from notification_deliveries where id=$1',foreign)[0]['read_at'] is None
        before=c.get('/my/notifications').json()['unreadCount']
        result=c.post('/my/notifications/read',json={'ids':[str(ids[0]),str(uuid4())]})
        assert result.status_code==200,result.text
        assert len(result.json()['items'])==1
        after=c.get('/my/notifications').json()
        assert after['unreadCount']==before-1
        records={n['id']:n for n in after['items']}
        assert records[str(ids[0])]['read_at'] and records[str(ids[1])]['read_at'] is None
        assert c.post('/my/notifications/read',json={'ids':[]}).status_code==422
        assert c.post('/my/notifications/read',json={'ids':[str(uuid4())]*101}).status_code==422
