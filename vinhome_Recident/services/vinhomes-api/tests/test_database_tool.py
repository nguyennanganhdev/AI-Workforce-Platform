"""The tool that registers clients and the one that erases everything (docs/domain/HOP_DONG_TICH_HOP.md section 8)."""

import asyncio
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import asyncpg
import pytest
from test_integration_auth import outsider
from test_resident_contract import TENANT, sql
from test_resident_contract import database as database  # noqa: F401 -- pytest fixture export

from vinhomes_api import database as tool


def test_a_registered_client_gets_a_secret_that_works_and_only_its_hash_is_kept(database):
    secret = asyncio.run(tool.client(database["admin"], "platform-test", "platform", False,
                                     {"resident": ["read"], "staff": ["read"]}, str(TENANT)))
    assert secret.startswith("ics_") and len(secret) > 40
    stored = sql(database, "select secret_hash,levels::text as levels,kind,accepts_cases from integration_clients where id='platform-test'")[0]
    assert secret not in str(stored) and len(stored["secret_hash"]) == 64
    with outsider(database) as c:
        tools = c.get("/integration/v1/tools", headers={"X-Client-Id": "platform-test", "Authorization": "Bearer " + secret})
        assert tools.status_code == 200 and tools.json()["tools"]
        assert all(t["level"] == "read" for t in tools.json()["tools"])
    # registering again rotates the secret: the old one stops working at once
    newer = asyncio.run(tool.client(database["admin"], "platform-test", "platform", False, {"resident": ["read"], "staff": ["read"]}, str(TENANT)))
    with outsider(database) as c:
        assert c.get("/integration/v1/tools", headers={"X-Client-Id": "platform-test", "Authorization": "Bearer " + secret}).status_code == 401
        assert c.get("/integration/v1/tools", headers={"X-Client-Id": "platform-test", "Authorization": "Bearer " + newer}).status_code == 200


def test_reset_needs_the_databases_own_name_and_leaves_an_empty_schema(database):
    admin = database["admin"]
    parts = urlsplit(admin.replace("postgresql+asyncpg:", "postgresql:"))
    name = "reset_probe_" + uuid4().hex[:12]
    url = urlunsplit(parts._replace(path="/" + name))

    async def run():
        await tool.create(admin, name)
        try:
            await tool.migrate(url)
            await tool.seed(url)
            with pytest.raises(SystemExit):
                await tool.reset(url, "some_other_database")
            conn = await asyncpg.connect(url)
            try:
                assert await conn.fetchval("select count(*) from tickets") > 0         # a wrong name erased nothing
            finally:
                await conn.close()
            await tool.reset(url, name)
            conn = await asyncpg.connect(url)
            try:
                assert await conn.fetchval("select count(*) from tickets") == 0
                assert await conn.fetchval("select count(*) from schema_migrations") == len(tool.migration_files())
                assert await conn.fetchval("select count(*) from state_transitions") > 50   # reference data came back with the migrations
            finally:
                await conn.close()
        finally:
            conn = await asyncpg.connect(admin.replace("postgresql+asyncpg:", "postgresql:"))
            try:
                await conn.execute(f'drop database if exists "{name}" with (force)')
            finally:
                await conn.close()

    asyncio.run(run())
