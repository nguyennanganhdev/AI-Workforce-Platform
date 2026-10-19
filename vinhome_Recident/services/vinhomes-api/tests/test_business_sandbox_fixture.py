"""No-key guards and real, isolated PostgreSQL business fixture acceptance."""

import asyncio
import os
from uuid import UUID

import pytest

from vinhomes_api import business_sandbox_fixture as fixture


def test_fixture_plan_replays_ids_and_separates_runs_and_repetitions():
    first = fixture.fixture_plan("repeatable", seed=41)
    assert first == fixture.fixture_plan("repeatable", seed=41)
    assert len(first) == len({row["channel_id"] for row in first}) == 72
    assert len({row["idempotency_key"] for row in first}) == 72
    assert not {row["channel_id"] for row in first} & {
        row["channel_id"] for row in fixture.fixture_plan("fresh-reset", seed=41)
    }
    assert first != fixture.fixture_plan("repeatable", seed=42)


@pytest.mark.parametrize("run", ["../production", "", "LiveTenant", "x" * 49])
def test_rejects_invalid_run_id(run):
    with pytest.raises(ValueError, match="run_id"):
        fixture.fixture_plan(run)


@pytest.mark.parametrize("url", [
    "postgresql://owner@127.0.0.1/production",
    "postgresql://owner@production.example/owner_pilot_test_" + "a" * 32,
])
def test_refuses_wrong_database_before_engine_creation(url, monkeypatch):
    monkeypatch.setattr(fixture, "create_async_engine", lambda *a, **k: pytest.fail("Engine must not be created"))
    with pytest.raises(ValueError, match="loopback owner_pilot_test"):
        asyncio.run(fixture.build_fixture(url, "guard-test"))


def test_real_fixture_intake_is_idempotent_and_a_fresh_run_has_fresh_tickets(tmp_path):
    # Explicit opt-in only: this is a NEW marked synthetic sandbox, never existing runtime config.
    url = os.getenv("BUSINESS_SANDBOX_TEST_URL")
    if not url:
        pytest.skip("Set BUSINESS_SANDBOX_TEST_URL to a fresh isolated marked sandbox")
    password = os.environ["BUSINESS_SANDBOX_TEST_RUNTIME_PASSWORD"]

    async def exercise():
        await fixture.initialize(url, tmp_path / "private", password)
        first = await fixture.build_fixture(url, "fixture-contract", seed=17)
        replay = await fixture.build_fixture(url, "fixture-contract", seed=17)
        assert first == replay
        second = await fixture.build_fixture(url, "fixture-reset", seed=17, scenarios=1)
        assert not {row["ticket_id"] for row in first["tickets"]} & {
            row["ticket_id"] for row in second["tickets"]
        }
        assert first["resident_user_id"].startswith("sim-resident-")
        assert len(first["staff"]) >= 2
        assert all(UUID(row["ticket_id"]) for row in first["tickets"])
        engine = fixture.create_async_engine(url.replace("postgresql:", "postgresql+asyncpg:", 1))
        try:
            async with engine.begin() as db:
                await db.execute(fixture.text("select set_config('app.tenant_id',:tenant,true)"), {"tenant": fixture.TENANT})
                ids = [UUID(row["ticket_id"]) for row in first["tickets"]]
                count = (await db.execute(fixture.text("select count(*) from tickets where id=any(:ids)"), {"ids": ids})).scalar_one()
                events = (await db.execute(fixture.text("select count(*) from ticket_events where ticket_id=any(:ids) and event_type='ticket.created'"), {"ids": ids})).scalar_one()
                assert count == events == 72
        finally:
            await engine.dispose()
    asyncio.run(exercise())
