"""Reference migration on SQL/Redis plus real PostgreSQL authority races."""

import asyncio
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import pytest
from sqlalchemy import insert, text

from agentscope.app.storage import AsyncSQLAlchemyStorage
from agentscope.app.vin_platform import PlatformError, QuotaPolicy, VinPlatformService
from agentscope.app.vin_platform import _tables as t
from agentscope.credential import OpenAICredential


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter", ["sql", "redis"])
async def test_reference_cas_preserves_ids_and_other_keys(adapter, tmp_path):
    from storage_redis_knowledge_base_test import make_storage
    storage = make_storage() if adapter == "redis" else AsyncSQLAlchemyStorage("sqlite+aiosqlite:///" + str(tmp_path / "storage.db"))
    if adapter == "sql":
        await storage.__aenter__()
    try:
        ident = await storage.upsert_credential("alice", OpenAICredential(api_key="offline-old-key", name="test"))
        before = await storage.get_credential("alice", ident)
        replacement = {**before.data, "api_key": "server-managed", "secret_ref": "vin:platform-openai"}
        assert not await storage.replace_credential_data("bob", ident, before.data, replacement)
        assert await storage.replace_credential_data("alice", ident, before.data, replacement)
        assert not await storage.replace_credential_data("alice", ident, before.data, replacement)
        after = await storage.get_credential("alice", ident)
        assert after.id == before.id and after.created_at == before.created_at
        assert after.data == replacement
    finally:
        if adapter == "sql":
            await storage.__aexit__(None, None, None)


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter", ["sql", "redis"])
async def test_batch_agent_activation_rolls_back_on_any_conflict(adapter, tmp_path):
    from storage_redis_knowledge_base_test import make_storage
    from storage_sql_test import _agent_record
    from agentscope.app.storage._base import AgentRevisionConflict
    storage = make_storage() if adapter == "redis" else AsyncSQLAlchemyStorage("sqlite+aiosqlite:///" + str(tmp_path / "agents.db"))
    if adapter == "sql":
        await storage.__aenter__()
    try:
        first, second = _agent_record("alice", "one"), _agent_record("alice", "two")
        await storage.activate_agents_batch("alice", [first, second])
        assert first.storage_revision == second.storage_revision == 1
        first.data.name, second.data.name = "new one", "new two"
        second.storage_revision = 0
        with pytest.raises(AgentRevisionConflict):
            await storage.activate_agents_batch("alice", [first, second])
        assert (await storage.get_agent("alice", first.id)).data.name == "one"
        second.storage_revision = 1
        await storage.activate_agents_batch("alice", [first, second])
        assert (await storage.get_agent("alice", first.id)).data.name == "new one"
        assert await storage.list_agents("bob") == []
    finally:
        if adapter == "sql":
            await storage.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_expand_migration_and_postgres_race(tmp_path):
    admin_url = os.environ.get("VIN_TEST_ADMIN_URL")
    if not admin_url:
        pytest.skip("VIN_TEST_ADMIN_URL for disposable loopback PostgreSQL required")
    parsed = urlsplit(admin_url.replace("postgresql+asyncpg:", "postgresql:"))
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Disposable loopback database only")
    import asyncpg
    from alembic import command
    from alembic.config import Config
    from sqlalchemy.ext.asyncio import create_async_engine
    name = "vin_authority_test_" + uuid4().hex
    control = await asyncpg.connect(admin_url)
    await control.execute('CREATE DATABASE "' + name + '"')
    url = urlunsplit(parsed._replace(scheme="postgresql+asyncpg", path="/" + name))
    engine = create_async_engine(url)
    try:
        cfg = Config(str(Path(__file__).parents[1] / "src/agentscope/app/storage/_sql/_alembic/alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", url)
        await asyncio.to_thread(command.upgrade, cfg, "0022_personal_job_owner")
        async with engine.begin() as db:
            await db.execute(text("""INSERT INTO wf_durable_jobs
                (id,owner_kind,owner_namespace,tenant_id,domain_id,area_id,manager_account_id,provider_integration_id,
                 job_type,payload,payload_hash,idempotency_key,status,attempt,max_attempts,not_before,fencing_token,created_at,updated_at)
                VALUES('legacy-scope','scope','legacy-scope','test','domain','area','manager',NULL,
                  'fixture','{}','fixture','legacy-scope-key','pending',0,1,CURRENT_TIMESTAMP,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
                  ('legacy-provider','provider','legacy-provider','test',NULL,NULL,NULL,'provider',
                  'fixture','{}','fixture','legacy-provider-key','pending',0,1,CURRENT_TIMESTAMP,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"""))
            await db.execute(text("INSERT INTO vin_memberships (id,tenant_id,user_id,group_id,active) VALUES ('legacy-member','test','alice','pilot',true)"))
            await db.execute(text("INSERT INTO vin_grants (id,tenant_id,catalog_id,subject_kind,subject_id,permissions,active) VALUES ('legacy-grant','test','catalog','user','alice','[]',true)"))
        await asyncio.to_thread(command.upgrade, cfg, "head")
        await asyncio.to_thread(command.upgrade, cfg, "head")
        async with engine.begin() as db:
            assert (await db.execute(text("SELECT version_num FROM alembic_version"))).scalar_one() == "0024_vin_admin_revisions"
            for table_name in ("vin_memberships", "vin_grants"):
                assert (await db.execute(text("SELECT revision FROM " + table_name))).scalar_one() == 1
            assert (await db.execute(text("SELECT count(*) FROM wf_durable_jobs WHERE id LIKE 'legacy-%'"))).scalar_one() == 2
            for user, role in [("admin", "PLATFORM_ADMIN"), ("alice", "VIN_USER")]:
                await db.execute(text("""INSERT INTO auth_users(id,tenant_id,email,username,password_hash,status,role,created_at,updated_at)
                    VALUES(:u,'test',:email,:u,'offline-password-hash','active',:r,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"""),
                    {"u": user, "email": user + "@test.invalid", "r": role})
                await db.execute(insert(t.accounts).values(user_id=user, tenant_id="test", eligible=True, revision=1))
        service = VinPlatformService(SimpleNamespace(_require_engine=lambda: engine), SimpleNamespace())
        await service.check_schema()
        await service.set_policy(await service.context("admin"), "role:VIN_USER",
            QuotaPolicy(daily_tokens=1000, monthly_tokens=2000, models=["fake"], max_concurrency=20, enabled=True))
        context = await service.context("alice")
        job = await service.jobs.enqueue(context, kind="delivery", key="migrated-job", payload={"body": "fixture"})
        claimed = await service.jobs.claim("fixture-worker")
        assert claimed.job_id == job.job_id and claimed.personal_user_id == "alice"
        await service.jobs.complete(claimed, "fixture-worker", {"delivered": True})
        async def reserve():
            try:
                return await service.quota.reserve(context, budget=600, model="fake", purpose="chat")
            except PlatformError as exc:
                assert exc.code == "QUOTA_EXCEEDED"
                return None
        results = await asyncio.gather(*[reserve() for _ in range(10)])
        assert len([r for r in results if r]) == 1
        ident = next(r for r in results if r)
        await asyncio.gather(*[service.quota.settle("test", ident, 200) for _ in range(5)])
        usage = await service.quota.usage(context)
        assert all(b["used"] == 200 and b["reserved"] == 0 for b in usage["buckets"])
        from agentscope.app.auth import AuthService
        from agentscope.app.deps import get_current_principal
        from fastapi import HTTPException
        async with AuthService(database_url=url, jwt_secret="offline-jwt-secret-" * 3, refresh_pepper="offline-refresh-" * 3,
            default_tenant_id="test") as auth:
            user = await auth.register_personal(email="resident@test.invalid", username="resident", password="offline-test-password")
            assert user.role == "VIN_USER" and user.area_id is None and user.domain_id is None
            async with engine.begin() as db:
                assert (await db.execute(text("SELECT count(*) FROM wf_manager_memberships WHERE manager_account_id=:u"), {"u": user.id})).scalar_one() == 0
                # Self-registration works at once on the default quota (PM 19/10).
                assert (await db.execute(text("SELECT eligible FROM vin_accounts WHERE user_id=:u"), {"u": user.id})).scalar_one() is True
            tokens = await auth.login(tenant_id="test", identity="resident", password="offline-test-password")
            request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(auth_service=auth, vin_platform_service=service)))
            principal = await get_current_principal(request, authorization="Bearer " + tokens.access_token)
            assert principal.user_id == user.id
            await auth.logout(tokens.refresh_token)
            with pytest.raises(HTTPException) as rejected:
                await get_current_principal(request, authorization="Bearer " + tokens.access_token)
            assert rejected.value.status_code == 401
    finally:
        await engine.dispose()
        assert name.startswith("vin_authority_test_") and len(name) == 51
        await control.execute('DROP DATABASE "' + name + '" WITH (FORCE)')
        await control.close()
