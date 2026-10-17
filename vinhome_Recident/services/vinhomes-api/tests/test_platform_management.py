"""BQL transport, grant and zone isolation on disposable restricted PostgreSQL."""
from uuid import uuid4

from test_platform_mcp_v2 import BOOTSTRAP, call, rpc, handed
from test_resident_contract import TENANT, sql, database
from test_account_administration import door
from vinhomes_api.platform_management import TOOLS, sign_grant, verify_grant


def scoped_ticket(database, ticket):
    sql(database, '''update tickets t set zone_id=z.id,site_id=z.site_id from
        (select id,site_id from zones where tenant_id=$2 order by id limit 1) z where t.id=$1''',ticket,TENANT)
    return sql(database,'select management_unit_id,zone_id,site_id,created_at from tickets where id=$1',ticket)[0]


def test_management_grants_are_bound_revocable_and_do_not_open_ticket_actions(database, handed):
    ticket, ticket_token, _ = handed
    row = scoped_ticket(database,ticket)
    bind = sql(database, '''insert into platform_management_bindings(tenant_id,platform_tenant,platform_domain,platform_area,
        platform_user,management_unit_id,zone_id,site_id) values($1,'test','vinhome','op2','manager-op2',$2,$3,$4) returning id''',
        TENANT,row['management_unit_id'],row['zone_id'],row['site_id'])[0]['id']
    period = {'from_date': '2000-01-01', 'to_date': '2000-02-01'}
    with door(database) as client:
        body = {'platform_tenant':'test','platform_domain':'vinhome','platform_area':'op2',
                'platform_user':'manager-op2','tools':list(TOOLS)}
        assert client.post('/platform/management-grants',json=body).status_code == 401
        assert client.post('/platform/management-grants',headers={'Authorization':'Bearer '+BOOTSTRAP},
                           json={**body,'platform_area':'other'}).status_code == 403
        response = client.post('/platform/management-grants',headers={'Authorization':'Bearer '+BOOTSTRAP},json=body)
        assert response.status_code == 200,response.text
        token = response.json()['bearer_token']
        assert call(client,BOOTSTRAP,TOOLS[1],period,True)['error']['code'] == 'MANAGEMENT_SCOPE_FORBIDDEN'
        assert call(client,ticket_token,TOOLS[1],period,True)['error']['code'] == 'MANAGEMENT_SCOPE_FORBIDDEN'
        assert call(client,token,'vh_ticket_get',{'ticket_id':str(ticket)},True)['error']['code'] == 'TICKET_SCOPE_FORBIDDEN'
        assert call(client,token,TOOLS[1],period)['total'] == 0
        assert call(client,token,TOOLS[0],{**period,'limit':1})['items'] == []
        assert call(client,token,TOOLS[2],period)['total'] == 0
        assert call(client,token,TOOLS[3],period)['groups'] == []
        assert call(client,token,TOOLS[4],{'query':'unmatched-reference'})['items'] == []
        assert call(client,token,TOOLS[5],{})['travel'] == 'mock_only'
        limited = sign_grant(bind,[TOOLS[1]])
        assert call(client,limited,TOOLS[0],period,True)['error']['code'] == 'MANAGEMENT_SCOPE_FORBIDDEN'
        assert verify_grant(sign_grant(bind,[TOOLS[1]],ttl=-1)) is None
        assert verify_grant(token[:-1]+'x') is None
        sql(database,'update platform_management_bindings set active=false where id=$1',bind)
        assert rpc(client,token,'tools/list').status_code == 401


def test_management_queries_match_only_bound_zone(database, handed):
    ticket, _, _ = handed
    row = scoped_ticket(database,ticket)
    bind = sql(database,'''insert into platform_management_bindings(tenant_id,platform_tenant,platform_domain,platform_area,
        platform_user,management_unit_id,zone_id,site_id) values($1,'test','vinhome','op2-2','manager-op2-2',$2,$3,$4) returning id''',
        TENANT,row['management_unit_id'],row['zone_id'],row['site_id'])[0]['id']
    from datetime import timedelta
    start = row['created_at'].date()
    period = {'from_date':start.isoformat(),'to_date':(start+timedelta(days=1)).isoformat()}
    expected = sql(database,'''select count(*) as total from tickets where tenant_id=$1 and management_unit_id=$2
        and zone_id=$3 and created_at >= $4 and created_at < $5''',TENANT,row['management_unit_id'],row['zone_id'],start,start+timedelta(days=1))[0]['total']
    with door(database) as client:
        token = sign_grant(bind,list(TOOLS))
        assert call(client,token,TOOLS[1],period)['total'] == expected
        items = call(client,token,TOOLS[0],{**period,'limit':1})
        assert items['total'] == expected and len(items['items']) == 1
        assert not {'contact_phone','contact_name','description'} & set(items['items'][0])
        assert call(client,token,TOOLS[1],{'from_date':'2026-01-01','to_date':'2026-12-01'},True)['error']['code']=='INVALID_PERIOD'
