"""The cost ledger: one row per model call, summed by case, agent and model."""
from __future__ import annotations

import time

from sqlalchemy import func, insert, select

from . import db
from .providers import ModelCatalog


class CostService:
    def __init__(self, database: db.Database, catalog: ModelCatalog) -> None:
        self._db = database
        self._catalog = catalog

    async def record(self, *, tenant: str, case_id: str | None, session_id: str,
                     agent_id: str, agent_name: str, model: str,
                     input_tokens: int, output_tokens: int,
                     cache_read: int = 0, cache_write: int = 0) -> float:
        spec = self._catalog.by_name(model)
        cost = spec.cost(input_tokens, output_tokens, cache_read, cache_write) if spec else 0.0
        async with self._db.engine.begin() as conn:
            await conn.execute(insert(db.ledger).values(
                tenant=tenant, case_id=case_id, session_id=session_id,
                agent_id=agent_id, agent_name=agent_name[:80], model=model[:120],
                tier=spec.tier if spec else None, input_tokens=input_tokens,
                output_tokens=output_tokens, cache_read_tokens=cache_read,
                cache_write_tokens=cache_write, cost_usd=cost,
                priced=1 if (spec and spec.priced) else 0, created_at=time.time()))
        return cost

    async def case_totals(self, case_id: str) -> dict:
        L = db.ledger.c
        q = select(func.coalesce(func.sum(L.cost_usd), 0.0),
                   func.coalesce(func.sum(L.input_tokens), 0),
                   func.coalesce(func.sum(L.output_tokens), 0),
                   func.coalesce(func.sum(L.cache_read_tokens), 0),
                   func.count(),
                   func.coalesce(func.sum(1 - L.priced), 0)).where(L.case_id == case_id)
        async with self._db.engine.connect() as conn:
            usd, tin, tout, cache, calls, unpriced = (await conn.execute(q)).one()
        return {"cost_usd": float(usd), "input_tokens": int(tin), "output_tokens": int(tout),
                "cache_read_tokens": int(cache), "calls": int(calls), "unpriced_calls": int(unpriced)}

    async def breakdown(self, case_id: str, by: str = "agent_name") -> list[dict]:
        L = db.ledger.c
        col = getattr(L, by)
        q = (select(col, func.sum(L.cost_usd), func.sum(L.input_tokens),
                    func.sum(L.output_tokens), func.count())
             .where(L.case_id == case_id).group_by(col))
        async with self._db.engine.connect() as conn:
            return [{by: r[0], "cost_usd": float(r[1] or 0), "input_tokens": int(r[2] or 0),
                     "output_tokens": int(r[3] or 0), "calls": int(r[4])}
                    for r in await conn.execute(q)]

    async def tenant_summary(self, tenant: str, since: float = 0.0) -> list[dict]:
        L = db.ledger.c
        q = (select(L.model, func.sum(L.cost_usd), func.sum(L.input_tokens),
                    func.sum(L.output_tokens), func.count())
             .where(L.tenant == tenant, L.created_at >= since).group_by(L.model))
        async with self._db.engine.connect() as conn:
            return [{"model": r[0], "cost_usd": float(r[1] or 0), "input_tokens": int(r[2] or 0),
                     "output_tokens": int(r[3] or 0), "calls": int(r[4])}
                    for r in await conn.execute(q)]
