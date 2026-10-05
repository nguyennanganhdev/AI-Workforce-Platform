import asyncio
from types import SimpleNamespace
import pytest
from adapters.backend.errors import AdapterError
from groupchat.reception import ReceptionMessage
from persistence.sqlite import DevelopmentStore
from runtime.ingress import DurableIngress
from runtime.service import Continuation, Worker
from tests.adapters.reception.support import input_message
from support.fakes import make_context


async def test_v2_durable_accept_before_ack_and_original_body_conflict(tmp_path):
    ctx=make_context();raw=input_message()
    for key in ('tenant_id','domain_id','workspace_id','ticket_id','ticket_generation'):raw[key]=getattr(ctx,key)
    class Gateway:
        async def resolve(self,msg,authentication):
            if authentication!='verified':raise AdapterError('source_forbidden')
            return SimpleNamespace(verified=SimpleNamespace(context=ctx,message=msg))
    class Delegation:
        async def durable_reference(self,auth,context,identity,digest): return 'stable-backend-source-proof-reference'
    store=DevelopmentStore(tmp_path/'f.sqlite')
    ingress=DurableIngress(Gateway(),None,None,store,Delegation(),{})
    with pytest.raises(AdapterError,match='forbidden'):await ingress.accept('reception',raw,'forged')
    assert await store.claim('w') is None
    receipt=await ingress.accept('reception',raw,'verified')
    assert receipt=={'id':raw['message_id'],'durable':True}
    assert await ingress.accept('reception',raw,'verified')==receipt
    with pytest.raises(AdapterError,match='conflict'): await ingress.accept('reception',raw|{'message':'changed'},'verified')
    restarted=DevelopmentStore(store.path)
    claim=await restarted.claim('w')
    assert claim.payload['wire']==raw and 'verified' not in str(claim.payload)
    assert claim.payload['authentication_ref']=='stable-backend-source-proof-reference'
    with pytest.raises(ValueError):await ingress.accept('reception',raw|{'schema_version':'1.0'},'verified')


async def test_unknown_worker_jobs_are_durable_bounded_and_never_acked(tmp_path):
    now=[100.]
    store=DevelopmentStore(tmp_path/'f.sqlite',clock=lambda:now[0])
    await store.accept('job',{'unknown_remote_attempt':'op'})
    calls=[]
    async def handle(claim):calls.append(claim.fence);return 5
    worker=Worker(store,handle,owner='w',max_attempts=3)
    for _ in range(3):
        assert await worker.once()
        now[0]+=6
    assert not await worker.once()
    assert calls==[1,2,3]
    with store.connection() as db:
        assert db.execute('SELECT status FROM inbox').fetchone()==('blocked',)
        assert db.execute('SELECT count(*) FROM acknowledgements').fetchone()==(0,)


async def test_normal_continuations_survive_recovery_bound_and_restart(tmp_path):
    now = [100.]
    store = DevelopmentStore(tmp_path/'f.sqlite', clock=lambda: now[0])
    await store.accept('job', {'work': 'multiple bounded supervisor slices'})
    fences = []
    async def handle(claim):
        fences.append(claim.fence)
        return Continuation() if len(fences) <= 4 else None
    for _ in range(4):
        worker = Worker(store, handle, owner='w', max_attempts=3)
        assert await worker.once()
        with store.connection() as db:
            assert db.execute('SELECT status FROM inbox').fetchone() == ('pending',)
        now[0] += 6
        store = DevelopmentStore(store.path, clock=lambda: now[0])
    assert await Worker(store, handle, owner='w', max_attempts=3).once()
    assert fences == [1, 2, 3, 4, 5]
    with store.connection() as db:
        assert db.execute('SELECT status FROM inbox').fetchone() == ('done',)


