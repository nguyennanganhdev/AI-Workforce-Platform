# -*- coding: utf-8 -*-
"""Deleting a team clears its collaboration state wherever it lives, and
hand-offs to a dead team stop being retried."""
from types import SimpleNamespace
from typing import Any
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis

from agentscope.app._manager._handoff_dispatcher import (
    _MAX_DELIVERY_ATTEMPTS,
    HandoffDispatcher,
)
from agentscope.app._service._session import SessionService
from agentscope.app.storage import RedisStorage, TeamHandoffRecord
from agentscope.app.storage._model._team_context import TeamTurnRecord


def _handoff(team_id: str, **fields: Any) -> TeamHandoffRecord:
    return TeamHandoffRecord(
        user_id="u",
        team_id=team_id,
        handoff_id=f"h-{team_id}",
        source_agent_id="a",
        source_session_id="s1",
        recipient_agent_id="b",
        recipient_session_id="s2",
        idempotency_key=f"k-{team_id}",
        payload={},
        **fields,
    )


class TeamCollaborationCleanupTest(IsolatedAsyncioTestCase):

    async def test_deleting_a_team_clears_the_shared_context_store(self) -> None:
        storage = MagicMock()
        storage.get_team = AsyncMock(return_value=None)
        storage.delete_team = AsyncMock(return_value=True)
        shared = MagicMock()
        shared.delete_team_collaboration = AsyncMock()
        service = SessionService(storage, MagicMock(), shared_context_storage=shared)

        self.assertTrue(await service.delete_team("u", "t1"))

        shared.delete_team_collaboration.assert_awaited_once_with("u", "t1")

    async def test_redis_drops_only_that_teams_turn_and_handoffs(self) -> None:
        redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

        class _Storage(RedisStorage):
            async def __aenter__(self) -> Any:
                self._client = redis
                return self

        storage = await _Storage().__aenter__()
        await storage.upsert_team_turn(
            "u",
            TeamTurnRecord(
                user_id="u",
                team_id="t1",
                turn_id="turn",
                reply_owner_session_id="s1",
                reply_owner_agent_id="a",
                customer_session_id="s1",
            ),
        )
        mine, other = _handoff("t1"), _handoff("t2")
        await storage.upsert_team_handoff("u", mine)
        await storage.upsert_team_handoff("u", other)

        await storage.delete_team_collaboration("u", "t1")

        self.assertIsNone(await storage.get_team_turn("u", "t1"))
        self.assertIsNone(await storage.get_team_handoff("u", mine.id))
        left = await storage.list_outstanding_team_handoffs()
        self.assertEqual([record.id for record in left], [other.id])


class HandoffDispatcherCleanupTest(IsolatedAsyncioTestCase):

    def _dispatcher(self, rows: list[TeamHandoffRecord]) -> tuple[HandoffDispatcher, Any]:
        storage = SimpleNamespace(
            list_outstanding_team_handoffs=AsyncMock(return_value=rows),
            get_team_shared_context=AsyncMock(return_value=None),
        )
        dispatcher = HandoffDispatcher(MagicMock(), storage)  # type: ignore[arg-type]
        dispatcher._context = SimpleNamespace(mark_handoff=AsyncMock())  # pylint: disable=protected-access
        return dispatcher, storage

    async def test_periodic_pass_skips_delivered_rows_in_the_query(self) -> None:
        dispatcher, storage = self._dispatcher([])

        await dispatcher._recover(include_delivered=False)  # pylint: disable=protected-access

        self.assertEqual(
            storage.list_outstanding_team_handoffs.await_args.kwargs["statuses"],
            ("pending", "failed"),
        )

    async def test_handoff_to_a_deleted_team_is_cancelled(self) -> None:
        record = _handoff("gone")
        dispatcher, _ = self._dispatcher([record])

        await dispatcher._recover(include_delivered=False)  # pylint: disable=protected-access

        dispatcher._context.mark_handoff.assert_awaited_once_with(record, "cancelled")  # pylint: disable=protected-access

    async def test_failed_handoff_stops_after_the_attempt_limit(self) -> None:
        record = _handoff(
            "t1",
            delivery_status="failed",
            delivery_attempts=_MAX_DELIVERY_ATTEMPTS,
        )
        dispatcher, storage = self._dispatcher([record])

        await dispatcher._recover(include_delivered=False)  # pylint: disable=protected-access

        call = dispatcher._context.mark_handoff.await_args  # pylint: disable=protected-access
        self.assertEqual(call.args, (record, "cancelled"))
        storage.get_team_shared_context.assert_not_awaited()


class SQLTeamCollaborationCleanupTest(IsolatedAsyncioTestCase):

    async def test_sql_drops_context_snapshots_turn_and_handoffs_of_one_team(self) -> None:
        from sqlalchemy import func, select

        from agentscope.app.storage import AsyncSQLAlchemyStorage, TeamSharedContextRecord
        from agentscope.app.storage._sql._tables import (
            TeamHandoffRow,
            TeamSharedContextSnapshotRow,
        )

        async with AsyncSQLAlchemyStorage(
            "sqlite+aiosqlite:///:memory:", create_tables=True,
        ) as storage:
            for team in ("t1", "t2"):
                record = TeamSharedContextRecord(id=team, user_id="u", team_id=team)
                record.state.revision = 1
                await storage.compare_and_swap_team_shared_context("u", record, 0)
                await storage.upsert_team_handoff("u", _handoff(team))
            await storage.upsert_team_turn(
                "u",
                TeamTurnRecord(
                    user_id="u", team_id="t1", turn_id="turn",
                    reply_owner_session_id="s1", reply_owner_agent_id="a",
                    customer_session_id="s1",
                ),
            )

            await storage.delete_team_collaboration("u", "t1")

            self.assertIsNone(await storage.get_team_shared_context("u", "t1"))
            self.assertIsNone(await storage.get_team_turn("u", "t1"))
            self.assertIsNotNone(await storage.get_team_shared_context("u", "t2"))
            async with storage._session() as sess:  # pylint: disable=protected-access
                for row in (TeamSharedContextSnapshotRow, TeamHandoffRow):
                    teams = (
                        await sess.execute(select(row.team_id, func.count()).group_by(row.team_id))
                    ).all()
                    self.assertEqual({team for team, _ in teams}, {"t2"})
