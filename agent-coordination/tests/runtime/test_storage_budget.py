import asyncio
import json
import os
import subprocess
import sys

import pytest
from adapters.backend.errors import AdapterError
from persistence.sqlite import DevelopmentStore
from persistence.budget import Budget
from supervisor.models import SupervisorState
from support.fakes import make_context


async def test_restart_cas_and_two_instances(tmp_path):
    path=tmp_path/'framework.sqlite'
    a,b=DevelopmentStore(path),DevelopmentStore(path)
    ctx=make_context()
    state=SupervisorState(context=ctx,groupchat_version_id='group',turn_policy={})
    assert await a.commit(state,None,delivery_id='event')
    loaded=await b.load(ctx)
    assert loaded==state
    first=loaded.model_copy(deep=True);first.version=1;first.question_draft='Còn rò nước không?'
    second=loaded.model_copy(deep=True);second.version=1;second.question_draft='other worker'
    results=await asyncio.gather(a.commit(first,0),b.commit(second,0))
    assert results==[True,False]
    assert (await DevelopmentStore(path).load(ctx)).question_draft=='Còn rò nước không?'
    # A separate Python process reads committed checkpoint, not a process-local fake.
    program="from persistence.sqlite import DevelopmentStore; from groupchat.models import Context; import asyncio,json,sys; s=asyncio.run(DevelopmentStore(sys.argv[1]).load(Context.model_validate_json(sys.argv[2]))); print(s.model_dump_json())"
    result=subprocess.run([sys.executable,'-c',program,str(path),ctx.model_dump_json()],
        capture_output=True,text=True,check=True,env={**os.environ,'PYTHONPATH':str(__import__('pathlib').Path(__file__).resolve().parents[2]/'src')})
    assert json.loads(result.stdout)['version']==1
    with a.connection() as db:
        assert db.execute('SELECT * FROM acknowledgements').fetchall()==[(ctx.tenant_id,'event')]
    assert not await a.commit(second,0,delivery_id='loser')
    with a.connection() as db: assert not db.execute('SELECT 1 FROM acknowledgements WHERE id=?',('loser',)).fetchone()


async def test_durable_accept_conflict_lease_takeover_and_stale_ack(tmp_path):
    time=[100.]
    a=DevelopmentStore(tmp_path/'f.sqlite',clock=lambda:time[0])
    b=DevelopmentStore(tmp_path/'f.sqlite',clock=lambda:time[0])
    assert await a.accept('tenant:event',{'version':1})
    assert not await b.accept('tenant:event',{'version':1})
    with pytest.raises(AdapterError,match='conflict'): await b.accept('tenant:event',{'version':2})
    first=await a.claim('worker-a',1)
    assert await b.claim('worker-b',1) is None
    time[0]=102
    second=await b.claim('worker-b',1)
    assert second.fence==first.fence+1
    with pytest.raises(AdapterError,match='stale_fence'): await a.ack(first)
    await b.ack(second)
    assert await a.claim('worker-a') is None


async def test_room_storage_rollback_and_production_rejection(tmp_path):
    store=DevelopmentStore(tmp_path/'f.sqlite')
    ctx=make_context()
    with pytest.raises(RuntimeError):
        async with store.transaction(ctx) as state:
            state.fence=10
            raise RuntimeError('crash')
    async with store.transaction(ctx) as state: assert state.fence==0
    with pytest.raises(ValueError): DevelopmentStore(tmp_path/'prod.sqlite',mode='production')


