"""Remove per-user plaintext copies of the platform key. Run inside the app container.

Usage: python remove_platform_key_copies.py dry|apply

- vin-platform-openai catalog entry also lists the embedding model
- role:AREA_MANAGER is granted the platform provider (BQL keeps working)
- role:VIN_USER and role:AREA_MANAGER get the default personal policy plus
  the embedding model (only when no policy exists for that role)
- every Redis record whose ``credential_id`` is a copy is repointed to
  vin-platform-openai (WATCH/MULTI per key, TTL kept)
- the copies are deleted
Prints counts and ids only, never secrets. Idempotent.
"""

import asyncio
import json
import os
import sys
from collections import Counter
from datetime import timedelta

from redis.exceptions import WatchError
from sqlalchemy import select, text

from agentscope.app.auth import AuthService
from agentscope.app.storage import RedisStorage
from agentscope.app.vin_platform import VinPlatformService
from agentscope.app.vin_platform import _tables as t
from agentscope.app.vin_platform._contracts import CatalogEntry, ResourceGrant
from agentscope.app.vin_platform._quota import default_personal_policy
from agentscope.app.vin_platform._resources import PLATFORM_PROVIDER_ID, is_platform_copy

MODE = sys.argv[1]
APPLY = MODE == "apply"
EMBEDDING = "text-embedding-3-small"


def repoint(node, ids, hits):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "credential_id" and value in ids:
                node[key] = PLATFORM_PROVIDER_ID
                hits.append(node.get("model"))
            else:
                repoint(value, ids, hits)
    elif isinstance(node, list):
        for item in node:
            repoint(item, ids, hits)


async def main():
    report = {"mode": MODE}
    async with RedisStorage(host=os.getenv("REDIS_HOST", "localhost"), port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")), password=os.getenv("REDIS_PASSWORD") or None) as storage, AuthService(
            database_url=os.environ["AGENTSCOPE_SQL_URL"], jwt_secret=os.environ["AUTH_JWT_SECRET"],
            refresh_pepper=os.environ["AUTH_REFRESH_PEPPER"], issuer=os.getenv("AUTH_JWT_ISSUER", "agentscope"),
            audience=os.getenv("AUTH_JWT_AUDIENCE", "agentscope-api"),
            default_tenant_id=os.getenv("AUTH_DEFAULT_TENANT_ID", "default"),
            access_ttl=timedelta(minutes=15), refresh_ttl=timedelta(days=30)) as auth:
        svc = VinPlatformService(auth, storage)
        async with svc.engine.begin() as db:
            admins = (await db.execute(text("SELECT id FROM auth_users WHERE role='PLATFORM_ADMIN' AND status='active'"))).scalars().all()
            users = (await db.execute(text("SELECT id FROM auth_users"))).scalars().all()
        assert len(admins) == 1, f"expected one platform admin, found {len(admins)}"
        admin = await svc.context(admins[0])

        # 1. Catalog entry lists the embedding model too.
        async with svc.engine.begin() as db:
            row = (await db.execute(select(t.catalog).where(t.catalog.c.tenant_id == admin.tenant_id,
                t.catalog.c.kind == "credential", t.catalog.c.resource_id == PLATFORM_PROVIDER_ID))).mappings().one()
        entry = CatalogEntry.model_validate(row["data"])
        report["catalog_models_before"] = entry.model_names
        if EMBEDDING not in entry.model_names and APPLY:
            await svc.publish_catalog(admin, entry.model_copy(update={
                "version": row["version"] + 1, "model_names": [*entry.model_names, EMBEDDING]}))
        catalog_id = row["id"]

        # 2. BQL accounts may execute the platform provider.
        async with svc.engine.begin() as db:
            granted = (await db.execute(select(t.grants.c.id).where(t.grants.c.catalog_id == catalog_id,
                t.grants.c.subject_kind == "role", t.grants.c.subject_id == "AREA_MANAGER",
                t.grants.c.active.is_(True)))).scalar_one_or_none()
        report["area_manager_grant_existed"] = bool(granted)
        if not granted and APPLY:
            await svc.grant(admin, ResourceGrant(catalog_id=catalog_id, subject_kind="role",
                subject_id="AREA_MANAGER", permissions=["view", "bind", "execute"]))

        # 3. Default policy (chat model first, then embedding) where none exists.
        base = default_personal_policy()
        policy = base.model_copy(update={"models": [*base.models, *([EMBEDDING] if EMBEDDING not in base.models else [])]})
        report["policy_models"] = policy.models
        for subject in ("role:VIN_USER", "role:AREA_MANAGER"):
            async with svc.engine.begin() as db:
                exists = (await db.execute(select(t.policies.c.subject).where(t.policies.c.tenant_id == admin.tenant_id,
                    t.policies.c.subject == subject))).scalar_one_or_none()
            report["policy_existed:" + subject] = bool(exists)
            if not exists and APPLY:
                await svc.set_policy(admin, subject, policy)

        # 4. Find the copies and repoint every reference.
        copies = {}
        for user in users:
            for record in await storage.list_credentials(user):
                if record.user_id == user and not record.data.get("secret_ref") and is_platform_copy(record):
                    copies[record.id] = user
        report["copies"] = len(copies)
        client = storage._client if hasattr(storage, "_client") else storage.client
        kinds, models, conflicts = Counter(), Counter(), 0
        async for key in client.scan_iter("*"):
            name = key.decode() if isinstance(key, bytes) else key
            if ":credential:" in name or await client.type(key) not in (b"string", "string"):
                continue
            raw = await client.get(key)
            text_value = raw.decode("utf-8", "ignore") if isinstance(raw, bytes) else (raw or "")
            if not any(ident in text_value for ident in copies):
                continue
            for _ in range(5):
                async with client.pipeline(transaction=True) as pipe:
                    try:
                        await pipe.watch(key)
                        current = await pipe.get(key)
                        value = json.loads(current)
                        hits = []
                        repoint(value, copies, hits)
                        if hits:
                            kind = name.split(":")[3] if name.startswith("agentscope:user:") else name.split(":")[1]
                            kinds[kind] += 1
                            models.update(str(m) for m in hits)
                            if APPLY:
                                pipe.multi()
                                pipe.set(key, json.dumps(value, ensure_ascii=False), keepttl=True)
                                await pipe.execute()
                        break
                    except WatchError:
                        continue
            else:
                conflicts += 1
        report["repointed"] = dict(kinds)
        report["models"] = dict(models)
        report["conflicts"] = conflicts

        # 5. Delete the copies.
        deleted = 0
        if APPLY and not conflicts:
            for ident, user in copies.items():
                deleted += bool(await storage.delete_credential(user, ident))
        report["deleted"] = deleted
        print(json.dumps(report, ensure_ascii=False))


asyncio.run(main())