@pytest.mark.parametrize('raises', [False, True])
async def test_recovery_after_continuations_has_its_own_durable_bound(tmp_path, raises):
    now = [100.]
    store = DevelopmentStore(tmp_path/'f.sqlite', clock=lambda: now[0])
    await store.accept('job', {'work': 'yield then reconcile'})
    attempts = []
    async def handle(claim):
        attempts.append((claim.fence, claim.recovery_attempts))
        if len(attempts) <= 4:
            return Continuation()
        if raises:
            raise AdapterError('temporary_failure')
        return 5
    for index in range(7):
        worker = Worker(store, handle, owner='w', max_attempts=3)
        if raises and index >= 4:
            with pytest.raises(AdapterError, match='temporary_failure'):
                await worker.once()
        else:
            assert await worker.once()
        with store.connection() as db:
            assert db.execute('SELECT status FROM inbox').fetchone() == (
                'blocked' if index == 6 else 'pending',)
        now[0] += 6
        store = DevelopmentStore(store.path, clock=lambda: now[0])
    assert attempts == [(1,0),(2,0),(3,0),(4,0),(5,0),(6,1),(7,2)]
    assert not await Worker(store, handle, owner='w').once()
    with store.connection() as db:
        assert db.execute('SELECT count(*) FROM acknowledgements').fetchone() == (0,)


async def test_expired_claim_counts_recovery_without_resetting_fence(tmp_path):
    now = [100.]
    store = DevelopmentStore(tmp_path/'f.sqlite', clock=lambda: now[0])
    await store.accept('job', {'work': 'abandoned owner'})
    first = await store.claim('first', 1)
    now[0] += 2
    store = DevelopmentStore(store.path, clock=lambda: now[0])
    second = await store.claim('second')
    assert (first.fence, first.recovery_attempts) == (1,0)
    assert (second.fence, second.recovery_attempts) == (2,1)
    with pytest.raises(AdapterError, match='stale_fence'):
        await store.defer(first, 5, recovery=True)
    await store.ack(second)


async def test_worker_renews_lease_during_io_and_other_worker_cannot_claim(tmp_path, monkeypatch):
    now=[100.]
    store=DevelopmentStore(tmp_path/'f.sqlite',clock=lambda:now[0])
    other=DevelopmentStore(store.path,clock=lambda:now[0])
    await store.accept('job',{'work':'bounded long I/O'})
    started=asyncio.Event();allow_return=asyncio.Event()
    renewed_past_original_lease=asyncio.Event()
    original_expiry=now[0]+.12
    renew=store.renew
    async def observed_renewal(claim, lease_seconds):
        # Advance the database clock only when the real heartbeat runs. Slow CI scheduling cannot
        # expire a 120 ms lease, but another worker must still be excluded past the original expiry.
        now[0]+=lease_seconds/2
        updated=await renew(claim,lease_seconds)
        if now[0]>original_expiry:
            renewed_past_original_lease.set()
        return updated
    monkeypatch.setattr(store,'renew',observed_renewal)
    async def handler(claim):
        started.set()
        await allow_return.wait()
        await store.put_once('result','job',{'fence':claim.fence})
    worker=Worker(store,handler,owner='first',lease_seconds=.12)
    task=asyncio.create_task(worker.once())
    try:
        await asyncio.wait_for(started.wait(),5)
        await asyncio.wait_for(renewed_past_original_lease.wait(),5)
        assert now[0]>original_expiry
        assert await other.claim('second',.12) is None
        allow_return.set();assert await asyncio.wait_for(task,5)
        assert await other.claim('second') is None
    finally:
        task.cancel()
        await asyncio.gather(task,return_exceptions=True)


async def test_lease_loss_cancels_local_io_and_prevents_late_result(tmp_path):
    now=[100.]
    store=DevelopmentStore(tmp_path/'f.sqlite',clock=lambda:now[0])
    await store.accept('job',{'work':'remote outcome remains unknown'})
    started=asyncio.Event();cancelled=asyncio.Event()
    async def handler(claim):
        started.set()
        try:await asyncio.sleep(1)
        finally:cancelled.set()
        await store.put_once('result','job',{'unsafe':'late'})
    worker=Worker(store,handler,owner='first',lease_seconds=.06)
    task=asyncio.create_task(worker.once());await started.wait()
    now[0]+=1
    takeover=await store.claim('second',1)
    with pytest.raises(AdapterError,match='stale_fence'):await task
    assert cancelled.is_set() and await store.get('result','job') is None
    assert takeover.fence==2
    await store.ack(takeover)
