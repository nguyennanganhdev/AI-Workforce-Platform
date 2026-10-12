"""GET /partner/conversations/{id}/events: the SSE stream (contract 9.6).

Credential, audience and cursor are checked before the first byte, so a refusal is a normal
JSON error. After that the stream only reads the log: it keeps one position (a sequence) and
asks the database for what is past it, so replay and live are the same loop and an event is
neither skipped nor sent twice at the boundary. A wake-up signal makes it quick; a timed read
makes it correct without the signal (another process, no Redis).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import Counter
from typing import Any, AsyncIterator, Callable

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from .auth import PartnerPrincipal, need, require, still_valid
from .errors import WorkforceError, invalid
from .events import public_event, read_after, resolve_cursor
from .reads import audience, own_conversation
from .waker import wait, waker

log = logging.getLogger("awp.workforce")
BATCH = 200
OPS = ("read_result", "receive_events")


async def shielded(coro):
    """Run a database call to its end even if the stream is cancelled meanwhile (the client went
    away). Cancelling an async driver mid-query leaves a broken connection in the pool."""
    task = asyncio.ensure_future(coro)
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        task.add_done_callback(lambda t: t.cancelled() or t.exception())  # nobody awaits it now
        raise


async def next_rows(ctx: Any, conversation_id: str, position: int) -> list:
    async with ctx.db.engine.connect() as c:
        return await read_after(c, conversation_id, position, BATCH)


def frame(item: dict) -> bytes:
    data = json.dumps(item, ensure_ascii=False, separators=(",", ":"))
    return f"id: {item['event_id']}\nevent: {item['event_type']}\ndata: {data}\n\n".encode()


async def feed(ctx: Any, p: PartnerPrincipal, conv: Any, position: int,
               release: Callable[[], None] = lambda: None, slot: "Slot | None" = None) -> AsyncIterator[bytes]:
    s = ctx.settings
    beat, recheck = max(s.wf_heartbeat_seconds, 0.01), max(s.wf_revalidate_seconds, 0.01)
    poll = max(s.wf_sse_poll_seconds, 0.01)
    last_sent = last_check = time.monotonic()
    try:
        with waker.watch(conv["id"]) as ev:
            while True:
                ev.clear()  # a change from here on sets it, even while we read
                t = time.monotonic()
                if slot is not None:
                    await slot.renew()
                if t - last_check >= recheck:  # by the clock on every pass, busy or idle (contract 9.6)
                    if not await shielded(still_valid(ctx, p, OPS, conv["route_id"])):
                        return  # key or grant gone: end the stream, a reconnect must authenticate again
                    last_check = t
                rows = await shielded(next_rows(ctx, conv["id"], position))
                if rows:
                    for row in rows:
                        yield frame(public_event(row, conv))
                        position = row["sequence"]
                    last_sent = time.monotonic()
                    continue
                if t - last_sent >= beat:
                    yield b": heartbeat\n\n"
                    last_sent = t
                due = min(beat - (t - last_sent), recheck - (t - last_check), poll)
                await wait(ev, due)
    except Exception:
        log.exception("event stream of %s ended", conv["id"])  # headers are out: just close
    finally:
        release()


# One sorted set per key: a member per open stream, its score the time it runs out. Take a place only below the limit.
TAKE = """redis.call('zremrangebyscore', KEYS[1], '-inf', ARGV[1])
if redis.call('zcard', KEYS[1]) >= tonumber(ARGV[2]) then return 0 end
redis.call('zadd', KEYS[1], ARGV[3], ARGV[4])
redis.call('expire', KEYS[1], ARGV[5])
return 1"""
STREAMS = "awp:streams:"


def too_many() -> WorkforceError:
    return WorkforceError("RATE_LIMITED", 429, "Too many event streams are open for this credential.",
                          {"retry_after_seconds": 5}, retryable=True, headers={"Retry-After": "5"})


class Slot:
    """One open stream's place. `release` is safe to call twice and from anywhere in the event loop."""

    def __init__(self, slots: "Slots", key: str, local: Callable[[], None], member: str | None) -> None:
        self.slots, self.key, self.local, self.member = slots, key, local, member
        self.renewed = time.monotonic()

    async def renew(self) -> None:
        """The stream is still open: its place in the fleet's count does not run out."""
        if self.member is None or time.monotonic() - self.renewed < Slots.TTL / 3:
            return
        self.renewed = time.monotonic()
        try:
            await self.slots.redis.zadd(STREAMS + self.key, {self.member: time.time() + Slots.TTL})
            await self.slots.redis.expire(STREAMS + self.key, int(Slots.TTL * 2))
        except Exception as e:  # counted too low for a while, never a broken stream
            log.debug("could not renew a stream's place (%s)", type(e).__name__)

    def release(self) -> None:
        self.local()
        member, self.member = self.member, None
        if member is None or self.slots.redis is None:
            return

        async def drop() -> None:
            try:
                await self.slots.redis.zrem(STREAMS + self.key, member)
            except Exception:  # it runs out by itself
                pass

        try:
            task = asyncio.get_running_loop().create_task(drop())
            self.slots.tasks.add(task)
            task.add_done_callback(self.slots.tasks.discard)
        except RuntimeError:
            pass


