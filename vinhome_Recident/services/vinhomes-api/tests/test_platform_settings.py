"""Admin configuration against isolated PostgreSQL; no Agent or external provider calls."""
import asyncio
import io
import json
import zipfile
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from test_domain_database import demo_client
from test_resident_contract import TENANT, sql
from test_resident_contract import database as database  # noqa: PLC0414
from test_staff_dispatch import approved_order
from vinhomes_api import platform_settings as settings, platform_sync
from vinhomes_api.platform import Platform

PATH = '/admin/platform-connection'
KEYS = {'customer_key': 'customer-private-key-123456', 'provider_key': 'provider-private-key-123456',
        'signing_key_id': 'sig_test_01', 'signing_secret': 'signing-private-secret-123456'}


@pytest.fixture(autouse=True)
def configuration(database, monkeypatch):
    monkeypatch.setenv('VINHOMES_API_CONFIG_ENCRYPTION_KEY', '18' * 32)
    monkeypatch.setenv('VINHOMES_PLATFORM_ALLOWED_HOSTS', 'platform.test')
    monkeypatch.setenv('VINHOMES_API_PLATFORM_URL', '')
    monkeypatch.setenv('VINHOMES_API_PLATFORM_MCP_TOKEN', 'test-bootstrap-' + 'x' * 40)
    for key in KEYS:
        monkeypatch.delenv('VINHOMES_API_PLATFORM_' + key.upper(), raising=False)
    sql(database, 'DELETE FROM platform_connection_settings')
    sql(database, "UPDATE platform_links SET status='closed',state='closed'")
    calls = []

    def handle(request):
        calls.append(request)
        expected = KEYS['provider_key'] if '/provider/' in request.url.path else KEYS['customer_key']
        if request.headers.get('authorization') != 'ApiKey ' + expected:
            return httpx.Response(401, json={'error': {'code': 'AUTH_FAILED', 'message': 'do not reflect remote secrets'}})
        if '/routes/' in request.url.path:
            body = json.loads(request.content)
            return httpx.Response(200, json={'route_id': request.url.path.split('/')[-2], 'status': 'active',
                'external_management_ref': body['external_management_ref'], 'revision': body['expected_revision'] + 1})
        return httpx.Response(404, json={'error': {'code': 'RESOURCE_NOT_FOUND'}})
    monkeypatch.setattr(settings, 'Platform', lambda bridge: Platform(bridge, transport=httpx.MockTransport(handle)))
    yield calls


def save(c, **changes):
    response = c.put(PATH, json={'version': 0, 'url': 'https://platform.test', **KEYS, **changes})
    assert response.status_code == 200, response.text
    return response.json()


def confirm(c, config):
    ref = config['units'][0]['code']
    response = c.post(PATH + '/routes/confirm', json={'version': config['version'], 'management_ref': ref,
                      'route_id': 'route_test', 'revision': 1})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['units'][0]['route']['revision'] == 2
    return result


def test_only_admin_configures_checks_confirms_and_exports(database):
    for actor in ('management', 'technical'):
        with demo_client(database, actor) as c:
            assert c.get(PATH).status_code == 403
            assert c.put(PATH, json={'version': 0}).status_code == 403
            assert c.post(PATH + '/check', json={'version': 0}).status_code == 403
            assert c.post(PATH + '/mcp-export').status_code == 403
            assert c.post(PATH + '/routes/confirm', json={'version': 1, 'management_ref': 'test', 'route_id': 'route', 'revision': 1}).status_code == 403


