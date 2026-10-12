"""The message bus of the platform: in memory for one process, Redis for a fleet (AWP_REDIS_URL).

AgentScope's RedisMessageBus is used as it is, with one difference: a lock says who holds it. AgentScope takes the
session lock for every run (`agentscope:session:lock:<sid>`, a lease of 600 s that the holder renews), and a process that
is killed leaves it behind: every later run of that session then waits for up to ten minutes. With the holder's name in
the lock's value, another process can tell a dead holder's lock from a live one's and delete exactly that one
(`release_of`), which is all `workforce/nodes.py` ever asks for: only after the holder's own lease in the database ran
out, and by compare-and-delete, so the lock of a process that lives is never touched.
"""
from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from agentscope.app.message_bus import InMemoryMessageBus, RedisMessageBus

LOCKS = "agentscope:*:lock:*"  # every lock key AgentScope makes (session, inbox, SOP)
# Delete the key only when it still holds the value we read: never the lock somebody else took meanwhile.
DROP = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"


def new_node() -> str:
    """The name of one process for as long as it runs: never reused, so a restarted process is a new node."""
    return "n" + uuid.uuid4().hex[:16]


def holder_of(value: Any) -> str | None:
    """The node that holds a lock, from the lock's value; None for a value that is not ours (left alone for ever)."""
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    node, sep, token = str(value or "").partition(":")
    return node if sep and token and node.startswith("n") else None


class FleetBus(RedisMessageBus):
    """RedisMessageBus built from a URL, whose locks carry the node that holds them."""

    def __init__(self, url: str, node: str) -> None:
        super().__init__()
        self.url, self.node = url, node
        self._pool: Any = None

    async def __aenter__(self) -> "FleetBus":
        import redis.asyncio as aioredis

        self._pool = aioredis.ConnectionPool.from_url(self.url, decode_responses=True)
        self._client = aioredis.Redis(connection_pool=self._pool)
        try:
            await self._client.ping()
        except Exception as e:
            await self.aclose()
            raise RuntimeError(f"AWP_REDIS_URL is set but Redis does not answer ({type(e).__name__}); several processes "
                               "need it, one process runs without it (unset AWP_REDIS_URL)") from e
        return self

    async def aclose(self) -> None:
        pool, self._pool, self._client = self._pool, None, None
        if pool is not None:
            await pool.aclose()

    @asynccontextmanager
    async def acquire_lock(self, key: str, *, ttl_secs: int = 600) -> AsyncGenerator[None, None]:
        """As RedisMessageBus.acquire_lock (SET NX EX, a heartbeat every half lease, release by comparing the value),
        with `<node>:<random>` as the value."""
        token = f"{self.node}:{uuid.uuid4().hex}"
        while not await self._client.set(key, token, nx=True, ex=ttl_secs):
            await asyncio.sleep(self._LOCK_RETRY_DELAY_SECS)

        async def beat() -> None:
            while True:
                await asyncio.sleep(max(1.0, ttl_secs / 2))
                await self._client.expire(key, ttl_secs)

        task = asyncio.create_task(beat(), name=f"lock-heartbeat:{key}")
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            try:
                await self._client.eval(DROP, 1, key, token)
            except Exception:  # the lease runs out by itself
                pass

    async def locks(self) -> dict[str, str]:
        """Every lock that is held now: key -> value."""
        out: dict[str, str] = {}
        async for key in self._client.scan_iter(match=LOCKS, count=500):
            try:
                value = await self._client.get(key)
            except Exception:  # not a plain value: not a lock
                continue
            if value is not None:
                out[key] = value
        return out

    async def release_of(self, node: str) -> list[str]:
        """Delete the locks `node` holds, each only if its value is still the one read here. Returns their keys."""
        if not node or node == self.node:
            return []
        gone = []
        for key, value in (await self.locks()).items():
            if holder_of(value) == node and await self._client.eval(DROP, 1, key, value):
                gone.append(key)
        return gone


def build_bus(redis_url: str, node: str) -> Any:
    return FleetBus(redis_url, node) if redis_url else InMemoryMessageBus()
