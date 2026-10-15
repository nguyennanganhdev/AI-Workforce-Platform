"""Project approval imports sourced master references and catalog without manufacturing operational people."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import asyncpg
import pytest
from test_resident_contract import (
    database as database,  # noqa: PLC0414 -- pytest fixture export
)
from vinhomes_api import database as tool
from vinhomes_api.bootstrap import bootstrap
from vinhomes_api.owner_review import load

PROPOSALS = Path(
    os.getenv(
        "VINHOMES_TEST_PROPOSAL_DIR",
        str(
            Path(__file__).resolve().parents[3] / "deploy/owner-data-proposals/20261014"
        ),
    )
)


def test_approval_import_is_atomic_idempotent_and_keeps_unknowns_unverified(
    database, tmp_path
):
    name = "owner_review_test_" + uuid4().hex
    parts = urlsplit(database["admin"])
    target = urlunsplit(parts._replace(path="/" + name))
    approval = tmp_path / "approval.json"
    approval.write_text(
        json.dumps(
            {
                "approval_kind": "project_scope",
                "user_statement": "Isolated test approval only",
                "proposal_snapshot_sha256": hashlib.sha256(
                    (PROPOSALS / "proposals.jsonl").read_bytes()
                ).hexdigest(),
            }
        ),
        encoding="utf-8",
    )

    async def check():
        await tool.create(database["admin"], name)
        try:
            await tool.migrate(target)
            await bootstrap(target)
            result = await load(target, PROPOSALS, approval)
            assert (
                result["project_approved_records"] == 113
                and result["geography_zones"] == 25
                and result["geography_buildings"] == 30
            )
            assert await load(target, PROPOSALS, approval) == result
            await tool.role(target, urlsplit(database["runtime"]).username, None)
            conn = await asyncpg.connect(target)
            try:
                assert (
                    await conn.fetchval("select count(*) from owner_data_records")
                    == 113
                )
                assert (
                    await conn.fetchval(
                        "select count(*) from owner_data_records where operational_verified"
                    )
                    == 0
                )
                assert (
                    await conn.fetchval(
                        "select count(*) from zones where status='inactive'"
                    )
                    == 25
                )
                assert (
                    await conn.fetchval(
                        "select count(*) from buildings where status='inactive'"
                    )
                    == 30
                )
                assert (
                    await conn.fetchval(
                        "select count(*) from domain_service_catalog where not operational_enabled"
                    )
                    == 34
                )
                assert (
                    await conn.fetchval(
                        "select count(*) from domain_service_catalog where policy->>'fee_amount' is not null"
                    )
                    == 0
                )
                for table in (
                    "users",
                    "unit_residents",
                    "units",
                    "staff_profiles",
                    "staff_shifts",
                ):
                    assert await conn.fetchval("select count(*) from " + table) == 0
            finally:
                await conn.close()
            runtime = urlunsplit(
                urlsplit(
                    database["runtime"].replace("postgresql+asyncpg:", "postgresql:")
                )._replace(path="/" + name)
            )
            conn = await asyncpg.connect(runtime)
            try:
                async with conn.transaction():
                    await conn.execute(
                        "select set_config('app.tenant_id',$1,true)", str(uuid4())
                    )
                    assert (
                        await conn.fetchval("select count(*) from owner_data_records")
                        == 0
                    )
            finally:
                await conn.close()
            changed = json.loads(approval.read_text(encoding="utf-8"))
            changed["proposal_snapshot_sha256"] = "0" * 64
            approval.write_text(json.dumps(changed))
            with pytest.raises(ValueError, match="snapshot"):
                await load(target, PROPOSALS, approval)
        finally:
            conn = await asyncpg.connect(database["admin"])
            try:
                await conn.execute('DROP DATABASE IF EXISTS "' + name + '"')
            finally:
                await conn.close()

    asyncio.run(check())
