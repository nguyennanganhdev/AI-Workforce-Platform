"""SQL persistence coverage for durable team shared context."""

from unittest import IsolatedAsyncioTestCase

from sqlalchemy import func, select

from agentscope.app.storage import (
    AsyncSQLAlchemyStorage,
    SharedContextEvent,
    SharedTaskState,
    TeamSharedContextRecord,
)
from agentscope.app.storage._sql._tables import TeamSharedContextSnapshotRow


class TestTeamSharedContextSQL(IsolatedAsyncioTestCase):
    async def test_cas_rejects_stale_writer_and_keeps_snapshots(self) -> None:
        async with AsyncSQLAlchemyStorage(
            "sqlite+aiosqlite:///:memory:",
            create_tables=True,
        ) as storage:
            original = TeamSharedContextRecord(
                id="cas-ticket",
                user_id="owner-1",
                team_id="cas-ticket",
            )
            original.state.active_task_id = "task-1"
            original.state.tasks["task-1"] = SharedTaskState(
                id="task-1",
                objective="Generic customer task",
            )
            original.state.revision = 1
            self.assertTrue(
                await storage.compare_and_swap_team_shared_context(
                    "owner-1",
                    original,
                    0,
                ),
            )

            winner = original.model_copy(deep=True)
            stale = original.model_copy(deep=True)
            winner.state.revision = 2
            winner.state.tasks["task-1"].status = "completed"
            stale.state.revision = 2
            stale.state.tasks["task-1"].status = "failed"

            self.assertTrue(
                await storage.compare_and_swap_team_shared_context(
                    "owner-1",
                    winner,
                    1,
                ),
            )
            self.assertFalse(
                await storage.compare_and_swap_team_shared_context(
                    "owner-1",
                    stale,
                    1,
                ),
            )
            loaded = await storage.get_team_shared_context(
                "owner-1",
                "cas-ticket",
            )
            self.assertEqual("completed", loaded.state.tasks["task-1"].status)
            async with storage._session() as session:
                snapshot_count = await session.scalar(
                    select(func.count()).select_from(
                        TeamSharedContextSnapshotRow,
                    ),
                )
            self.assertEqual(2, snapshot_count)

    async def test_round_trip_update_owner_scope_and_delete(self) -> None:
        async with AsyncSQLAlchemyStorage(
            "sqlite+aiosqlite:///:memory:",
            create_tables=True,
        ) as storage:
            record = TeamSharedContextRecord(
                id="ticket-1",
                user_id="owner-1",
                team_id="ticket-1",
            )
            record.state.active_task_id = "task-1"
            record.state.tasks["task-1"] = SharedTaskState(
                id="task-1",
                objective="Plan a trip",
            )
            record.state.revision = 1
            record.state.events.append(
                SharedContextEvent(
                    id="event-1",
                    revision=1,
                    task_id="task-1",
                    kind="customer_message",
                    content="Two adults, 17/10 to 18/10",
                ),
            )
            await storage.upsert_team_shared_context("owner-1", record)

            loaded = await storage.get_team_shared_context(
                "owner-1",
                "ticket-1",
            )
            self.assertEqual(loaded.state.events[0].id, "event-1")
            self.assertIsNone(
                await storage.get_team_shared_context("owner-2", "ticket-1"),
            )

            loaded.state.metrics.packets_built = 2
            await storage.upsert_team_shared_context("owner-1", loaded)
            updated = await storage.get_team_shared_context(
                "owner-1",
                "ticket-1",
            )
            self.assertEqual(updated.state.metrics.packets_built, 2)
            self.assertTrue(
                await storage.delete_team_shared_context(
                    "owner-1",
                    "ticket-1",
                ),
            )
            self.assertIsNone(
                await storage.get_team_shared_context("owner-1", "ticket-1"),
            )
