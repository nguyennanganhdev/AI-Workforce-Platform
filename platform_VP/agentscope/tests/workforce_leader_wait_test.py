"""The Leader wakes on team-context signals instead of fast polling."""

import asyncio
import time
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase

from agentscope.app._shared_context import SharedContextService
from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.middleware import LeaderEvidenceMiddleware
from agentscope.app.storage import TeamSharedContextRecord


class _Storage:
    def __init__(self) -> None:
        self.record: TeamSharedContextRecord | None = None

    async def get_session(self, *_args):
        return SimpleNamespace(team_id="team-1")

    async def get_team_shared_context(self, _user, _team):
        return self.record.model_copy(deep=True) if self.record else None

    async def upsert_team_shared_context(self, _user, record):
        self.record = record.model_copy(deep=True)
        return record

    async def compare_and_swap_team_shared_context(self, _user, record, expected):
        if (self.record.state.revision if self.record else 0) != expected:
            return False
        self.record = record.model_copy(deep=True)
        return True


class WatchTest(IsolatedAsyncioTestCase):
    async def test_every_committed_change_is_signalled(self) -> None:
        service = SharedContextService(_Storage(), InMemoryMessageBus())  # type: ignore[arg-type]
        async with service.watch("team-1") as changes:
            await service.append_event(
                user_id="u",
                team_id="team-1",
                kind="customer_message",
                content="hello",
            )
            item = await asyncio.wait_for(changes.get(), timeout=2)
        self.assertGreater(item["revision"], 0)

    async def test_leader_wait_returns_on_signal_not_on_safety_poll(self) -> None:
        state = {"ready": False}
        queue: asyncio.Queue = asyncio.Queue()

        class Shared:
            @asynccontextmanager
            async def watch(self, _team):
                yield queue

            async def team_evidence_status(self, *_a, **_k):
                return (1, 0, 0, False) if state["ready"] else (0, 0, 0, False)

            async def collaboration_review(self, *_a):
                return [] if state["ready"] else ["worker"]

            async def pending_user_question(self, *_a):
                return None

        middleware = LeaderEvidenceMiddleware(
            _Storage(),  # type: ignore[arg-type]
            Shared(),  # type: ignore[arg-type]
            "u",
            "leader",
            "leader-session",
        )
        middleware._pending_consent = lambda: _false()  # type: ignore[method-assign]

        async def report_later():
            await asyncio.sleep(0.2)
            state["ready"] = True
            queue.put_nowait({"revision": 2})

        started = time.monotonic()
        asyncio.create_task(report_later())
        ready = await middleware._wait_until_ready(1, asyncio.get_running_loop().time() + 30)

        self.assertTrue(ready)
        self.assertLess(time.monotonic() - started, 2.0)


async def _false() -> bool:
    return False
