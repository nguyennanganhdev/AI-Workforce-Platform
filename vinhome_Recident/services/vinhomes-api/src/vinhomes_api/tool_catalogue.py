"""Register the tools this API's gateway serves in a tenant's catalogue.

An agent's configuration can only name a tool that is registered, and the gateway only runs a
registered read tool. A release that adds, renames or retires a gateway tool therefore has to be
followed by this registration. It needs the database owner, which no running service is given:

    DATABASE_URL=<owner> VINHOMES_API_TENANT_ID=<tenant> python -m vinhomes_api.tool_catalogue

Repeatable. Tools of other tool hosts (the technical tools) are registered by their own host's
upgrade step and are not touched here.
"""
import asyncio
import json
import os

import asyncpg

from .v3_tool_gateway import catalogue


async def register(db: asyncpg.Connection, tenant: str) -> list[str]:
    """Upsert the gateway's tools and remove the ones it no longer serves. Runs in the caller's transaction."""
    tools = catalogue()
    for tool in tools:
        await db.execute("""insert into mcp_servers(id,title,vendor,url,provenance,tenant_id)
            values($1,$1,'first-party','internal:/internal/coordination/v1/tools','first-party',$2)
            on conflict(id) do nothing""", tool['server_id'], tenant)
        await db.execute("""insert into mcp_tools(server_id,name,description,input_schema,effect,destructive,version,tenant_id)
            values($1,$2,$3,cast($4 as jsonb),$5,false,$6,$7)
            on conflict(server_id,name) do update set description=excluded.description,
              input_schema=excluded.input_schema,effect=excluded.effect,version=excluded.version""",
            tool['server_id'], tool['name'], tool['description'], json.dumps(tool['input_schema']), tool['effect'], tool['version'], tenant)
    # A tool the gateway no longer serves must not stay grantable: an agent holding it is refused at the call.
    await db.execute("delete from mcp_tools where server_id=any($1::text[]) and tenant_id=$2 and not name=any($3::text[])",
                     list({t['server_id'] for t in tools}), tenant, [t['name'] for t in tools])
    return [t['name'] for t in tools]


async def main() -> None:
    url, tenant = os.environ.get("DATABASE_URL", ""), os.environ.get("VINHOMES_API_TENANT_ID", "")
    if not url or not tenant:
        raise SystemExit("DATABASE_URL (the database owner) and VINHOMES_API_TENANT_ID are required")
    db = await asyncpg.connect(url.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        async with db.transaction():
            await db.execute("select set_config('app.tenant_id',$1,true)", tenant)
            names = await register(db, tenant)
    finally:
        await db.close()
    print(json.dumps({"type": "gateway-tools-registered", "tools": names}))


if __name__ == "__main__":
    asyncio.run(main())
