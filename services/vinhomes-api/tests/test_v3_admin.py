"""What the platform administrator reads: units, the models at work, the audit trail."""
import httpx
from uuid import UUID, uuid4
from test_resident_contract import sql, TENANT
from test_resident_contract import (
    database as database,  # noqa: PLC0414 -- pytest fixture export
)
from test_v3_agent_database import demo_client


def test_only_an_administrator_reads_the_units_the_models_and_the_trail(database, monkeypatch):
    from vinhomes_api import v3_admin
    asked = []

    class Services:
        def __init__(self, **options): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *error): return False
        async def get(self, url):
            asked.append(url)
            if 'coordination' in url:
                return httpx.Response(200, json={'status': 'ok', 'model': 'gemini-3.8-flash', 'provider': 'google', 'specialist_model': 'gpt-5.5'})
            raise httpx.ConnectError('down')

    monkeypatch.setenv('VINHOMES_API_COORDINATION_URL', 'http://coordination.test')
    monkeypatch.setenv('FACTORY_SERVICE_URL', 'http://factory.test')
    monkeypatch.setattr(v3_admin.httpx, 'AsyncClient', Services)
    with demo_client(database, 'management') as management:
        for path in ('/admin/units', '/admin/models', '/admin/audit-events'):
            assert management.get(path).status_code == 403
    with demo_client(database, 'admin') as admin:
        units = admin.get('/admin/units').json()['items']
        assert units and all(set(u) >= {'name', 'buildings', 'groups', 'staff', 'open_tickets'} for u in units)
        assert any(u['buildings'] and u['groups'] and u['groups'][0]['members'] >= 1 for u in units)
        roles = {m['role']: m for m in admin.get('/admin/models').json()['items']}
        assert roles['supervisor'] == {'role': 'supervisor', 'configured': True, 'running': True, 'model': 'gemini-3.8-flash', 'provider': 'google'}
        assert roles['specialist']['model'] == 'gpt-5.5'
        # A service that does not answer is reported as down, not as an error of this screen.
        assert roles['factory'] == {'role': 'factory', 'configured': True, 'running': False, 'model': None, 'provider': None}
        assert roles['reception']['configured'] is False and set(roles) == {'reception', 'supervisor', 'specialist', 'factory', 'embedding'}
        assert asked == ['http://coordination.test/health', 'http://factory.test/health']
        # Reading a connection list leaves no trail; creating an account or an agent does. Any event will do here.
        trail = admin.get('/admin/audit-events?limit=5').json()
        assert len(trail['items']) <= 5 and trail['kinds'] == sorted(trail['kinds'])
        if trail['items']:
            kind = trail['items'][0]['event_type'].split('.')[0]
            only = admin.get(f'/admin/audit-events?kind={kind}').json()['items']
            assert only and all(e['event_type'].startswith(kind) for e in only)
            older = admin.get('/admin/audit-events', params={'before': trail['items'][-1]['created_at']}).json()['items']
            assert all(e['created_at'] < trail['items'][-1]['created_at'] for e in older)
        assert admin.get('/admin/audit-events?kind=Agent;drop').status_code == 422
        # The trail of a span of days leaves as a file a spreadsheet opens, and taking it is itself recorded.
        sql(database, """insert into audit_events(tenant_id,initiator_kind,initiator_id,event_type,target_type,target_id,payload,created_at)
            values($1,'system','=cmd|calc','export.test','test','t','{"ghi chú": "Đạt"}',timestamptz '2026-03-02 10:00:00+07') returning id""", TENANT)
        assert admin.get('/admin/audit-events/export?from=2026-03-03&to=2026-03-02').status_code == 422
        assert admin.get('/admin/audit-events/export?to=2026-03-02').status_code == 422
        sheet = admin.get('/admin/audit-events/export?from=2026-03-02&to=2026-03-02&kind=export')
        assert sheet.status_code == 200 and sheet.headers['content-type'] == 'text/csv; charset=utf-8'
        assert sheet.headers['content-disposition'] == 'attachment; filename="nhat-ky-2026-03-02-2026-03-02.csv"'
        lines = sheet.content.decode('utf-8-sig').splitlines()
        assert lines[0].startswith('Thời điểm (giờ Việt Nam),Sự kiện,Người hoặc agent') and len(lines) == 2
        # Việt Nam time, the text as it is, and a name that looks like a formula written as text.
        assert lines[1] == '2026-03-02 10:00:00,export.test,\'=cmd|calc,system,test,t,"{""ghi chú"": ""Đạt""}"'
        assert len(admin.get('/admin/audit-events/export?from=2026-03-03&to=2026-03-03&kind=export').content.decode('utf-8-sig').splitlines()) == 1
        taken = sql(database, "select target_id,payload::text from audit_events where event_type='audit.exported' order by created_at")
        assert taken[0]['target_id'] == '2026-03-02..2026-03-02' and '"rows": 1' in taken[0]['payload']
    with demo_client(database, 'management') as management:
        assert management.get('/admin/audit-events/export?from=2026-03-02&to=2026-03-02').status_code == 403


