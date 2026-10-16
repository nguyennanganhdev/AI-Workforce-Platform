"""A bare database for the unit tests of events, workflows and retention (no app, no HTTP)."""
from __future__ import annotations

import asyncio
import time

from sqlalchemy import insert, select

import dbtest
from awp.db import Database
from awp.workforce import tables as t
from awp.workforce.tables import new_id


class Lab:
    def __init__(self, path) -> None:
        """`path` is where the SQLite file goes (a name in the test's tmp_path); on PostgreSQL it names a fresh database."""
        self.loop = asyncio.new_event_loop()
        self.where = dbtest.one(path.parent, path.name)
        self.db = Database(self.where.url)
        self.run(self.db.create_all())

    def run(self, coro):
        return self.loop.run_until_complete(coro)

    def close(self) -> None:
        self.run(self.db.dispose())
        self.loop.close()

    async def _seed(self, state: str, closed_at: float | None, revision: int) -> dict:
        cid, wid, stamp = new_id("conv"), new_id("wf"), time.time()
        conv = dict(id=cid, client_id="cl_1", route_id="route_1", external_user_id="resident-1",
                    external_conversation_id=f"CHAT-{cid[-6:]}", external_ticket_id=f"TICKET-{cid[-6:]}",
                    last_sequence=0, purged_through=0, created_at=stamp)
        wf = dict(id=wid, conversation_id=cid, client_id="cl_1", route_id="route_1", case_id=None,
                  external_user_id="resident-1", external_ticket_id=conv["external_ticket_id"],
                  ticket_id=None, state=state, revision=revision, expects=None, current_request_id=None,
                  close_reason=None, attention_reason=None, last_activity_at=stamp, created_at=stamp,
                  closed_at=closed_at)
        async with self.db.engine.begin() as conn:
            await conn.execute(insert(t.conversations).values(**conv))
            await conn.execute(insert(t.workflows).values(**wf))
        return {"conv": conv, "wf": wf}

    def seed(self, state: str = "active", closed_at: float | None = None, revision: int = 1) -> dict:
        """A conversation with one workflow, as rows. Returns {"conv": dict, "wf": dict}."""
        return self.run(self._seed(state, closed_at, revision))

    async def _rows(self, table, where):
        async with self.db.engine.connect() as conn:
            q = select(table)
            for k, v in where.items():
                q = q.where(table.c[k] == v)
            return (await conn.execute(q)).mappings().all()

    def rows(self, table, **where) -> list:
        return self.run(self._rows(table, where))

    def one(self, table, **where):
        found = self.rows(table, **where)
        assert len(found) == 1, found
        return found[0]
