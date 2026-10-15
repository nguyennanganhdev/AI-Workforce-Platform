"""Regression for ticket receipt isolation on the public MCP endpoint; no model calls."""
from uuid import uuid4
from test_resident_contract import database as database
from test_account_administration import door
from test_platform_mcp_v2 import handed as handed, call, version


def test_mcp_only_changes_handed_over_tickets_and_binds_receipts_to_payload(database,handed):
    ticket,token,_=handed
    with door(database) as client:
        args={'ticket_id':str(ticket),'client_reference':str(uuid4()),'note':'Th?ng tin c? d?n b? sung.','expected_ticket_version':version(database,ticket)}
        assert call(client,token,'vh_ticket_add_note',args)['status']=='confirmed'
        assert call(client,token,'vh_ticket_add_note',args)['status']=='confirmed'
        assert call(client,token,'vh_ticket_add_note',{**args,'note':'N?i dung kh?c'},True)['error']['code']=='REFERENCE_CONFLICT'
        assert call(client,token,'vh_ticket_add_note',{**args,'ticket_id':str(uuid4())},True)['error']['code']=='TICKET_SCOPE_FORBIDDEN'
