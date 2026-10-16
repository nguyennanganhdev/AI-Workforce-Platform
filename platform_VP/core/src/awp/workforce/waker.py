"""A nudge that tells waiting readers "something changed in this conversation".

It is only a shortcut: the database is the truth and every waiter also polls it, so
nothing breaks when a nudge is lost or when the writer is another process. The nudge
fires after the writer's commit has come back from the database: a reader woken earlier
reads nothing new and then sleeps until its next poll. SQLAlchemy's `commit` event is not
that moment (it fires before the driver is called), so the engine's `do_commit` is wrapped.
"""
from __future__ import annotations

import asyncio
import contextlib
from collections import defaultdict
from typing import Iterator

from sqlalchemy import event


class Waker:
    def __init__(self) -> None:
        self._waiting: dict[str, set[tuple[asyncio.AbstractEventLoop, asyncio.Event]]] = defaultdict(set)

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

    def poke(self, key: str) -> None:
        for loop, ev in list(self._waiting.get(key, ())):
            try:
                loop.call_soon_threadsafe(ev.set)
            except RuntimeError:  # that loop is closed
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


async def wait(ev: asyncio.Event, timeout: float) -> None:
    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(ev.wait(), max(timeout, 0))
