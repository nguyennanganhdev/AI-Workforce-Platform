# -*- coding: utf-8 -*-
"""A non-stateful schedule keeps only its newest sessions."""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from agentscope.app._manager._scheduler import _scheduler_manager as scheduler
from agentscope.app.storage import ScheduleOrigin, UserOrigin


class ScheduleSessionRetentionTest(IsolatedAsyncioTestCase):

    async def test_old_schedule_sessions_are_deleted_and_others_kept(self) -> None:
        now = datetime.now()
        mine = [
            SimpleNamespace(
                id=f"s{i}",
                created_at=now - timedelta(minutes=i),
                origin=ScheduleOrigin(schedule_id="sched"),
            )
            for i in range(25)
        ]
        other = SimpleNamespace(id="other", created_at=now - timedelta(days=9),
                                origin=ScheduleOrigin(schedule_id="another"))
        personal = SimpleNamespace(id="chat", created_at=now - timedelta(days=9), origin=UserOrigin())
        storage = SimpleNamespace(list_sessions=AsyncMock(return_value=[*mine, other, personal]))
        record = SimpleNamespace(id="sched", user_id="u", agent_id="a")
        deleted: list[str] = []

        class _Service:
            def __init__(self, *_args, **_kwargs) -> None:
                pass

            async def delete_session(self, _user, _agent, session_id) -> bool:
                deleted.append(session_id)
                return True

        with patch("agentscope.app._service._session.SessionService", _Service):
            await scheduler._prune_schedule_sessions(storage, MagicMock(), MagicMock(), record, "s0")

        self.assertEqual(sorted(deleted), sorted(f"s{i}" for i in range(20, 25)))
