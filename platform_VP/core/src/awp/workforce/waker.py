"""A nudge that tells waiting readers "something changed in this conversation".

It is only a shortcut: the database is the truth and every waiter also polls it, so
nothing breaks when a nudge is lost or when the writer is another process. The nudge
fires after the writer's commit has come back from the database: a reader woken earlier
reads nothing new and then sleeps until its next poll. SQLAlchemy's `commit` event is not
that moment (it fires before the driver is called), so the engine's `do_commit` is wrapped.

With a bus that the processes of a fleet share (Redis), a nudge also goes to the others (`relay`): a POST handled by
one process wakes the event stream a client holds open on another within milliseconds instead of at its next poll.
The relay is best effort by design (publish and forget, no queue): Redis down or slow costs speed, never an event.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from collections import defaultdict
from typing import Any, AsyncIterator, Awaitable, Callable, Iterator

from sqlalchemy import event

log = logging.getLogger("awp.workforce")
# The pub/sub channel of the fleet: {"key": conversation id, "from": node} is a nudge; anything else is news for the
# process itself ({"sync": "templates"}: the published agents changed), handed to `heard`.
CHANNEL = "awp:wake"


class Waker:
    def __init__(self) -> None:
        self._waiting: dict[str, set[tuple[asyncio.AbstractEventLoop, asyncio.Event]]] = defaultdict(set)
        self.far: Callable[[str], None] | None = None  # tells the other processes (set by `relay`, thread safe)

    @contextlib.contextmanager
    def watch(self, key: str) -> Iterator[asyncio.Event]:
        """Register before reading the database, then `clear()` / read / `wait()`: a change that
        lands between the read and the wait still sets the event."""
        entry = (asyncio.get_running_loop(), asyncio.Event())
        self._waiting[key].add(entry)
        try:
            yield entry[1]
        finally:
            self._waiting[key].discard(entry)
            if not self._waiting[key]:
                del self._waiting[key]

    def poke(self, key: str, local: bool = False) -> None:
        """Wake the readers of `key` in this process, and (unless `local`: the nudge came from another process) pass
        it on to the others."""
        for loop, ev in list(self._waiting.get(key, ())):
            try:
                loop.call_soon_threadsafe(ev.set)
            except RuntimeError:  # that loop is closed
                pass
        far = self.far
        if far is not None and not local:
            try:
                far(key)
            except Exception:  # never the writer's problem
                pass


waker = Waker()


_KEYS = "awp_poke"  # in the info of the pooled connection, from the `commit` event until the commit is back


def poke_on_commit(conn, key: str) -> None:
    """Poke `key` once the transaction of `conn` is committed (once per key, nothing on rollback)."""
    sc = conn.sync_connection
    keys = getattr(sc, "_awp_poke", None)
    if keys is None:
        keys = sc._awp_poke = set()
        _wrap_commit(sc.engine.dialect)
        event.listen(sc, "commit", _hand_over)
    keys.add(key)


def _hand_over(sc) -> None:
    """Just before the driver commits: what this transaction wants poked goes to where `do_commit` finds it."""
    keys, sc._awp_poke = sc._awp_poke, set()
    if keys:
        sc.connection.info[_KEYS] = keys


def _wrap_commit(dialect) -> None:
    if getattr(dialect, "_awp_pokes", False):
        return
    commit = dialect.do_commit

    def do_commit(dbapi_connection):
        keys = dbapi_connection.info.pop(_KEYS, ())
        commit(dbapi_connection)  # raises: nobody is woken for what did not happen
        for k in keys:
            waker.poke(k)

    dialect.do_commit, dialect._awp_pokes = do_commit, True


@contextlib.asynccontextmanager
async def relay(bus: Any, node: str, shared: bool, target: Waker | None = None,
                heard: Callable[[dict], Awaitable[None]] | None = None) -> AsyncIterator[Callable[[dict], None]]:
    """While open: nudges of this process are published on the bus and those of the others wake the readers here.
    Yields `tell(payload)`, which says something else to the other processes; what they say comes to `heard`.
    Nothing when the bus is not shared. A subscription that breaks (Redis restarted) is taken up again; meanwhile the
    readers fall back on their polls and the processes on their periodic look at the database."""
    w = target or waker
    if not shared:
        yield lambda payload: None
        return
    loop, sending = asyncio.get_running_loop(), set()

    async def send(payload: dict) -> None:
        try:
            await bus.publish(CHANNEL, {**payload, "from": node})
        except Exception as e:
            log.debug("could not pass a nudge on (%s)", type(e).__name__)

    def spawn(payload: dict) -> None:
        task = loop.create_task(send(payload))
        sending.add(task)
        task.add_done_callback(sending.discard)

    def tell(payload: dict) -> None:  # called from whichever thread committed
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(spawn, payload)

    async def listen() -> None:
        while True:
            try:
                async for said in bus.subscribe(CHANNEL):
                    if said.get("from") == node:
                        continue
                    if said.get("key"):
                        w.poke(str(said["key"]), local=True)
                    elif heard is not None:
                        try:
                            await heard(said)
                        except Exception:
                            log.exception("could not act on the news of another process")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("the nudges of the other processes stopped (%s); listening again", type(e).__name__)
            await asyncio.sleep(1.0)

    listener = loop.create_task(listen())
    w.far = lambda key: tell({"key": key})
    try:
        yield tell
    finally:
        w.far = None
        listener.cancel()
        await asyncio.gather(listener, *sending, return_exceptions=True)


async def wait(ev: asyncio.Event, timeout: float) -> None:
    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(ev.wait(), max(timeout, 0))
