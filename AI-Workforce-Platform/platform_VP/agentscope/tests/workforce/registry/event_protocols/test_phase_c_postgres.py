# -*- coding: utf-8 -*-
"""Optional PostgreSQL gate for async protocol CAS and uniqueness."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import unittest
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from agentscope.app.workforce.contracts import (
    Scope,
    WorkforceContractError,
    WorkforceErrorCode,
)
from agentscope.app.workforce.foundation import (
    SqlAlchemyUnitOfWorkFactory,
)
from agentscope.app.workforce.registry.event_protocols import (
    AsyncToolProtocol,
    SqlAsyncProtocolProvider,
)
from agentscope.app.workforce.registry.event_protocols._tables import metadata


POSTGRES_URL = os.environ.get("WORKFORCE_TEST_POSTGRES_URL")


@unittest.skipUnless(
    POSTGRES_URL,
    "dedicated PostgreSQL test DSN not supplied",
)
class ProtocolPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def test_protocol_publish_compare_and_set(self):
        sample_path = (
            Path(__file__).resolve().parents[4]
            / "docs/workforce/handoffs/nguyen-phuong-dong"
            / "phase_a_samples.json"
        )
        samples = json.loads(sample_path.read_text(encoding="utf-8"))
        base = AsyncToolProtocol.model_validate(
            samples["protocols"]["provider_event"],
        )
        first = AsyncToolProtocol.model_validate(
            base.model_dump() | {"protocol_version": "2"},
        )
        second = AsyncToolProtocol.model_validate(
            base.model_dump()
            | {"protocol_version": "3", "timeout_seconds": 7200},
        )
        scope = Scope(
            tenant_id="tenant-1",
            domain_id="domain-1",
            area_id="area-1",
            manager_account_id="manager-1",
        )
        schema = "wf_registry_test_" + uuid4().hex
        admin = create_async_engine(POSTGRES_URL)
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(
            POSTGRES_URL,
            connect_args={"server_settings": {"search_path": schema}},
        )
        try:
            async with engine.begin() as connection:
                await connection.run_sync(metadata.create_all)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            provider = SqlAsyncProtocolProvider(
                SqlAlchemyUnitOfWorkFactory(sessions),
            )

            async def load_context(actor, envelope):
                raise AssertionError("normalization is outside this test")

            service = provider.bind(scope, load_context)
            original = await service.publish(base)
            outcomes = await asyncio.gather(
                service.publish(first, original),
                service.publish(second, original),
                return_exceptions=True,
            )
            successes = [
                item for item in outcomes if not isinstance(item, Exception)
            ]
            conflicts = [
                item for item in outcomes if isinstance(item, Exception)
            ]
            self.assertEqual(1, len(successes))
            self.assertEqual(1, len(conflicts))
            self.assertIsInstance(conflicts[0], WorkforceContractError)
            self.assertEqual(
                WorkforceErrorCode.REVISION_CONFLICT,
                conflicts[0].code,
            )
            current = await service.get_snapshot(scope, base.tool_version_id)
            self.assertEqual(current, successes[0])
        finally:
            await engine.dispose()
            async with admin.begin() as connection:
                await connection.execute(
                    text(f'DROP SCHEMA "{schema}" CASCADE'),
                )
            await admin.dispose()

if __name__ == "__main__":
    unittest.main()