class Slots:
    """Open streams per key: a stream is a coroutine that reads the database, and the rate limit counts connects, not
    streams that stay open.

    In one process the count is in memory (`take`). With a bus the fleet shares (`attach`), the count is the fleet's: a
    sorted set in Redis with one member per open stream, renewed by the stream while it is open and removed when it
    ends; the place of a stream whose process died runs out after `TTL` seconds. When Redis does not answer, the count
    falls back to this process's, so a stream is never refused or dropped because Redis is away."""

    TTL = 60.0

    def __init__(self, limit: int) -> None:
        self.limit, self.open = limit, Counter()
        self.redis: Any = None
        self.tasks: set = set()

    async def attach(self, bus: Any) -> None:
        get = getattr(bus, "get_client", None)
        self.redis = get() if get is not None else None

    async def enter(self, key: str) -> Slot:
        """A place for one stream of `key`, or WorkforceError 429 when the key is full."""
        if self.limit > 0 and self.redis is not None:
            member, at = uuid.uuid4().hex, time.time()
            try:
                ok = await self.redis.eval(TAKE, 1, STREAMS + key, at, self.limit, at + self.TTL, member, int(self.TTL * 2))
            except Exception as e:
                log.warning("the fleet's count of event streams is not reachable (%s): counting in this process", type(e).__name__)
            else:
                if not ok:
                    raise too_many()
                self.open[key] += 1
                return Slot(self, key, self._leave(key), member)
        return Slot(self, key, self.take(key), None)

    def _leave(self, key: str) -> Callable[[], None]:
        done = False

        def release() -> None:
            nonlocal done
            if not done:
                done = True
                self.open[key] -= 1
                if self.open[key] <= 0:
                    del self.open[key]
        return release

    def take(self, key: str) -> Callable[[], None]:
        """A release function (safe to call twice), or WorkforceError 429 when the key is full."""
        if 0 < self.limit <= self.open[key]:
            raise too_many()
        self.open[key] += 1
        return self._leave(key)


def build_stream(r: APIRouter, ctx: Any) -> None:
    @r.get("/partner/conversations/{conversation_id}/events")
    async def events(conversation_id: str, request: Request, external_user_id: str | None = Query(None),
                     after_cursor: str | None = Query(None, max_length=200),
                     p: PartnerPrincipal = Depends(require("read_result"))):
        need(p, "receive_events")
        user = audience(external_user_id)
        header = request.headers.get("last-event-id") or None
        if header and after_cursor and header != after_cursor:
            raise invalid("Last-Event-ID and after_cursor are both set and differ.")
        async with ctx.db.engine.connect() as conn:
            conv = await own_conversation(conn, p, conversation_id, user)
            position = await resolve_cursor(conn, conv, after_cursor or header)
        slot = await ctx.slots.enter(p.key_id)
        # The generator frees the slot when it ends; the background task covers a response that
        # was never started (the client left first). Releasing twice is harmless.
        return StreamingResponse(
            feed(ctx, p, conv, position, slot.release, slot), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            background=BackgroundTask(slot.release))
