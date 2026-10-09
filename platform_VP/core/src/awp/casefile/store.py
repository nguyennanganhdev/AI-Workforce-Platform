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
        intake: dict, budget_usd: float = 0.0, budget_tokens: int = 0,
    ) -> str:
        case_id = "case_" + uuid.uuid4().hex[:16]
        now = time.time()
        async with self._db.engine.begin() as conn:
            await conn.execute(insert(db.cases).values(
                id=case_id, tenant=tenant, domain=domain,
                external_ref=external_ref, status="open", user_id=user_id,
                intake=intake, budget_usd=budget_usd,
                budget_tokens=budget_tokens, created_at=now, updated_at=now,
            ))
        return case_id

    async def get_case(self, case_id: str) -> dict | None:
        async with self._db.engine.connect() as conn:
            row = (await conn.execute(
                select(db.cases).where(db.cases.c.id == case_id))).first()
        return dict(row._mapping) if row else None

    async def find_case(self, tenant: str, domain: str, external_ref: str) -> dict | None:
        async with self._db.engine.connect() as conn:
            row = (await conn.execute(select(db.cases).where(
                db.cases.c.tenant == tenant, db.cases.c.domain == domain,
                db.cases.c.external_ref == external_ref))).first()
        return dict(row._mapping) if row else None

    async def update_case(self, case_id: str, **values: Any) -> None:
        values["updated_at"] = time.time()
        async with self._db.engine.begin() as conn:
            await conn.execute(
                update(db.cases).where(db.cases.c.id == case_id).values(**values))

    async def list_cases(self, tenant: str, status: str | None = None,
                         limit: int = 50) -> list[dict]:
        q = select(db.cases).where(db.cases.c.tenant == tenant)
        if status:
            q = q.where(db.cases.c.status == status)
        q = q.order_by(db.cases.c.created_at.desc()).limit(limit)
        async with self._db.engine.connect() as conn:
            return [dict(r._mapping) for r in (await conn.execute(q))]

    async def stalled(self, idle_seconds: float) -> list[str]:
        """Ids of open cases with no new item for `idle_seconds`."""
        cutoff = time.time() - idle_seconds
        last = (select(db.case_items.c.case_id, func.max(db.case_items.c.created_at).label("t"))
                .group_by(db.case_items.c.case_id).subquery())
        q = (select(db.cases.c.id)
             .outerjoin(last, last.c.case_id == db.cases.c.id)
             .where(db.cases.c.status == "open",
                    func.coalesce(last.c.t, db.cases.c.created_at) < cutoff))
        async with self._db.engine.connect() as conn:
            return [r[0] for r in await conn.execute(q)]

    # ---- sessions ------------------------------------------------------
    async def bind_session(self, case_id: str, session_id: str, agent_id: str,
                           agent_name: str, role: str) -> None:
        async with self._db.engine.begin() as conn:
            exists = (await conn.execute(select(db.case_sessions.c.session_id).where(
                db.case_sessions.c.session_id == session_id))).first()
            if exists:
                await conn.execute(update(db.case_sessions).where(
                    db.case_sessions.c.session_id == session_id).values(
                    case_id=case_id, agent_id=agent_id, agent_name=agent_name, role=role))
            else:
                await conn.execute(insert(db.case_sessions).values(
                    session_id=session_id, case_id=case_id, agent_id=agent_id,
                    agent_name=agent_name, role=role))

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
                  addressee: str | None = None) -> Item:
        """Append an item. The reference (F1, F2...) is allocated inside the
        transaction; concurrent writers that pick the same number retry."""
        prefix = PREFIX[kind]
        for attempt in range(8):
            try:
                async with self._db.engine.begin() as conn:
                    n = (await conn.execute(select(func.count()).select_from(db.case_items).where(
                        db.case_items.c.case_id == case_id,
                        db.case_items.c.kind == kind))).scalar_one()
                    ref = f"{prefix}{n + 1}"
                    now = time.time()
                    res = await conn.execute(insert(db.case_items).values(
                        case_id=case_id, ref=ref, kind=kind, author=author,
                        addressee=addressee, data=data, created_at=now))
                    return Item(res.inserted_primary_key[0], case_id, ref, kind, author,
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

    async def close_case(self, case_id: str, status: str, result: dict,
                         outbox_payload: dict) -> bool:
        """Close an open case and queue its result in one transaction.
        Returns False when the case was no longer open (nothing is written)."""
        async with self._db.engine.begin() as conn:
            res = await conn.execute(update(db.cases).where(
                db.cases.c.id == case_id, db.cases.c.status == "open").values(
                status=status, result=result, updated_at=time.time()))
            if res.rowcount == 0:
                return False
            await conn.execute(insert(db.outbox).values(
                case_id=case_id, kind="result", payload=outbox_payload,
                status="pending", attempts=0, created_at=time.time()))
        return True

    # ---- inbound dedupe ------------------------------------------------
    async def inbound_seen(self, tenant: str, domain: str, message_id: str) -> str | None:
        async with self._db.engine.connect() as conn:
            row = (await conn.execute(select(db.inbound.c.case_id).where(
                db.inbound.c.tenant == tenant, db.inbound.c.domain == domain,
                db.inbound.c.message_id == message_id))).first()
        return row[0] if row else None

    async def remember_inbound(self, tenant: str, domain: str, message_id: str,
                               case_id: str) -> str | None:
        """Return the case id seen before for this message, else record it."""
        async with self._db.engine.begin() as conn:
            row = (await conn.execute(select(db.inbound.c.case_id).where(
                db.inbound.c.tenant == tenant, db.inbound.c.domain == domain,
                db.inbound.c.message_id == message_id))).first()
            if row:
                return row[0]
            await conn.execute(insert(db.inbound).values(
                tenant=tenant, domain=domain, message_id=message_id,
                case_id=case_id, created_at=time.time()))
        return None
