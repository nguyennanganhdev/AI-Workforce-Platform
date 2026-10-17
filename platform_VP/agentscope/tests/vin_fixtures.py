"""Shared N1/N2 authority fixture. Uses production auth migrations, never model IO.

Consumers: ``from vin_fixtures import authority`` with PYTHONPATH=src;tests.
``create_authority_schema``/``seed_authority`` also support integration fixtures.
"""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from cryptography.fernet import Fernet
from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import create_async_engine

from agentscope.app.vin_platform import VinPlatformService, QuotaPolicy
from agentscope.app.vin_platform import _tables as t
from agentscope.app.vin_platform._contracts import CatalogEntry, ResourceGrant


def create_authority_schema(connection):
    """Run the actual 0007/0008 auth DDL, including domain_id/area_id and FKs."""
    from agentscope.app.storage._sql import _tables
    folder = Path(_tables.__file__).parent / "_alembic" / "versions"
    with Operations.context(MigrationContext.configure(connection)):
        for filename in ("0007_auth.py", "0008_area_platform.py"):
            spec = importlib.util.spec_from_file_location("vin_fixture_" + filename[:-3], folder / filename)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.upgrade()
    t.metadata.create_all(connection)


async def seed_authority(engine):
    async with engine.begin() as db:
        await db.run_sync(create_authority_schema)
        for user, tenant, role in (("admin", "vin", "PLATFORM_ADMIN"), ("alice", "vin", "VIN_USER"),
                ("bob", "vin", "VIN_USER"), ("other", "foreign", "PLATFORM_ADMIN")):
            await db.execute(text("""INSERT INTO auth_users
                (id,tenant_id,email,username,password_hash,status,role,domain_id,area_id,created_at,updated_at)
                VALUES(:u,:t,:email,:u,'offline-not-a-login-hash','active',:r,NULL,NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"""),
                {"u": user, "t": tenant, "r": role, "email": user + "@fixture.invalid"})
            await db.execute(insert(t.accounts).values(user_id=user, tenant_id=tenant, eligible=True, revision=1))


async def seed_policy_catalog(authority, *, user_id="alice", environment="production", model="test-model"):
    """Explicit opt-in: ordinary authority tests can still verify missing policy."""
    admin = await authority.context("admin")
    await authority.set_policy(admin, "role:VIN_USER", QuotaPolicy(daily_tokens=100000, monthly_tokens=1000000,
        max_output_tokens=256, max_concurrency=2, embedding_daily_tokens=10000, storage_bytes=1000000,
        max_file_bytes=100000, models=[model], enabled=True))
    ident = await authority.publish_catalog(admin, CatalogEntry(kind="credential", resource_id="vin-platform-openai",
        owner_id="admin", name="Fixture managed provider", model_names=[model], environment=environment))
    await authority.grant(admin, ResourceGrant(catalog_id=ident, subject_kind="user", subject_id=user_id,
        permissions=["view", "bind", "execute"]))
    return await authority.context(user_id, environment=environment)


@pytest_asyncio.fixture
async def authority(tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "authority.db"))
    await seed_authority(engine)
    service = VinPlatformService(SimpleNamespace(_require_engine=lambda: engine), SimpleNamespace(),
        encryption_key=Fernet.generate_key())
    try:
        yield service
    finally:
        await engine.dispose()