def test_save_encrypts_redacts_and_preserves_omitted_credentials(database):
    with demo_client(database, 'admin') as c:
        initial = c.get(PATH)
        assert initial.status_code == 200 and initial.json()['source'] == 'environment'
        assert initial.headers['cache-control'] == 'no-store'
        config = save(c)
        assert config['version'] == 1 and config['source'] == 'admin' and not config['enabled']
        assert all(config['secrets_configured'].values())
        assert all(value not in json.dumps(config) for key, value in KEYS.items() if key != 'signing_key_id')
        stored = sql(database, 'SELECT credentials_ciphertext FROM platform_connection_settings')[0]['credentials_ciphertext']
        assert KEYS['customer_key'] not in stored
        assert settings.decrypt(stored) == KEYS
        kept = c.put(PATH, json={'version': 1, 'url': config['url']})
        assert kept.status_code == 200 and all(kept.json()['secrets_configured'].values())
        assert c.put(PATH, json={'version': 1, 'url': config['url']}).status_code == 409
        events = json.dumps(sql(database, "SELECT payload FROM audit_events WHERE event_type LIKE 'platform_connection.%'"))
        assert all(v not in events for v in KEYS.values())


@pytest.mark.parametrize('url', ['http://public.example.com', 'https://169.254.169.254', 'https://127.0.0.1',
    'https://localhost', 'https://user:password@example.com', 'https://example.com/workforce/v1', 'https://example.com/?key=secret'])
def test_refuse_unsafe_urls_without_reflecting_secrets(database, url):
    with demo_client(database, 'admin') as c:
        response = c.put(PATH, json={'version': 0, 'url': url, 'customer_key': 'short-secret'})
        assert response.status_code == 422
        assert 'short-secret' not in response.text and url not in response.text


def test_check_is_read_only_no_agent_and_wrong_keys_are_not_success(database, configuration):
    with demo_client(database, 'admin') as c:
        checked = c.post(PATH + '/check', json={'version': 0, 'url': 'https://platform.test', **KEYS})
        assert checked.status_code == 200 and checked.json()['ok']
        assert checked.json()['signing'] == 'configured_not_verified'
        assert len(configuration) == 2 and all(r.method == 'GET' for r in configuration)
        assert not sql(database, 'SELECT * FROM platform_connection_settings')
        bad = c.post(PATH + '/check', json={'version': 0, 'url': 'https://platform.test', **KEYS, 'customer_key': 'wrong-private-key-12345'})
        assert bad.status_code == 200 and not bad.json()['ok']
        assert bad.json()['checks'][0]['code'] == 'AUTH_REFUSED'
        assert KEYS['provider_key'] not in bad.text


def test_enable_requires_confirmed_route_and_accepts_returned_revision(database):
    with demo_client(database, 'admin') as c:
        config = save(c)
        assert c.put(PATH, json={'version': config['version'], 'url': config['url'], 'enabled': True}).status_code == 422
        config = confirm(c, config)
        enabled = c.put(PATH, json={'version': config['version'], 'url': config['url'], 'enabled': True})
        assert enabled.status_code == 200, enabled.text
        assert enabled.json()['enabled'] and enabled.json()['last_check']['ok']
        assert c.post(PATH + '/routes/confirm', json={'version': 1, 'management_ref': config['units'][0]['code'], 'route_id': 'test', 'revision': 1}).status_code == 409


def test_active_workflow_blocks_disable_or_retarget(database):
    order, _ = approved_order(database)
    ticket = UUID(order['ticket_id'])
    with demo_client(database, 'admin') as c:
        config = confirm(c, save(c))
        config = c.put(PATH, json={'version': config['version'], 'url': config['url'], 'enabled': True}).json()
        sql(database, """INSERT INTO platform_links(ticket_id,tenant_id,channel_id,user_id,management_ref,status)
          SELECT t.id,t.tenant_id,t.channel_id,t.requester_user_id,mu.code,'open' FROM tickets t
          JOIN management_units mu ON mu.id=t.management_unit_id WHERE t.id=$1""", ticket)
        for changes in ({'enabled': False}, {'url': 'https://another.example.com'}, {'customer_key': 'replacement-private-key-1234'}):
            denied = c.put(PATH, json={'version': config['version'], 'url': config['url'], 'enabled': True, **changes})
            assert denied.status_code == 409
        assert c.get(PATH).json()['enabled']


