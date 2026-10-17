"""Optional D4 gates on a dedicated DSN and per-case disposable schema."""

import asyncio
import os
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.workforce.fixtures.phase_d_execution import D3CaseDriver
from tests.workforce.lifecycle.releases import test_phase_d as release_checks


@pytest.mark.parametrize(
    "check",
    [
        "test_two_instances_publish_one_winner_without_duplicate_version",
        "test_concurrent_retry_same_command_returns_one_result",
        "test_edit_waits_for_publish_then_preserves_the_released_snapshot",
        "test_evaluation_cancel_waits_until_publish_commit",
    ],
)
def test_postgres_release_atomicity(check: str) -> None:
    database_url = os.environ.get("WORKFORCE_TEST_POSTGRES_URL")
    if not database_url:
        pytest.skip("Dedicated WORKFORCE_TEST_POSTGRES_URL not supplied")

    async def scenario() -> None:
        schema = "wf_d4_test_" + uuid4().hex
        admin = create_async_engine(database_url)
        driver = D3CaseDriver(
            database_url, {"server_settings": {"search_path": schema}}
        )
        checks: Any = release_checks.ReleaseTests()
        checks.driver = driver
        try:
            async with admin.begin() as tx:
                await tx.execute(text(f'CREATE SCHEMA "{schema}"'))
            await driver.setup()
            await checks.setup_release()
            await getattr(checks, check)()
        finally:
            if hasattr(driver, "env"):
                await driver.cleanup()
            async with admin.begin() as tx:
                await tx.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            await admin.dispose()

    asyncio.run(scenario())
