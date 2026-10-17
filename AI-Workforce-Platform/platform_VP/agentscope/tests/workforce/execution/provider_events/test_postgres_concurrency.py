"""
Real PostgreSQL acceptance gate; SQLite does not prove locks or commit order.
"""

import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from execution_fakes import (
    PROVIDER,
    SCOPE_A,
    approved_call,
    event_fixture,
    harness,
)

POSTGRES_URL = os.environ.get("WORKFORCE_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason=(
        "Dedicated PostgreSQL test DSN not supplied; "
        "Docker daemon unavailable in this session"
    ),
)


def test_postgres_parallel_consent_execution_and_inbox_apply_once():
    async def scenario():
        # Only remove the random schema this test created, never existing
        # tables.
        schema = "wf_execution_test_" + uuid4().hex
        admin = create_async_engine(POSTGRES_URL)
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        try:
            async with harness(
                POSTGRES_URL,
                tracking=True,
                connect_args={"server_settings": {"search_path": schema}},
            ) as env:
                call = await approved_call(env)
                results = await asyncio.gather(
                    *[env.gateway.execute(SCOPE_A, call) for _ in range(8)]
                )
                assert env.provider.calls == 1
                assert all(
                    r["status"] in {"executing", "succeeded"} for r in results
                )
                op = (
                    await env.operations.get_for_workflow(
                        SCOPE_A, "workflow-A"
                    )
                )[0]
                event = event_fixture(
                    job_id=op["external_job_id"], version=2, status="completed"
                )
                receipts = await asyncio.gather(
                    *[env.ingress.accept(PROVIDER, event) for _ in range(8)]
                )
                assert len({r["receipt_id"] for r in receipts}) == 1
                outcomes = await asyncio.gather(
                    *[
                        env.processor.process(receipts[0]["receipt_id"])
                        for _ in range(8)
                    ]
                )
                assert set(outcomes) == {"applied"}
                async with env.repo.transaction() as uow:
                    from execution_fakes import test_events
                    from sqlalchemy import select

                    rows = (
                        (await uow.execute(select(test_events)))
                        .mappings()
                        .all()
                    )
                    assert sum(r["id"].startswith("apply-") for r in rows) == 1
        finally:
            async with admin.begin() as connection:
                await connection.execute(
                    text(f'DROP SCHEMA "{schema}" CASCADE')
                )
            await admin.dispose()

    asyncio.run(scenario())
