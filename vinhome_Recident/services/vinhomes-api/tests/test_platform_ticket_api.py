"""MCP protocol and domain authorization only: no Agent, model, or platform server."""
import json
from uuid import uuid4

from test_resident_contract import TENANT, sql, database as database
from test_account_administration import door

TOKEN='isolated-mcp-business-test-token-0123456789'


def test_mcp_only_changes_handed_over_tickets_and_binds_receipts_to_payload(database,monkeypatch):
    monkeypatch.setenv('VINHOMES_API_PLATFORM_MCP_TOKEN',TOKEN)
    monkeypatch.setenv('VINHOMES_API_PLATFORM_URL','')
    ticket=sql(database,"select id from tickets where tenant_id=$1 and status in ('open','triaging') order by created_at limit 1",TENANT)[0]['id']
    headers={'Authorization':'Bearer '+TOKEN,'Accept':'application/json, text/event-stream'}
    with door(database) as client:
        def call(name,arguments):
            response=client.post('/mcp',headers=headers,json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':name,'arguments':arguments}})
            assert response.status_code==200,response.text
            body=response.json()
            assert not body.get('error') and not body['result'].get('isError'),body
            answer=body['result']['content'][0]['text']
            try:return json.loads(answer)
            except json.JSONDecodeError:return answer
        assert 'ticket_id' in call('vh_ticket_get',{'ticket_id':str(ticket)})  # unlinked ticket is refused
        sql(database,"""insert into platform_links(ticket_id,tenant_id,channel_id,user_id,management_ref)
            select t.id,t.tenant_id,t.channel_id,t.requester_user_id,mu.code from tickets t
            join management_units mu on mu.id=t.management_unit_id and mu.tenant_id=t.tenant_id where t.id=$1""",ticket)
        assert call('vh_ticket_get',{'ticket_id':str(ticket)})['ticket_status'] in {'open','triaging'}
        reference=str(uuid4())
        args={'ticket_id':str(ticket),'client_reference':reference,'note':'Cư dân bổ sung thông tin kiểm thử.'}
        assert call('vh_ticket_add_note',args)=={'status':'confirmed'}
        assert call('vh_ticket_add_note',args)=={'status':'confirmed'}
        changed=call('vh_ticket_add_note',{**args,'note':'Nội dung khác với reference đã dùng.'})
        assert changed['status']=='failed' and 'nội dung khác' in changed['reason']
        wrong=call('vh_ticket_add_note',{**args,'ticket_id':str(uuid4())})
        assert wrong['status']=='failed'
        sql(database,"update platform_links set status='closed' where ticket_id=$1",ticket)
        assert call('vh_ticket_add_note',args)=={'status':'confirmed'}  # replay returns receipt, no new write
        assert call('vh_ticket_add_note',{**args,'client_reference':str(uuid4())})['status']=='failed'
        assert sql(database,"select count(*) as n from ticket_events where ticket_id=$1 and event_type='ticket.note_added'",ticket)[0]['n']==1
