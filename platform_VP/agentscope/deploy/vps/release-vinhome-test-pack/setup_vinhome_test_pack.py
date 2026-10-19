"""Vinhomes test pack: the Domain's read-only management MCP in the pack library. Run in the app container.

Usage: python setup_vinhome_test_pack.py dry|apply SOURCE_USER_ID

- copies the SOURCE user's "vinhomes" MCP record (Domain /mcp + control-plane
  header) to the platform admin under the same id, keeping only the
  read-only vh_management_* tools
- publishes it to the catalog and saves pack "vinhomes-test" (no sample
  agents; customers build their own agent on the pack's tools)
The Domain grant binding comes from VINHOMES_TEST_BINDING at run time.
Prints counts and ids only, never headers or tokens. Idempotent.
"""

import asyncio
import json
import os
import sys
from datetime import timedelta

from sqlalchemy import select, text

from agentscope.app.auth import AuthService
from agentscope.app.storage import RedisStorage
from agentscope.app.vin_platform import VinPlatformService
from agentscope.app.vin_platform import _tables as t
from agentscope.app.vin_platform._contracts import CatalogEntry, Pack
from agentscope.app.vin_platform._packs import save_pack

APPLY, SOURCE_USER = sys.argv[1] == "apply", sys.argv[2]
PACK_ID = "vinhomes-test"


async def main():
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
        assert len(admins) == 1, f"expected one platform admin, found {len(admins)}"
        admin_id = admins[0]
        admin = await svc.context(admin_id)

        source = next((m for m in await storage.list_mcps(SOURCE_USER) if m.client.name == "vinhomes"
                       and any(t["name"].startswith("vh_management_") for t in m.discovered_tools)), None)
        assert source is not None, "source user has no vinhomes MCP with management tools"
        tools = [d for d in source.discovered_tools if d["name"].startswith("vh_management_") and d.get("read_only") is True]
        names = [d["name"] for d in tools]
        report = {"mode": sys.argv[1], "mcp_id": source.id, "tools": names}

        copy = source.model_copy(deep=True, update={"user_id": admin_id, "discovered_tools": tools,
                                                     "display_name": "Vinhomes (thử nghiệm)"})
        copy.client.enable_tools = names
        copy.client.confirm_tools = None
        async with svc.engine.begin() as db:
            catalog_id = (await db.execute(select(t.catalog.c.id).where(t.catalog.c.tenant_id == admin.tenant_id,
                t.catalog.c.kind == "mcp", t.catalog.c.resource_id == source.id))).scalar_one_or_none()
            pack_exists = (await db.execute(select(t.packs.c.revision).where(t.packs.c.tenant_id == admin.tenant_id,
                t.packs.c.id == PACK_ID))).scalar_one_or_none()
        report.update(catalog_existed=bool(catalog_id), pack_revision=pack_exists)
        if APPLY:
            await storage.upsert_mcp(admin_id, copy)
            if catalog_id is None:
                catalog_id = await svc.publish_catalog(admin, CatalogEntry(kind="mcp", resource_id=source.id,
                    owner_id=admin_id, name="Vinhomes (thử nghiệm)",
                    description="Báo cáo chỉ đọc của khu demo Vinhomes: danh sách phiếu, tổng hợp, SLA, khối lượng việc, tra tài liệu.",
                    tool_names=names))
            await save_pack(svc, admin, PACK_ID, Pack(name="Vinhomes (thử nghiệm)",
                description="Gói thử: đọc báo cáo vận hành của một khu demo trên hệ thống Vinhomes. Chỉ để thử nghiệm, dữ liệu mô phỏng.",
                catalog_ids=[catalog_id]), expected_revision=pack_exists)
            report["catalog_id"] = catalog_id
        print(json.dumps(report, ensure_ascii=False))


asyncio.run(main())