def test_mcp_export_is_explicit_private_and_audited(database, monkeypatch):
    token = 'bootstrap-private-' + 'x' * 40
    monkeypatch.setenv('VINHOMES_API_PLATFORM_MCP_TOKEN', token)
    monkeypatch.setenv('VINHOMES_API_ALLOWED_ORIGINS', 'https://vinhomes.example.com')
    with demo_client(database, 'admin') as c:
        assert token not in c.get(PATH).text
        exported = c.post(PATH + '/mcp-export')
        assert exported.status_code == 200 and exported.headers['cache-control'] == 'no-store'
        with zipfile.ZipFile(io.BytesIO(exported.content)) as bundle:
            assert token in bundle.read('vinhomes-mcp.secret.env').decode()
            config = json.loads(bundle.read('mcp-server.json'))
            assert config['url'] == 'https://vinhomes.example.com/mcp'
            assert len(config['tools']) == 7 and token not in bundle.read('mcp-server.json').decode()
        assert sql(database, "SELECT id FROM audit_events WHERE event_type='platform_connection.mcp_exported'")


def test_worker_reloads_ui_configuration_without_restart_or_env_changes(database, monkeypatch):
    with demo_client(database, 'admin') as c:
        config = confirm(c, save(c))
        c.put(PATH, json={'version': config['version'], 'url': config['url'], 'enabled': True})
    seen = []
    async def nothing(*args, **kwargs):
        seen.append(platform_sync._run_tenant.get())
        return 0
    for name in ('queue_progress', 'close_ended', 'send_commands', 'read_events', 'send_progress'):
        monkeypatch.setattr(platform_sync, name, nothing)
    async def run():
        engine = create_async_engine(database['runtime'])
        clients, retired = {}, []
        try:
            await platform_sync.configured_pass(engine, clients, retired)
            assert clients[str(TENANT)].bridge.url == 'https://platform.test'
            assert seen == [str(TENANT)] * 5
            async with platform_sync._scoped(engine, str(TENANT)) as db:
                saved = await settings.row(db)
                assert saved['worker_version'] == saved['version'] and saved['worker_seen_at']
                assert await settings.connection_enabled(db)
                assert not await settings.connection_enabled(db, 'unconfirmed-unit')
                await db.execute(text('UPDATE platform_connection_settings SET enabled=false WHERE tenant_id=:tenant'), {'tenant': TENANT})
            await platform_sync.configured_pass(engine, clients, retired)
            assert str(TENANT) not in clients and not retired
        finally:
            for client in clients.values(): await client.aclose()
            await engine.dispose()
    asyncio.run(run())


def test_missing_encryption_key_refuses_write_and_wrong_key_fails_closed(database, monkeypatch):
    with demo_client(database, 'admin') as c:
        monkeypatch.delenv('VINHOMES_API_CONFIG_ENCRYPTION_KEY')
        assert not c.get(PATH).json()['encryption_ready']
        response = c.put(PATH, json={'version': 0, 'url': 'https://platform.test', **KEYS})
        assert response.status_code == 503 and KEYS['customer_key'] not in response.text
        monkeypatch.setenv('VINHOMES_API_CONFIG_ENCRYPTION_KEY', '18' * 32)
        save(c)
        monkeypatch.setenv('VINHOMES_API_CONFIG_ENCRYPTION_KEY', '19' * 32)
        assert c.get(PATH).status_code == 503


def test_settings_follow_tenant_rls(database):
    with demo_client(database, 'admin') as c:
        save(c)
    async def run():
        engine = create_async_engine(database['runtime'])
        try:
            async with platform_sync._scoped(engine, str(TENANT)) as db:
                assert await settings.row(db)
            async with platform_sync._scoped(engine, str(uuid4())) as db:
                assert await settings.row(db) is None
        finally:
            await engine.dispose()
    asyncio.run(run())


def test_public_hostname_resolving_to_metadata_is_rejected(monkeypatch):
    async def run():
        async def lookup(*args, **kwargs):
            return [(2, 1, 6, '', ('169.254.169.254', 443))]
        monkeypatch.setattr(asyncio.get_running_loop(), 'getaddrinfo', lookup)
        with pytest.raises(Exception) as denied:
            await settings.validate_destination('https://public-name.example.com')
        assert denied.value.status_code == 422
    asyncio.run(run())
