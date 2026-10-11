"""Dedicated PostgreSQL C6 gate; never treat SQLite as race evidence."""

import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.workforce.e2e.async_tickets import test_phase_c_c6 as slice_checks
from tests.workforce.fixtures.phase_c_e2e import RawProviderCaseDriver, SCOPE


def test_postgres_raw_http_duplicate_apply_and_continuation_once():
    database_url = os.environ.get("WORKFORCE_TEST_POSTGRES_URL")
    if not database_url:
        pytest.skip("Dedicated WORKFORCE_TEST_POSTGRES_URL not supplied")

    async def scenario():
        # Create/drop only this random schema, never shared tables.
        schema = "wf_c6_test_" + uuid4().hex
        admin = create_async_engine(database_url)
        driver = RawProviderCaseDriver(
            database_url, {"server_settings": {"search_path": schema}}
        )
        checks = slice_checks.C6SliceTests()
        checks.driver = driver
        try:
            async with admin.begin() as conn:
                await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            await driver.setup()
            _, workflow_id, operation = await checks.create_operation()
            event = checks.event(operation, "pg-complete", 4, "completed")
            responses = await asyncio.gather(
                *[driver.send(event) for _ in range(8)]
            )
            assert all(r.status_code == 202 for r in responses)
            receipt_ids = {r.json()["receipt_id"] for r in responses}
            assert len(receipt_ids) == 1
            receipt_id = receipt_ids.pop()
            before = await driver.env.workflows_repo.load(SCOPE, workflow_id)
            outcomes = await asyncio.gather(
                *[driver.processor.process(receipt_id) for _ in range(8)]
            )
            assert set(outcomes) == {"applied"}
            after = await driver.env.workflows_repo.load(SCOPE, workflow_id)
            assert after.workflow.revision == before.workflow.revision + 1
            assert (
                after.checkpoint.protocol_pins
                == before.checkpoint.protocol_pins
            )
            calls = driver.model.calls
            # The original durable provider job now observes the applied inbox.
            await checks.run_job("completed")
            await checks.run_job("completed")
            assert driver.model.calls == calls + 1
            assert driver.provider.calls == 1
            assert (await driver.worker.run_once()).status == "idle"
        finally:
            if hasattr(driver, "env"):
                await driver.cleanup()
            async with admin.begin() as conn:
                await conn.execute(
                    text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
                )
            await admin.dispose()

    asyncio.run(scenario())
