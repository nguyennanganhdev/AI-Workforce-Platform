import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from vp import integrations, maintenance, queue, runtime
from vp.db import Artifact, Job, Membership, Record, Reservation, Session, now, transaction
from vp.domain import create_session, submit_chat
from vp.evaluations import record_evaluation
from vp.limits import RateExceeded, reconcile, reserve
from vp.queue import claim, fence, worker_loop
from vp.runtime import SafeRuntimeError


async def test_revoked_owner_cannot_start_model_or_tool(leased, monkeypatch):
    _, job = leased
    async with transaction() as db:
        (await db.get(Membership, ("default", "admin"))).role = "viewer"
    called = []
    monkeypatch.setattr(runtime, "create_model", lambda *args: called.append(args))
    with pytest.raises(SafeRuntimeError, match="owner_access_revoked"):
        await runtime.execute_agent(job)
    with pytest.raises(SafeRuntimeError, match="owner_access_revoked"):
        await integrations.execute_approved(job)
    assert called == []


@pytest.mark.parametrize("change_config", [True, False])
async def test_approved_tool_config_binding_and_success_recovery(
    leased, monkeypatch, change_config
):
    sid, job = leased
    async with transaction() as db:
        db.add(
            Record(
                id="mcp",
                workspace="default",
                owner="admin",
                kind="mcp",
                version=2,
                body={
                    "enabled": True,
                    "url": "https://new.example/mcp",
                    "allowed_tools": ["write"],
                },
            )
        )
        db.add(
            Artifact(
                id="execution",
                workspace="default",
                session_id=sid,
                agent_id="coordinator",
                kind="tool_execution",
                turn=1,
                body={
                    "status": "approved" if change_config else "succeeded",
                    "mcp_id": "mcp",
                    "config_version": 1,
                    "tool": "write",
                    "arguments": {"value": "exact"},
                    "phase": "work",
                    "round": 0,
                },
            )
        )
        current = await db.get(Job, job.id)
        current.body = {**current.body, "execution_id": "execution"}
        job.body = current.body
    calls = []

    @asynccontextmanager
    async def connection(config):
        calls.append(config)
        yield SimpleNamespace()

    monkeypatch.setattr(integrations, "connection", connection)
    if change_config:
        with pytest.raises(SafeRuntimeError, match="tool_config_changed"):
            await integrations.execute_approved(job)
    else:
        await integrations.execute_approved(job)
        async with transaction() as db:
            assert (await db.get(Artifact, "execution")).body["status"] == "succeeded"
            assert (await db.get(Job, job.id)).status == "done"
            assert (await db.get(Session, sid)).status == "running"
    assert calls == []


async def test_rate_delays_do_not_consume_recovery_attempts(leased, monkeypatch):
    _, job = leased
    # Return the initial fixture claim to the queue, then force controlled delays
    # available immediately. No wall-clock minute sleeps or provider network I/O.
    async with transaction() as db:
        current = await db.get(Job, job.id)
        current.status, current.attempts = "queued", 0
    original_claim = queue.claim

    async def immediate_claim(*args):
        async with transaction() as db:
            current = await db.get(Job, job.id)
            if current.status == "queued":
                current.available = now() - 1
        return await original_claim(*args)

    monkeypatch.setattr(queue, "claim", immediate_claim)
    stop = asyncio.Event()
    executions = []

    async def execute(current):
        executions.append(current.generation)
        if len(executions) <= 4:
            raise RateExceeded()
        async with transaction() as db:
            session, active = await fence(db, current.id, current.generation)
            active.status, session.status = "done", "idle"
        stop.set()

    await asyncio.wait_for(worker_loop(0, stop, execute), 10)
    assert len(executions) == 5
    async with transaction() as db:
        current = await db.get(Job, job.id)
        assert current.status == "done" and current.attempts == 1


