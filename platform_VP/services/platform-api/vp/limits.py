"""Atomic money and RPM/TPM reservations, using integer micro-dollars."""

import math
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .config import settings
from .db import RateWindow, Reservation, Session, Wallet, now


class BudgetExceeded(Exception):
    pass


class RateExceeded(Exception):
    pass


def insert_for(db, table):
    return pg_insert(table) if db.bind.dialect.name == "postgresql" else sqlite_insert(table)


async def upsert_rate(db, key, bucket, requests, tokens):
    stmt = insert_for(db, RateWindow).values(
        key=key, bucket=bucket, requests=requests, tokens=tokens
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[RateWindow.key, RateWindow.bucket],
        set_={"requests": RateWindow.requests + requests, "tokens": RateWindow.tokens + tokens},
    ).returning(RateWindow)
    return (await db.execute(stmt)).scalar_one()


def upper_cost(model: dict) -> int:
    # Reserve the entire allowed input window: serialized tools/tokens and vendor-specific
    # tokenization cannot cause an underestimate. This is deliberately conservative.
    return math.ceil(
        (
            model["context_tokens"] * model["input_micros_per_million"]
            + model["max_output_tokens"] * model["output_micros_per_million"]
        )
        / 1_000_000
    )


async def reserve(
    db, session: Session, job, model: dict, rate_tokens: int | None = None
) -> Reservation:
    month = datetime.now(UTC).strftime("%Y-%m")
    await db.execute(
        insert_for(db, Wallet)
        .values(
            workspace=session.workspace,
            month=month,
            budget=settings.monthly_budget_micros,
            spent=0,
            reserved=0,
        )
        .on_conflict_do_nothing()
    )
    wallet = await db.scalar(
        select(Wallet)
        .where(
            Wallet.workspace == session.workspace,
            Wallet.month == month,
        )
        .with_for_update()
    )
    amount = upper_cost(model)
    if session.spent + session.reserved + amount > session.budget:
        raise BudgetExceeded("session_budget_exhausted")
    if wallet.spent + wallet.reserved + amount > wallet.budget:
        raise BudgetExceeded("workspace_budget_exhausted")
    rate = await upsert_rate(
        db,
        "model:" + model["id"],
        int(now() // 60),
        1,
        rate_tokens
        if rate_tokens is not None
        else model["context_tokens"] + model["max_output_tokens"],
    )
    if rate.requests > model["rpm"] or rate.tokens > model["tpm"]:
        raise RateExceeded("provider_rate_limit")
    session.reserved += amount
    wallet.reserved += amount
    reservation = Reservation(
        workspace=session.workspace,
        month=month,
        session_id=session.id,
        job_id=job.id,
        generation=job.generation,
        amount=amount,
        usage={
            "model_id": model["id"],
            "pricing_version": model["pricing_version"],
            "model_version": model.get("version"),
        },
    )
    db.add(reservation)
    await db.flush()
    return reservation


async def reconcile(db, reservation_id: str, model: dict, usage: dict | None):
    lookup = await db.get(Reservation, reservation_id)
    session = await db.scalar(
        select(Session)
        .where(
            Session.id == lookup.session_id,
        )
        .with_for_update()
    )
    reservation = await db.scalar(
        select(Reservation)
        .where(
            Reservation.id == reservation_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if reservation.status != "reserved":
        return
    wallet = await db.scalar(
        select(Wallet)
        .where(
            Wallet.workspace == reservation.workspace,
            Wallet.month == reservation.month,
        )
        .with_for_update()
    )
    # Missing usage/uncertain timeout is charged at the reservation bound and flagged.
    # Do not release money on restart; a provider may already have billed the call.
    if usage is None:
        charged = reservation.amount
        status = "estimated_uncertain"
    else:
        charged = math.ceil(
            (
                usage.get("input_tokens", 0) * model["input_micros_per_million"]
                + usage.get("output_tokens", 0) * model["output_micros_per_million"]
            )
            / 1_000_000
        )
        status = "usage_reported"
    session.reserved -= reservation.amount
    wallet.reserved -= reservation.amount
    session.spent += charged
    wallet.spent += charged
    reservation.status = status
    reservation.charged = charged
    reservation.usage = {**reservation.usage, **(usage or {}), "billing_verified": False}