def test_admin_creates_unit_room_and_supervisor_atomically(database):
    building = uuid4()
    sql(database, """insert into buildings(id,tenant_id,site_id,code,name,status)
        select $1,$2,id,$3,'New managed building','active' from sites where tenant_id=$2 limit 1""",
        building, TENANT, 'new-' + building.hex)
    with demo_client(database, 'admin') as c:
        options = c.get('/admin/unit-options')
        assert options.status_code == 200, options.text
        category = options.json()['categories'][0]['id']
        body = {'code': 'new-' + uuid4().hex, 'name': 'Ban quản lý mới',
                'building_ids': [str(building)], 'category_ids': [category]}
        with demo_client(database, 'management') as manager:
            assert manager.post('/admin/units', json=body).status_code == 403
            assert manager.get('/admin/unit-options').status_code == 403
        invalid = {**body, 'building_ids': [str(uuid4())]}
        assert c.post('/admin/units', json=invalid).status_code == 422
        assert not sql(database, 'select id from management_units where code=$1', body['code'])
        response = c.post('/admin/units', json=body)
        assert response.status_code == 201, response.text
        unit = response.json()
        assert c.post('/admin/units', json=body).status_code == 409
        assert c.post('/admin/units', json={**body, 'code': 'overlap-' + uuid4().hex}).status_code == 409
        assert c.post('/admin/units', json={**body, 'building_ids': [str(building)] * 2}).status_code == 422
        detail = next(u for u in c.get('/admin/units').json()['items'] if u['id'] == unit['id'])
        assert detail['buildings'] == ['New managed building']
        assert detail['groups'][0]['members'] == 1
        agents = c.get(f"/rooms/{unit['room_id']}/agents")
        assert agents.status_code == 200, agents.text
        assert any(a['purpose'] == 'supervisor' for a in agents.json()['items'])
        preset = sql(database, "select id,status,configuration from agents where workspace_id=$1 and name='Agent Báo cáo'", UUID(unit['workspace_id']))
        assert len(preset) == 1 and preset[0]['status'] == 'draft'
        import json
        configuration = json.loads(preset[0]['configuration'])
        assert configuration['preset'] == 'report-agent-v2'
        assert len(configuration['mcp_tools']) == 4
        assert len(sql(database, 'select id from management_coverage where management_unit_id=$1', UUID(unit['id']))) == 1
        assert sql(database, "select id from audit_events where event_type='management_unit.created' and target_id=$1", unit['id'])


def test_external_event_filters_and_timestamp_tie_pagination(database):
    marker=uuid4().hex
    for event in ('external-source-used','external-write-requested','external-write-decided'):
        sql(database, """insert into audit_events(tenant_id,initiator_kind,initiator_id,event_type,target_type,target_id,payload,created_at)
            values($1,'person','local-v3-management',$2,'mcp_server',$3,'{}',timestamptz '2026-03-04 10:00:00+07') returning id""",TENANT,event,marker)
    sql(database, """insert into audit_events(tenant_id,initiator_kind,initiator_id,event_type,target_type,target_id,payload,created_at)
        select $1,'system','cursor-test','pagination.checked','test',$2,'{}',timestamptz '2026-03-04 12:00:00+07' from generate_series(1,55) returning id""",TENANT,marker)
    with demo_client(database,'admin') as admin:
        for event in ('external-source-used','external-write-requested','external-write-decided'):
            filters={'kind':event,'search':marker,'from':'2026-03-04','to':'2026-03-04'}
            response=admin.get('/admin/audit-events',params=filters)
            assert response.status_code==200,response.text
            assert [item['event_type'] for item in response.json()['items']]==[event]
            exported=admin.get('/admin/audit-events/export',params=filters)
            assert exported.status_code==200,exported.text
            assert len(exported.content.decode('utf-8-sig').splitlines())==2
        filters={'kind':'pagination','search':marker,'limit':50}
        first=admin.get('/admin/audit-events',params=filters).json()['items']
        assert len(first)==50
        cursor={'before':first[-1]['created_at'],'before_id':first[-1]['id']}
        next_page=admin.get('/admin/audit-events',params={**filters,**cursor})
        assert next_page.status_code==200,next_page.text
        remaining=next_page.json()['items']
        assert len(remaining)==5 and len({item['id'] for item in first+remaining})==55
        # Old clients retain the strictly earlier timestamp behavior.
        assert admin.get('/admin/audit-events',params={**filters,'before':cursor['before']}).json()['items']==[]
        assert admin.get('/admin/audit-events',params={'before_id':cursor['before_id']}).status_code==422
