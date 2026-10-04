"""Real PostgreSQL restart, fencing and concurrent quota checks in a throwaway database."""
import asyncio
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from adapters.backend.errors import AdapterError
from persistence.budget import Budget
from persistence.postgres import PostgreSQLStore
from supervisor.models import SupervisorState
from support.fakes import make_context


@pytest.fixture
def postgres_url():
    def env(name):
        path = Path(__file__).resolve().parents[3] / 'services/vinhomes-api/.local-v3-faker' / name
        return dict(line.split('=', 1) for line in path.read_text().splitlines() if line and not line.startswith('#')) if path.exists() else {}
    admin = os.getenv('COORDINATION_TEST_ADMIN_URL') or env('migration.env').get('DATABASE_URL')
    runtime = os.getenv('COORDINATION_TEST_URL') or env('api.env').get('VINHOMES_API_DATABASE_URL')
    if not admin or not runtime:
        pytest.skip('Local PostgreSQL test URLs are required')
    admin = admin.replace('postgresql+asyncpg:', 'postgresql:')
    runtime = runtime.replace('postgresql+asyncpg:', 'postgresql:')
    if any(urlsplit(url).hostname not in ('localhost', '127.0.0.1', '::1') for url in (admin, runtime)):
        pytest.fail('These tests only create a disposable database on local PostgreSQL')
    name = 'coordination_test_' + uuid4().hex
    with psycopg.connect(runtime) as db:
        role, elevated = db.execute('SELECT current_user,(rolsuper OR rolbypassrls) FROM pg_roles WHERE rolname=current_user').fetchone()
        assert not elevated, 'Exercise a restricted runtime role'
    with psycopg.connect(admin, autocommit=True) as db:
        db.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(name), sql.Identifier(role)))
    try:
        yield urlunsplit(urlsplit(runtime)._replace(path='/' + name))
    finally:
        assert name.startswith('coordination_test_') and len(name) == len('coordination_test_') + 32
        with psycopg.connect(admin, autocommit=True) as db:
            db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))


async def test_checkpoint_cas_and_inbox_fences_survive_another_process(postgres_url):
    time = [100.0]
    a, b = (PostgreSQLStore(postgres_url, clock=lambda: time[0]) for _ in range(2))
    context = make_context()
    state = SupervisorState(context=context, groupchat_version_id='group', turn_policy={})
    assert await a.commit(state, None)
    assert (await b.load(context)) == state
    first = state.model_copy(deep=True)
    first.version = 1
    assert await b.commit(first, 0)
    assert not await a.commit(first, 0)
    assert await a.accept('one', {'message': 'data'})
    assert not await b.accept('one', {'message': 'data'})
    with pytest.raises(AdapterError, match='conflict'):
        await b.accept('one', {'message': 'changed'})
    lease = await a.claim('a', 1)
    assert await b.claim('b', 1) is None
    time[0] += 2
    takeover = await b.claim('b', 30)
    assert takeover.fence == lease.fence + 1
    with pytest.raises(AdapterError, match='stale_fence'):
        with a.lease_scope(lease):
            await a.put_once('effect', 'one', {'stale': True})
    await b.ack(takeover)
    restarted = PostgreSQLStore(postgres_url, clock=lambda: time[0])
    assert await restarted.claim('restart') is None
    a.save_cursor('cursor-1')
    assert restarted.cursor() == 'cursor-1'


async def test_concurrent_workers_cannot_exceed_the_session_budget(postgres_url):
    from concurrent.futures import ThreadPoolExecutor
    a, b = PostgreSQLStore(postgres_url), PostgreSQLStore(postgres_url)
    async def reserve(store, call):
        try:
            await Budget(store, scope='session', token_limit=100).reserve(call, 60)
            return 'reserved'
        except AdapterError as error:
            return error.code
    with ThreadPoolExecutor(2) as pool:
        results = await asyncio.gather(
            asyncio.wrap_future(pool.submit(asyncio.run, reserve(a, 'a'))),
            asyncio.wrap_future(pool.submit(asyncio.run, reserve(b, 'b'))))
    assert sorted(results) == ['budget_exhausted', 'reserved']
    with a.connection() as db:
        assert db.execute('SELECT SUM(bound) FROM ledger').fetchone()[0] == 60
