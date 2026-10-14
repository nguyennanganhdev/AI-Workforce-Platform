"""Optional D3 PostgreSQL crash/reclaim gates in isolated test schemas."""

import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.workforce.e2e.async_tickets import test_phase_d_d3 as slice_checks
from tests.workforce.fixtures.phase_d_execution import D3CaseDriver


@pytest.mark.parametrize(
    "boundary", ["before_apply", "before_commit", "after_commit"]
)
def test_postgres_expired_provider_job_recovers_once(boundary):
    database_url = os.environ.get("WORKFORCE_TEST_POSTGRES_URL")
    if not database_url:
        pytest.skip("Dedicated WORKFORCE_TEST_POSTGRES_URL not supplied")

    async def scenario():
        schema = "wf_d3_test_" + uuid4().hex
        admin = create_async_engine(database_url)
        driver = D3CaseDriver(
            database_url, {"server_settings": {"search_path": schema}}
        )
        checks = slice_checks.D3RecoveryTests()
        checks.driver = driver
        try:
            async with admin.begin() as connection:
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await driver.setup()
            await checks._crash_and_recover(boundary)
        finally:
            if hasattr(driver, "env"):
                await driver.cleanup()
            async with admin.begin() as connection:
                await connection.execute(
                    text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
                )
            await admin.dispose()

    asyncio.run(scenario())
