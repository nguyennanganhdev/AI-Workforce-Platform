import asyncio

import pytest
from sqlalchemy import select

from vp.automation import advance_workflow, schedule_tick
from vp.config import settings
from vp.db import Job, Record, Reservation, Session, Wallet, transaction
from vp.domain import create_session, submit_chat
from vp.limits import BudgetExceeded, reserve
from vp.queue import claim, fence
from vp.schemas import AgentResult


async def test_workflow_human_gate_is_pinned_and_single_use(client, registry):
    workflow = (
        await client.post(
            "/api/resources/workflows",
            json={
                "name": "Two stages",
                "agent_ids": registry,
                "steps": ["Analyze", "Verify"],
                "human_gate": True,
            },
        )
    ).json()
    session = (await client.post(f"/api/workflows/{workflow['id']}/run")).json()
    async with transaction() as db:
        row = await db.get(Session, session["id"])
        row.status = "idle"
        task = await db.scalar(select(Job).where(Job.session_id == row.id))
        task.status = "done"
        await advance_workflow(db, row, AgentResult(status="complete", answer="Verified result"))
        config = await db.get(Record, workflow["id"])
        config.body = {**config.body, "steps": ["Changed", "Injected new step"]}
    body = {"approve": True, "reason": "Verified previous stage"}
    response = await client.post(f"/api/sessions/{session['id']}/workflow-gate", json=body)
    assert response.status_code == 200
    assert response.json()["board"]["goal"] == "Verify" and response.json()["turn"] == 2
    assert (
        await client.post(f"/api/sessions/{session['id']}/workflow-gate", json=body)
    ).status_code == 409


async def test_webhook_fixed_identity_and_payload_dedup(client, registry):
    token = "synthetic-webhook-token-at-least-32-characters"
    channel = (
        await client.post(
            "/api/resources/channels",
            json={
                "name": "Inbound",
                "agent_ids": registry,
                "token": token,
                "enabled": True,
            },
        )
    ).json()
    assert "token" not in channel and "token_hash" not in channel
    path = f"/api/channels/{channel['id']}/messages"
    body = {"text": "Verify source", "idempotency_key": "webhook-request"}
    assert (await client.post(path, json=body)).status_code == 401
    headers = {"Authorization": "Bearer " + token}
    first = await client.post(path, json=body, headers=headers)
    duplicate = await client.post(path, json=body, headers=headers)
    assert first.status_code == duplicate.status_code == 202 and first.json() == duplicate.json()
    assert (
        await client.post(path, json={**body, "text": "Different"}, headers=headers)
    ).status_code == 409
    async with transaction() as db:
        session = await db.get(Session, first.json()["session_id"])
        assert session.owner == "admin" and session.workspace == "default"


async def test_parallel_scheduler_coalesces_due_tick(client, registry, isolated_database):
    if isolated_database.dialect.name != "postgresql":
        pytest.skip("PostgreSQL scheduler ownership")
    workflow = (
        await client.post(
            "/api/resources/workflows",
            json={
                "name": "Scheduled",
                "agent_ids": registry,
                "steps": ["Verify"],
                "human_gate": True,
            },
        )
    ).json()
    schedule = (
        await client.post(
            "/api/resources/schedules",
            json={
                "name": "Due",
                "workflow_id": workflow["id"],
                "cron": "0 * * * *",
                "enabled": True,
            },
        )
    ).json()
    async with transaction() as db:
        row = await db.get(Record, schedule["id"])
        row.body = {**row.body, "next_run": 1}
    await asyncio.wait_for(asyncio.gather(schedule_tick(), schedule_tick()), 10)
    async with transaction() as db:
        sessions = (await db.scalars(select(Session))).all()
        assert len(sessions) == 1
        assert (await db.get(Record, schedule["id"])).body["last_session_id"] == sessions[0].id


async def test_parallel_reservations_cannot_overspend_wallet(
    principal, registry, isolated_database, monkeypatch
):
    if isolated_database.dialect.name != "postgresql":
        pytest.skip("PostgreSQL atomic workspace wallet")
    monkeypatch.setattr(settings, "monthly_budget_micros", 2000)
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
    jobs = []
    for i in range(4):
        async with transaction() as db:
            session = await create_session(db, principal, str(i), registry, 500000)
            await submit_chat(db, principal, session.id, "Verify", f"reserve-{i:08}")
        jobs.append(await claim("budget"))

    async def hold(job):
        try:
            async with transaction() as db:
                session, current = await fence(db, job.id, job.generation)
                await reserve(db, session, current, price)
            return True
        except BudgetExceeded:
            return False

    results = await asyncio.wait_for(asyncio.gather(*(hold(job) for job in jobs)), 10)
    assert sum(results) == 2
    async with transaction() as db:
        wallet = await db.scalar(select(Wallet))
        assert wallet.reserved == 2000 and wallet.spent == 0
        assert len((await db.scalars(select(Reservation))).all()) == 2
