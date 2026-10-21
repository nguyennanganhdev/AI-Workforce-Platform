# -*- coding: utf-8 -*-
"""A pub/sub consumer survives a dropped subscription and a failing
handler instead of ending for the life of the process."""
import asyncio
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from agentscope.app import _bus_ops
from agentscope.app._bus_ops import follow_channel


class _FlakyBus:
    """First subscribe fails; the second yields two payloads, then idles."""

    def __init__(self) -> None:
        self.subscribes = 0

    async def subscribe(self, _channel, *, on_ready=None):
        self.subscribes += 1
        if self.subscribes == 1:
            raise ConnectionError("redis restarted")
        if on_ready is not None:
            on_ready()
        yield {"n": 1}
        yield {"n": 2}
        await asyncio.Event().wait()


class FollowChannelTest(IsolatedAsyncioTestCase):

    async def test_reconnects_resyncs_and_survives_a_bad_message(self) -> None:
        bus, seen, resyncs = _FlakyBus(), [], []
        done = asyncio.Event()

        async def handle(payload: dict) -> None:
            seen.append(payload["n"])
            if payload["n"] == 1:
                raise ValueError("bad entry")
            done.set()

        async def resync() -> None:
            resyncs.append(True)

        ready = asyncio.Event()
        with patch.object(_bus_ops.asyncio, "sleep", side_effect=lambda _s: asyncio.sleep(0)):
            task = asyncio.create_task(
                follow_channel(bus, "c", handle, ready=ready, name="t", resync=resync),
            )
            await asyncio.wait_for(done.wait(), 2)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        self.assertTrue(ready.is_set())
        self.assertEqual(bus.subscribes, 2)
        self.assertEqual(resyncs, [True])
        self.assertEqual(seen, [1, 2])
