"""The pieces that let several processes share one database and one Redis (slice P5b): the setting, the bus whose locks
name their holder, the nudge that crosses processes, the fleet's count of open streams, the queue of a tenant's
evaluations, and the refusal to run two processes without a shared bus.

The tests that need a real Redis are skipped unless AWP_TEST_REDIS_URL is set (a Redis the tests may flush).
"""
from __future__ import annotations

import asyncio
import os
import time

import pytest
from agentscope.app.message_bus import InMemoryMessageBus, MessageBusKeys

import dbtest
from conftest import build
from awp.bus import FleetBus, build_bus, holder_of, new_node
from awp.config import Settings
from awp.db import Database
from awp.workforce import nodes
from awp.workforce.errors import WorkforceError
from awp.workforce.stream import Slots
from awp.workforce.waker import Waker, relay

REDIS_URL = os.environ.get("AWP_TEST_REDIS_URL", "").strip()
needs_redis = pytest.mark.skipif(not REDIS_URL, reason="needs AWP_TEST_REDIS_URL (a Redis the tests may flush)")


# ---- the setting -----------------------------------------------------------------------------------------------------
def test_the_bus_is_in_memory_unless_a_redis_url_is_set():
    assert Settings.from_env({}).redis_url == "" and Settings.from_env({}).wf_lease_seconds == 60.0
    s = Settings.from_env({"AWP_REDIS_URL": " redis://:pw@redis:6379/0 ", "AWP_WF_LEASE_SECONDS": "20"})
    assert s.redis_url == "redis://:pw@redis:6379/0" and s.wf_lease_seconds == 20.0
    assert isinstance(build_bus("", "n1"), InMemoryMessageBus)
    bus = build_bus(s.redis_url, "n1")
    assert isinstance(bus, FleetBus) and bus.node == "n1"


def test_a_redis_that_does_not_answer_stops_the_start_with_a_plain_reason(tmp_path):
    with pytest.raises(RuntimeError, match="AWP_REDIS_URL is set but Redis does not answer"):
        with build(tmp_path, redis_url="redis://127.0.0.1:1/0"):
            pass


def test_the_holder_of_a_lock_is_read_from_its_value_and_anything_else_is_nobodys():
    node = new_node()
    assert node.startswith("n") and len(node) == 17 and new_node() != node
    assert holder_of(f"{node}:abc") == node and holder_of(f"{node}:abc".encode()) == node
    for foreign in ("1", "", None, "c0ffee", "x:y", f"{node}:", ":tok"):  # AgentScope's own tokens, try_lock's "1"
        assert holder_of(foreign) is None


# ---- one process without a shared bus ---------------------------------------------------------------------------------
def test_a_second_process_without_a_shared_bus_refuses_to_start_next_to_one_that_lives(tmp_path):
    async def go():
        db = Database(dbtest.urls(tmp_path)[0].url)
        await db.create_all()
        try:
            await nodes.enter(db, "nfirst", 2.0, shared_bus=False)

            async def lives():
                for _ in range(40):
                    await asyncio.sleep(0.1)
                    await nodes.beat(db, "nfirst", 2.0, [])
            beating = asyncio.create_task(lives())
            with pytest.raises(RuntimeError, match="another platform process is running on this database"):
                await nodes.enter(db, "nsecond", 2.0, shared_bus=False)
            assert not await nodes.alive(db, "nsecond")
            await nodes.enter(db, "nthird", 2.0, shared_bus=True)  # with a bus they share, both may run
            assert await nodes.living(db) == {"nfirst", "nthird"}
            beating.cancel()
        finally:
            await db.dispose()
    asyncio.run(go())


def test_a_process_that_died_is_waited_out_for_its_lease_and_then_the_next_one_starts(tmp_path):
    async def go():
        db = Database(dbtest.urls(tmp_path)[0].url)
        await db.create_all()
        try:
            await nodes.enter(db, "ndead", 1.5, shared_bus=False)  # and it never beats again
            began = time.monotonic()
            await nodes.enter(db, "nnext", 1.5, shared_bus=False)
            assert 1.0 < time.monotonic() - began < 6.0
            assert await nodes.living(db) == {"nnext"} and await nodes.dead(db) == ["ndead"]
            await nodes.leave(db, "nnext")
            assert await nodes.living(db) == set()
        finally:
            await db.dispose()
    asyncio.run(go())


def test_a_beat_after_the_others_buried_this_process_says_so_and_marks_it_again(tmp_path):
    async def go():
        db = Database(dbtest.urls(tmp_path)[0].url)
        await db.create_all()
        try:
            await nodes.enter(db, "nme", 5.0, shared_bus=True)
            assert await nodes.beat(db, "nme", 5.0, []) is True
            await nodes.leave(db, "nme")  # what burying does to the row
            assert await nodes.beat(db, "nme", 5.0, []) is False and await nodes.alive(db, "nme")
        finally:
            await db.dispose()
    asyncio.run(go())