async def test_budget_atomic_unknown_restart_and_replay(tmp_path):
    store=DevelopmentStore(tmp_path/'f.sqlite')
    a=Budget(store,scope='tenant/run',token_limit=100)
    b=Budget(DevelopmentStore(store.path),scope='tenant/run',token_limit=100)
    await a.reserve('a',70)
    with pytest.raises(AdapterError,match='budget_exhausted'): await b.reserve('b',31)
    await a.reconcile('a')
    await b.reconcile('a')  # identical reconcile does not double count
    with pytest.raises(AdapterError,match='model_attempt_already_reserved'): await b.reserve('a',70)
    with pytest.raises(AdapterError,match='budget_exhausted'): await b.reserve('b',31)
    with store.connection() as db:
        row=db.execute('SELECT used,cost,status FROM ledger').fetchone()
    assert row==(None,None,'usage_unknown_cost_unknown')


async def test_budget_prices_are_pinned_and_upper_bounds(tmp_path):
    store=DevelopmentStore(tmp_path/'f.sqlite')
    budget=Budget(store,scope='s',token_limit=1000,cost_limit='.10',price_version='test-v1',price_per_token='.001')
    await budget.reserve('a',80)
    with pytest.raises(AdapterError,match='budget_exhausted'): await budget.reserve('b',21)
    await budget.reconcile('a',tokens=20)
    await budget.reserve('b',80)
    await budget.reconcile('b')
    with store.connection() as db:
        assert db.execute('SELECT used,cost,status FROM ledger WHERE id=?',('b',)).fetchone()==(None,'0.080','usage_unknown_estimated')
    with pytest.raises(AdapterError,match='usage_conflict'): await budget.reconcile('a',tokens=21)
    no_price=Budget(store,scope='unknown',token_limit=100,cost_limit=1,price_version='v1')
    with pytest.raises(AdapterError,match='cost_unknown'): await no_price.reserve('c',1)


async def test_expired_worker_cannot_write_checkpoint_or_journal(tmp_path):
    time=[100.]
    store=DevelopmentStore(tmp_path/'f.sqlite',clock=lambda:time[0])
    await store.accept('job',{'ticket':'t'})
    claim=await store.claim('worker-a',1)
    state=SupervisorState(context=make_context(),groupchat_version_id='group',turn_policy={})
    with store.lease_scope(claim):
        assert await store.commit(state,None)
        time[0]=102
        state.version=1
        with pytest.raises(AdapterError,match='stale_fence'): await store.commit(state,0)
        with pytest.raises(AdapterError,match='stale_fence'): await store.put_once('receipt','op',{'done':True})
    assert (await store.load(state.context)).version==0


async def test_two_separate_worker_processes_only_one_claim(tmp_path):
    path=tmp_path/'f.sqlite'
    store=DevelopmentStore(path);await store.accept('job',{'ticket':'example'})
    program="from persistence.sqlite import DevelopmentStore;import asyncio,json,sys;from dataclasses import asdict;c=asyncio.run(DevelopmentStore(sys.argv[1]).claim(sys.argv[2]));print(json.dumps(asdict(c) if c else None))"
    def invoke_worker(owner):
        result=subprocess.run([sys.executable,'-c',program,str(path),owner],capture_output=True,text=True,check=True)
        return json.loads(result.stdout)
    results=await asyncio.gather(asyncio.to_thread(invoke_worker,'a'),asyncio.to_thread(invoke_worker,'b'))
    assert sum(value is not None for value in results)==1
    assert next(value for value in results if value)['fence']==1


async def test_tenant_quota_covers_two_runs_supervisor_and_specialist(tmp_path):
    from persistence.budget import ScopedBudgets
    store=DevelopmentStore(tmp_path/'f.sqlite')
    registry=ScopedBudgets(store,token_limit=100,tenant_token_limit=150)
    a=registry.for_scope(make_context('A'));b=registry.for_scope(make_context('B'))
    await a.reserve('supervisor-a',90)
    await a.reconcile('supervisor-a')
    with pytest.raises(AdapterError,match='tenant_budget_exhausted'):await b.reserve('specialist-b',61)
    await b.reserve('specialist-b',60)
    # Same run quota is shared across model and tool continuations.
    with pytest.raises(AdapterError,match='budget_exhausted'):await registry.for_scope(make_context('A')).reserve('repair-a',11)
