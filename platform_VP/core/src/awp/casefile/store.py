"""Persistence for the case file: an append-only list of typed items."""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError

from .. import db

# Item kinds and the prefix of their reference, e.g. fact -> F1, F2, ...
PREFIX = {
    "evidence": "E", "fact": "F", "question": "Q", "challenge": "C",
    "answer": "A", "gap": "G", "decision": "D", "report": "R",
    "note": "N", "final": "X",
    "invite": "I",  # the leader brought a specialist in: which type, for what, out of which candidates (audit, not room talk)
    "trace": "T",  # a tool call of an agent in an evaluation sandbox (evals/sandbox.py): read by the checks, not by the room
}
KIND_OF_PREFIX = {v: k for k, v in PREFIX.items()}


@dataclass
class Item:
    id: int
    case_id: str
    ref: str
    kind: str
    author: str
    addressee: str | None
    data: dict[str, Any]
    created_at: float


def _item(row) -> Item:
    return Item(row.id, row.case_id, row.ref, row.kind, row.author,
                row.addressee, row.data or {}, row.created_at)


class CaseStore:
    def __init__(self, database: db.Database) -> None:
        self._db = database

    # ---- cases ---------------------------------------------------------
    async def create_case(
        self, *, tenant: str, domain: str, external_ref: str, user_id: str,
        meta: dict, budget_usd: float = 0.0, budget_tokens: int = 0, conn: Any = None,
    ) -> str:
        """`conn` joins the caller's transaction (the workflow and its case are written together)."""
        case_id = "case_" + uuid.uuid4().hex[:16]
        now = time.time()
        stmt = insert(db.cases).values(
            id=case_id, tenant=tenant, domain=domain,
            external_ref=external_ref, status="open", user_id=user_id,
            meta=meta, budget_usd=budget_usd,
            budget_tokens=budget_tokens, created_at=now, updated_at=now)
        if conn is not None:
            await conn.execute(stmt)
        else:
            async with self._db.engine.begin() as own:
                await own.execute(stmt)
        return case_id

    async def get_case(self, case_id: str) -> dict | None:
        async with self._db.engine.connect() as conn:
            row = (await conn.execute(
                select(db.cases).where(db.cases.c.id == case_id))).first()
        return dict(row._mapping) if row else None

    async def update_case(self, case_id: str, *, conn: Any = None, **values: Any) -> None:
        values["updated_at"] = time.time()
        stmt = update(db.cases).where(db.cases.c.id == case_id).values(**values)
        if conn is not None:
            await conn.execute(stmt)
            return
        async with self._db.engine.begin() as own:
            await own.execute(stmt)

    async def list_cases(self, tenant: str, status: str | None = None,
                         limit: int = 50) -> list[dict]:
        q = select(db.cases).where(db.cases.c.tenant == tenant)
        if status:
            q = q.where(db.cases.c.status == status)
        q = q.order_by(db.cases.c.created_at.desc()).limit(limit)
        async with self._db.engine.connect() as conn:
            return [dict(r._mapping) for r in (await conn.execute(q))]

    # ---- sessions ------------------------------------------------------
    async def bind_session(self, case_id: str, session_id: str, agent_id: str,
                           agent_name: str, role: str) -> None:
        async with self._db.engine.begin() as conn:
            exists = (await conn.execute(select(db.case_sessions.c.session_id).where(
                db.case_sessions.c.session_id == session_id))).first()
            if exists:
                await conn.execute(update(db.case_sessions).where(
                    db.case_sessions.c.session_id == session_id).values(
                    case_id=case_id, agent_id=agent_id, agent_name=agent_name[:80], role=role))
            else:
                await conn.execute(insert(db.case_sessions).values(
                    session_id=session_id, case_id=case_id, agent_id=agent_id,
                    agent_name=agent_name[:80], role=role))

    async def session_binding(self, session_id: str) -> dict | None:
        async with self._db.engine.connect() as conn:
            row = (await conn.execute(select(db.case_sessions).where(
                db.case_sessions.c.session_id == session_id))).first()
        return dict(row._mapping) if row else None

    async def sessions_of_case(self, case_id: str) -> list[dict]:
        async with self._db.engine.connect() as conn:
            rows = await conn.execute(select(db.case_sessions).where(
                db.case_sessions.c.case_id == case_id))
            return [dict(r._mapping) for r in rows]

    # ---- items ---------------------------------------------------------
    async def add(self, case_id: str, kind: str, author: str, data: dict,
                  addressee: str | None = None, conn: Any = None) -> Item:
        """Append an item. The reference (F1, F2...) is allocated inside the
        transaction; concurrent writers that pick the same number retry.
        `conn` joins the caller's transaction (the item commits with what the caller writes)."""
        prefix = PREFIX[kind]
        if conn is not None:
            await self._turn(conn, case_id)
            return await self._add_in(conn, case_id, prefix, kind, author, data, addressee)
        for attempt in range(8):
            try:
                async with self._db.engine.begin() as conn:
                    await self._turn(conn, case_id)
                    n = (await conn.execute(select(func.count()).select_from(db.case_items).where(
                        db.case_items.c.case_id == case_id,
                        db.case_items.c.kind == kind))).scalar_one()
                    ref = f"{prefix}{n + 1}"
                    now = time.time()
                    res = await conn.execute(insert(db.case_items).values(
                        case_id=case_id, ref=ref, kind=kind, author=author[:80],
                        addressee=addressee[:80] if addressee else addressee, data=data, created_at=now))
                    return Item(res.inserted_primary_key[0], case_id, ref, kind, author,
                                addressee, data, now)
            except IntegrityError:
                await asyncio.sleep(0.01 * (attempt + 1))
        raise RuntimeError("could not allocate a reference in the case file")

    @staticmethod
    async def _turn(conn: Any, case_id: str) -> None:
        """Writers of one case take turns for the reference (PostgreSQL: the case row's lock, held to the end of the
        transaction). Without it twelve writers all pick the same number and lose the race again and again; SQLite has one
        writer for the file, and the unique key plus the retry below remain the safety net on both."""
        if conn.dialect.name == "postgresql":
            await conn.execute(select(db.cases.c.id).where(db.cases.c.id == case_id).with_for_update())

    async def _add_in(self, conn: Any, case_id: str, prefix: str, kind: str, author: str, data: dict,
                      addressee: str | None) -> Item:
        for attempt in range(8):
            try:
                async with conn.begin_nested():  # a lost race on the reference must not poison the caller's transaction
                    n = (await conn.execute(select(func.count()).select_from(db.case_items).where(
                        db.case_items.c.case_id == case_id, db.case_items.c.kind == kind))).scalar_one()
                    now = time.time()
                    res = await conn.execute(insert(db.case_items).values(
                        case_id=case_id, ref=f"{prefix}{n + 1}", kind=kind, author=author[:80],
                        addressee=addressee[:80] if addressee else addressee, data=data, created_at=now))
                    return Item(res.inserted_primary_key[0], case_id, f"{prefix}{n + 1}", kind, author,
                                addressee, data, now)
            except IntegrityError:
                await asyncio.sleep(0.01 * (attempt + 1))
        raise RuntimeError("could not allocate a reference in the case file")

    async def get(self, case_id: str, ref: str) -> Item | None:
        async with self._db.engine.connect() as conn:
            row = (await conn.execute(select(db.case_items).where(
                db.case_items.c.case_id == case_id,
                db.case_items.c.ref == ref))).first()
        return _item(row) if row else None

    async def items(self, case_id: str, after_id: int = 0,
                    kinds: tuple[str, ...] | None = None) -> list[Item]:
        q = select(db.case_items).where(
            db.case_items.c.case_id == case_id, db.case_items.c.id > after_id)
        if kinds:
            q = q.where(db.case_items.c.kind.in_(kinds))
        async with self._db.engine.connect() as conn:
            rows = await conn.execute(q.order_by(db.case_items.c.id))
            return [_item(r) for r in rows]

    # ---- digest cursors ------------------------------------------------
    async def get_cursor(self, case_id: str, agent_key: str) -> int:
        async with self._db.engine.connect() as conn:
            row = (await conn.execute(select(db.cursors.c.last_item_id).where(
                db.cursors.c.case_id == case_id,
                db.cursors.c.agent_key == agent_key))).first()
        return row[0] if row else 0

    async def set_cursor(self, case_id: str, agent_key: str, last_id: int) -> None:
        async with self._db.engine.begin() as conn:
            res = await conn.execute(update(db.cursors).where(
                db.cursors.c.case_id == case_id,
                db.cursors.c.agent_key == agent_key).values(last_item_id=last_id))
            if res.rowcount == 0:
                await conn.execute(insert(db.cursors).values(
                    case_id=case_id, agent_key=agent_key, last_item_id=last_id))
