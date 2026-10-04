"""What the platform administrator reads: units, the models at work, the audit trail."""
import httpx
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
