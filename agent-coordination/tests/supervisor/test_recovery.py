import asyncio
from copy import deepcopy

import pytest
from supervisor.models import Reconciliation, SupervisorError
from supervisor.service import prepare_decision
from supervisor.models import DECISION


async def pending_plan(rig, proposal):
    await rig.start()
    s = await rig.state()
    _, opened = await rig.h.open()
    s.room = opened.data
    prepare_decision(s, DECISION.validate_python(proposal), await rig.authority.inspect(s), rig.service.clock())
    await rig.service._save(s, s.version)
    return await rig.state()


async def test_crash_before_dispatch_replays_saved_decision_not_model(rig, proposal):
    s = await pending_plan(rig, proposal)
    wire = deepcopy(s.action.wire)
    s = await rig.resume()
    assert s.phase == 'waiting_management'
    assert rig.model.calls == 0 and rig.transport.calls == [wire]
    await rig.resume()
    assert len(rig.transport.calls) == 1


async def test_timeout_unknown_requires_lookup_then_same_payload_key(rig, proposal):
    await pending_plan(rig, proposal)
    rig.transport.failure = TimeoutError()
    s = await rig.resume()
    assert s.action.status == 'unknown'
    wire = deepcopy(s.action.wire)
    await rig.resume()
    assert len(rig.transport.calls) == 1 and rig.authority.reconcile_calls == 1
    rig.authority.resolution = Reconciliation(outcome='not_applied')
    rig.transport.failure = None
    s = await rig.resume()
    assert s.phase == 'waiting_management' and s.action is None
    assert rig.transport.calls == [wire, wire]


async def test_crash_after_backend_commit_recovers_receipt_without_resend(rig, proposal):
    s = await pending_plan(rig, proposal)
    s.action.status = 'sending'
    await rig.service._save(s, s.version)
    rig.authority.resolution = Reconciliation(outcome='receipt', receipt={
        'request_id': s.action.action_id, 'status': 'accepted', 'data': {'operation_id': 'committed'}})
    s = await rig.resume()
    assert not rig.transport.calls and s.action is None
    assert s.approvals['management_plan'].decision is None


async def test_two_workers_claim_one_action(rig, proposal):
    await pending_plan(rig, proposal)
    results = await asyncio.gather(rig.resume(), rig.resume(), return_exceptions=True)
    assert len(rig.transport.calls) == 1
    assert all(not isinstance(r, Exception) or isinstance(r, SupervisorError) for r in results)


async def test_event_during_unknown_is_not_acknowledged(rig, proposal):
    await pending_plan(rig, proposal)
    rig.transport.failure = TimeoutError()
    s = await rig.resume()
    a = s.approvals['management_plan']
    d = rig.delivery('approval.responded', {'approval_id': a.approval_id, 'stage': a.stage,
        'plan_id': a.plan_id, 'plan_version': a.plan_version, 'decision': 'approve'})
    with pytest.raises(SupervisorError, match='action_pending'):
        await rig.service.handle_delivery(d, 'verified-worker')
    assert (rig.ctx.tenant_id, d.event_id) not in rig.store.acks


async def test_revoked_context_prevents_pending_dispatch(rig, proposal):
    await pending_plan(rig, proposal)
    rig.authority.allowed = False
    s = await rig.resume()
    assert not rig.transport.calls and s.action.status == 'pending'
    assert s.pause_reason == 'forbidden'


async def test_aggregate_ordering_is_not_global(rig):
    await rig.start()
    await rig.send('resident.message', {'text': 'one'}, aggregate='a', version=50)
    await rig.send('resident.message', {'text': 'two'}, aggregate='b', version=1)
    with pytest.raises(SupervisorError, match='stale_event'):
        await rig.send('resident.message', {'text': 'old'}, aggregate='a', version=49)
    assert len((await rig.state()).feedback) == 2


async def test_serializable_checkpoint_and_atomic_ack(rig):
    await rig.start()
    s = await rig.state()
    from supervisor.models import SupervisorState
    assert SupervisorState.model_validate_json(s.model_dump_json()) == s
    old_version = s.version
    await rig.send('resident.message', {'text': 'change'})
    s.version += 1
    assert not await rig.store.commit(s, old_version, delivery_id='must-not-ack')
    assert (rig.ctx.tenant_id, 'must-not-ack') not in rig.store.acks


async def test_two_independent_rooms_have_separate_journals(rig, proposal):
    from tests.supervisor.conftest import Rig
    from support.fakes import make_context
    other = Rig()
    other.ctx = make_context('TEST-2')
    other.h.ctx = other.ctx
    other.verifier.context = other.ctx
    other.authority.context = other.ctx
    await asyncio.gather(pending_plan(rig, proposal), pending_plan(other, proposal))
    await asyncio.gather(rig.resume(), other.resume())
    assert rig.transport.calls[0]['idempotency_key'] != other.transport.calls[0]['idempotency_key']
    assert rig.transport.calls[0]['context']['ticket_id'] == 'TEST-1'
    assert other.transport.calls[0]['context']['ticket_id'] == 'TEST-2'


async def test_cancellation_retains_sending_fence(rig, proposal):
    await pending_plan(rig, proposal)
    original = rig.backend.dispatch
    async def cancel(action):
        raise asyncio.CancelledError()
    rig.backend.dispatch = cancel
    with pytest.raises(asyncio.CancelledError):
        await rig.resume()
    assert (await rig.state()).action.status == 'sending'
    rig.backend.dispatch = original
    await rig.resume()
    assert not rig.transport.calls and rig.authority.reconcile_calls == 1