# ---- the nudge between processes --------------------------------------------------------------------------------------
def test_a_nudge_in_one_process_wakes_the_readers_of_the_others_and_does_not_come_back():
    async def go():
        bus = InMemoryMessageBus()  # one bus, two "processes" with a waker each
        one, two = Waker(), Waker()
        async with bus, relay(bus, "n1", True, one), relay(bus, "n2", True, two):
            await asyncio.sleep(0.05)  # both subscriptions are up
            with one.watch("conv") as here, two.watch("conv") as there, two.watch("other") as elsewhere:
                one.poke("conv")
                await asyncio.wait_for(there.wait(), 2)
                assert here.is_set() and not elsewhere.is_set()
                here.clear()
                there.clear()
                await asyncio.sleep(0.2)
                assert not here.is_set() and not there.is_set()  # the nudge that arrived was not passed on again
        assert one.far is None and two.far is None
    asyncio.run(go())


def test_news_that_is_not_a_nudge_reaches_the_other_processes_and_not_the_one_that_said_it():
    async def go():
        bus, got = InMemoryMessageBus(), {"n1": [], "n2": []}

        async def hear(name, said):
            got[name].append(said.get("sync"))

        async with bus, relay(bus, "n1", True, Waker(), lambda s: hear("n1", s)) as tell, \
                relay(bus, "n2", True, Waker(), lambda s: hear("n2", s)):
            await asyncio.sleep(0.05)
            tell({"sync": "templates"})
            await asyncio.sleep(0.2)
        assert got == {"n1": [], "n2": ["templates"]}
    asyncio.run(go())


def test_without_a_shared_bus_a_nudge_stays_in_its_process_and_a_broken_relay_never_reaches_the_writer():
    async def go():
        w = Waker()
        async with relay(InMemoryMessageBus(), "n1", False, w):
            assert w.far is None

        def broken(key):
            raise RuntimeError("redis is away")
        w.far = broken
        with w.watch("conv") as ev:
            w.poke("conv")  # must not raise: the commit it follows has happened
            await asyncio.sleep(0)
            assert ev.is_set()
    asyncio.run(go())


def test_an_agent_published_through_one_process_is_known_to_the_other_at_once(tmp_path):
    """Which specialists a leader may create is in each process's memory. Two apps on one database with one bus between
    them are two processes of a fleet: what one publishes or retires, the other knows within a moment."""
    from conftest import ADM, publish

    bus = InMemoryMessageBus()
    with build(tmp_path, message_bus=bus) as one, build(tmp_path, message_bus=bus) as two:
        there = two.app.state.awp.rt
        assert two.app.state.wf.engine.node != one.app.state.wf.engine.node and "parking" not in there.templates
        draft = {"key": "parking", "name": "Parking desk", "mission": "books visitor parking.", "handles": ["parking"]}
        assert one.post("/platform/v1/profiles", draft, ADM).status_code == 201
        publish(one, "parking")
        deadline = time.monotonic() + 5
        while "parking" not in there.templates and time.monotonic() < deadline:
            time.sleep(0.05)
        assert "parking" in there.templates and there.template_tenant["parking"] == "ta"
        assert two.post("/platform/v1/profiles/parking/retire", {}, ADM).status_code == 200
        here = one.app.state.awp.rt
        while "parking" in here.templates and time.monotonic() < deadline + 5:
            time.sleep(0.05)
        assert "parking" not in here.templates


# ---- open streams ----------------------------------------------------------------------------------------------------
def test_without_redis_the_streams_of_a_key_are_counted_in_this_process():
    async def go():
        s = Slots(2)
        await s.attach(None)
        a, b = await s.enter("k"), await s.enter("k")
        with pytest.raises(WorkforceError):
            await s.enter("k")
        a.release()
        a.release()
        c = await s.enter("k")
        assert s.open["k"] == 2
        b.release()
        c.release()
        assert "k" not in s.open
    asyncio.run(go())


