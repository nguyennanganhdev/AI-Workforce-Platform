import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import pytest
from groupchat.models import AgentOutput,RoomError,ScopeState
from groupchat.room import RoomService
from persistence.sqlite import DevelopmentStore
from support.harness import Harness


class ObservedStore(DevelopmentStore):
    in_transaction=False
    @asynccontextmanager
    async def transaction(self,context):
        async with super().transaction(context) as state:
            self.in_transaction=True
            try: yield state
            finally: self.in_transaction=False


async def test_room_remote_preparation_outside_transaction_and_durable_replay(tmp_path):
    h=Harness();store=ObservedStore(tmp_path/'room.sqlite')
    resolver=h.resolver
    for name in ('authorize','resolve','invocation_run'):
        original=getattr(resolver,name)
        async def checked(*args,_original=original,**kwargs):
            assert not store.in_transaction
            return await _original(*args,**kwargs)
        setattr(resolver,name,checked)
    for name in ('prepare','invoke','cancel'):
        original=getattr(h.agents,name)
        async def checked(*args,_original=original,**kwargs):
            assert not store.in_transaction
            return await _original(*args,**kwargs)
        setattr(h.agents,name,checked)
    h.service=RoomService(resolver,h.agents,store)
    _,opened=await h.open()
    command=h.turn(opened.data)
    done=await h.service.execute(command)
    assert done.status=='completed'
    restarted=RoomService(resolver,h.agents,DevelopmentStore(store.path))
    replay=await restarted.execute(command)
    assert replay.data==done.data and len(h.agents.calls)==1


async def test_child_run_preparation_retry_has_stable_operation_id(tmp_path):
    h=Harness();store=DevelopmentStore(tmp_path/'room.sqlite');h.service=RoomService(h.resolver,h.agents,store)
    _,opened=await h.open();command=h.turn(opened.data)
    ids=[];original=h.resolver.invocation_run
    async def child(ctx,room,participant,op):
        ids.append(op)
        return await original(ctx,room,participant,op)
    h.resolver.invocation_run=child
    h.agents.preflight_fail=True
    assert (await h.service.execute(command)).error.code=='MAPPING_MISSING'
    h.agents.preflight_fail=False
    assert (await h.service.execute(command)).status=='completed'
    assert len(ids)==2 and ids[0]==ids[1]
    assert len(h.agents.calls)==1


async def test_two_room_workers_same_command_invoke_once(tmp_path):
    h=Harness();a=DevelopmentStore(tmp_path/'room.sqlite');b=DevelopmentStore(a.path)
    h.service=RoomService(h.resolver,h.agents,a)
    _,opened=await h.open();command=h.turn(opened.data);h.agents.delay=.05
    other=RoomService(h.resolver,h.agents,b)
    one,two=await asyncio.gather(h.service.execute(command),other.execute(command))
    assert one.status in ('completed','accepted') and two.status in ('completed','accepted')
    assert len(h.agents.calls)==1
    async with b.transaction(h.ctx) as state:
        assert state.fence==1 and state.snapshot.turns_used==1