async def test_evaluation_merge_refreshes_cached_row(principal, registry, isolated_database):
    if isolated_database.dialect.name != "postgresql":
        pytest.skip("PostgreSQL concurrent evaluation row locks")
    async with transaction() as db:
        db.add(
            Record(
                id="eval",
                workspace="default",
                kind="evaluations",
                owner="admin",
                body={"cases": [{"expected_status": "needs_input"}] * 2, "results": {}},
            )
        )
        sessions = [await create_session(db, principal, str(i), registry, 500000) for i in range(2)]
        for i, session in enumerate(sessions):
            session.board = {**session.board, "evaluation": {"run_id": "eval", "case": i}}
        ids = [session.id for session in sessions]
    first_locked, second_cached = asyncio.Event(), asyncio.Event()

    async def first():
        async with transaction() as db:
            await db.scalar(select(Record).where(Record.id == "eval").with_for_update())
            first_locked.set()
            await second_cached.wait()
            await record_evaluation(db, await db.get(Session, ids[0]), {"status": "needs_input"})

    async def second():
        await first_locked.wait()
        async with transaction() as db:
            cached = await db.get(Record, "eval")
            assert not cached.body["results"]
            second_cached.set()
            await record_evaluation(db, await db.get(Session, ids[1]), {"status": "needs_input"})

    await asyncio.wait_for(asyncio.gather(first(), second()), 10)
    async with transaction() as db:
        result = (await db.get(Record, "eval")).body
        assert result["status"] == "complete" and result["passed"]
        assert set(result["results"]) == {"0", "1"}


async def test_maintenance_releases_wallet_before_next_session(
    principal, registry, isolated_database, monkeypatch
):
    if isolated_database.dialect.name != "postgresql":
        pytest.skip("PostgreSQL session/wallet lock interleaving")
    price = {
        "id": "paid",
        "context_tokens": 1000,
        "max_output_tokens": 0,
        "input_micros_per_million": 1000000,
        "output_micros_per_million": 0,
        "pricing_version": "fixture",
        "rpm": 100,
        "tpm": 100000,
    }
    ids, reservations = [], []
    for i in range(2):
        async with transaction() as db:
            session = await create_session(db, principal, str(i), registry, 500000)
            await submit_chat(db, principal, session.id, "Verify", f"request-{i:08}")
            ids.append(session.id)
        job = await claim("fixture")
        async with transaction() as db:
            session, current = await fence(db, job.id, job.generation)
            reservation = await reserve(db, session, current, price)
            reservation.created = i
            reservations.append(reservation.id)
            current.status, current.lease_until = "done", now() - 1
    first_reconciled, second_session_locked = asyncio.Event(), asyncio.Event()

    async def observed_reconcile(db, rid, model, usage):
        await reconcile(db, rid, model, usage)
        if rid == reservations[0]:
            first_reconciled.set()
            await second_session_locked.wait()

    monkeypatch.setattr(maintenance, "reconcile", observed_reconcile)

    async def concurrent_runtime():
        await first_reconciled.wait()
        async with transaction() as db:
            await db.scalar(select(Session).where(Session.id == ids[1]).with_for_update())
            second_session_locked.set()
            await reconcile(db, reservations[1], {}, None)

    await asyncio.wait_for(asyncio.gather(maintenance.settle_abandoned(), concurrent_runtime()), 10)
    async with transaction() as db:
        rows = (await db.scalars(select(Reservation))).all()
        assert all(row.status == "estimated_uncertain" for row in rows)


async def test_explicit_retry_cannot_repeat_external_effect(client, leased):
    sid, job = leased
    async with transaction() as db:
        current = await db.get(Job, job.id)
        current.status, current.error = "failed", "provider_error"
        (await db.get(Session, sid)).status = "needs_review"
        db.add(
            Artifact(
                workspace="default",
                session_id=sid,
                kind="tool_execution",
                turn=1,
                body={"read_only": False, "status": "uncertain"},
            )
        )
    response = await client.post(f"/api/operations/jobs/{job.id}/retry")
    assert response.status_code == 409