@needs_redis
def test_with_redis_the_streams_of_a_key_are_counted_over_every_process_and_a_dead_ones_place_runs_out(monkeypatch):
    monkeypatch.setattr(Slots, "TTL", 1.5)

    async def go():
        async with FleetBus(REDIS_URL, "n1") as one, FleetBus(REDIS_URL, "n2") as two:
            await one.get_client().flushdb()
            here, there = Slots(2), Slots(2)
            await here.attach(one)
            await there.attach(two)
            a, b = await here.enter("k"), await there.enter("k")
            for slots in (here, there):
                with pytest.raises(WorkforceError) as e:
                    await slots.enter("k")
                assert e.value.http == 429 and e.value.code == "RATE_LIMITED"
            other_key = await there.enter("j")  # another credential has its own count
            a.release()
            await asyncio.sleep(0.2)
            c = await there.enter("k")  # the place freed in one process is taken in the other
            # `b` and `c` are open. `b` keeps saying so; `c`'s process "dies" (never renews, never releases)
            for _ in range(8):
                await asyncio.sleep(0.3)
                b.renewed = 0.0
                await b.renew()
            d = await here.enter("k")  # c's place ran out, b's did not
            with pytest.raises(WorkforceError):
                await here.enter("k")
            for slot in (b, d, other_key):
                slot.release()
            await asyncio.sleep(0.2)
            assert await one.get_client().zcard("awp:streams:k") <= 1  # only what c left, until it is swept
    asyncio.run(go())


def test_when_redis_does_not_answer_the_count_falls_back_to_this_process():
    class Away:
        async def eval(self, *a):
            raise ConnectionError("redis is away")

    async def go():
        s = Slots(1)
        s.redis = Away()
        a = await s.enter("k")
        with pytest.raises(WorkforceError):
            await s.enter("k")
        a.release()
        (await s.enter("k")).release()
    asyncio.run(go())


# ---- locks that name their holder -------------------------------------------------------------------------------------
@needs_redis
def test_only_the_locks_of_the_named_dead_process_are_released_and_only_while_they_are_still_its():
    async def go():
        async with FleetBus(REDIS_URL, "nlive") as live, FleetBus(REDIS_URL, "ndead") as dead:
            redis = live.get_client()
            await redis.flushdb()
            mine, theirs, plain = (MessageBusKeys.session_lock(x) for x in ("s-live", "s-dead", "s-plain"))
            await redis.set(theirs, "ndead:tok", ex=600)  # what a killed process leaves: nobody renews or releases it
            await redis.set(plain, "0123abcd", ex=600)  # a lock taken by something that does not name itself
            await redis.set("awp:other:ndead", "ndead:tok", ex=600)  # not a lock at all
            async with live.acquire_lock(mine):
                assert holder_of(await redis.get(mine)) == "nlive" and await live.is_locked(theirs)
                assert await live.release_of("nlive") == []  # never its own
                assert await dead.release_of("nlive") == [mine]  # (what a survivor would do once nlive's lease ran out)
                assert not await live.is_locked(mine)
                assert await live.release_of("ndead") == [theirs]
                assert not await live.is_locked(theirs) and await live.is_locked(plain)
                assert await redis.get("awp:other:ndead") == "ndead:tok"
            # a lock the dead node's session was given again meanwhile is another value: not deleted
            await redis.set(theirs, "nlive:new", ex=600)
            assert await dead.release_of("ndead") == [] and await redis.get(theirs) == "nlive:new"
            await redis.flushdb()
    asyncio.run(go())


@needs_redis
def test_a_lock_is_held_for_one_holder_at_a_time_and_given_back_when_its_run_ends():
    async def go():
        async with FleetBus(REDIS_URL, "n1") as one, FleetBus(REDIS_URL, "n2") as two:
            await one.get_client().flushdb()
            key, order = MessageBusKeys.session_lock("s"), []

            async def run(bus, name):
                async with bus.acquire_lock(key, ttl_secs=30):
                    order.append(name + " in")
                    await asyncio.sleep(0.3)
                    order.append(name + " out")
            await asyncio.gather(run(one, "a"), run(two, "b"))
            assert order in (["a in", "a out", "b in", "b out"], ["b in", "b out", "a in", "a out"])
            assert not await one.is_locked(key) and await one.locks() == {}
    asyncio.run(go())


# ---- a tenant's evaluations queue over the fleet ------------------------------------------------------------------------
def test_the_place_of_an_evaluation_in_its_tenants_queue_is_the_same_from_every_process(tmp_path):
    from awp.evals.store import EvalStore

    async def go():
        db = Database(dbtest.urls(tmp_path)[0].url)
        await db.create_all()
        try:
            store = EvalStore(db)
            runs = [await store.open_run("ta", f"k{i}", 1, "sha256:x", "admin", time.time() + 60) for i in range(3)]
            other = await store.open_run("tb", "k0", 1, "sha256:x", "admin", time.time() + 60)
            assert [await store.ahead(r) for r in runs] == [0, 1, 2] and await store.ahead(other) == 0
            await store.write_run(runs[0]["id"], status="passed")
            assert [await store.ahead(r) for r in runs[1:]] == [0, 1]
        finally:
            await db.dispose()
    asyncio.run(go())
