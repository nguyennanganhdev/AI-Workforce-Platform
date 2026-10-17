import pytest
from sqlalchemy import inspect

from vin_fixtures import authority as authority, seed_policy_catalog  # noqa: F401


@pytest.mark.asyncio
async def test_real_auth_columns_and_seeded_contract(authority):
    async with authority.engine.connect() as db:
        columns = await db.run_sync(lambda conn: inspect(conn).get_columns("auth_users"))
    actual = {c["name"]: c for c in columns}
    assert actual["domain_id"]["nullable"] and actual["area_id"]["nullable"]
    assert not actual["email"]["nullable"] and not actual["password_hash"]["nullable"]
    context = await seed_policy_catalog(authority)
    assert context.workspace_id == "personal:alice"
    assert (await authority.catalog(context, "credential", "execute"))[0]["model_names"] == ["test-model"]
    assert (await authority.quota.usage(context))["effective_limits"][0]["remaining"] == 100000
