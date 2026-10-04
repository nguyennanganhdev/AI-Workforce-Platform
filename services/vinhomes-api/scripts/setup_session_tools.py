"""Give a local deployment the technical tools for Supervisor sessions.

    python scripts/setup_session_tools.py              # demo database (.local-v3-faker)
    python scripts/setup_session_tools.py --connected  # password-login database (.local-connected)
    python scripts/setup_session_tools.py --local DIR  # another local database: DIR/migration.env names it

1. Creates (or re-keys) the restricted database role the tool host signs in with and applies
   server/scripts/grant_technical_api_role.sql. The role can read and insert, never update or
   delete; the tool host refuses to start a call under a stronger role.
2. Registers the tool catalogue for the tenant (`mcp_servers` row `technical-tools` and one
   `mcp_tools` row per tool), so an agent's configuration can name the tools it is granted.
3. Writes <local>/technical-api.env (ignored by git): TECHNICAL_API_DATABASE_URL,
   TECHNICAL_API_TENANT_ID, TECHNICAL_TOOLS_SERVICE_TOKEN and TECHNICAL_CONNECTIONS_KEY (the key that
   seals the tokens of external MCP connections; kept across runs, or every stored token is lost).
   Nothing is printed from it.

No business data is seeded. Run again any time: every step is repeatable.
Then start the host with scripts/start_technical_tools.ps1.
"""
import asyncio
import base64
import json
import secrets
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import asyncpg

SERVICE = Path(__file__).resolve().parents[1]
ROOT = SERVICE.parents[1]
SERVER = "technical-tools"
DEMO_TENANT = "11111111-1111-5111-a111-111111111111"


def environment(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines()
                if line and not line.startswith("#") and "=" in line)


async def main(connected: bool, local: Path | None) -> None:
    local = local or SERVICE / (".local-connected" if connected else ".local-v3-faker")
    role = "vinhomes_connected_technical_api" if connected else "vinhomes_technical_api"
    owner_url = environment(local / "migration.env")["DATABASE_URL"]
    tenant = environment(SERVICE / ".env.connected")["VINHOMES_API_TENANT_ID"] if connected else DEMO_TENANT
    address = urlsplit(owner_url)
    if address.hostname not in ("localhost", "127.0.0.1"):
        raise RuntimeError("This setup is for a local database")
    path = local / "technical-api.env"
    existing = environment(path) if path.exists() else {}
    known = existing.get("TECHNICAL_API_DATABASE_URL")
    password = urlsplit(known).password if known else secrets.token_hex(24)
    token = existing.get("TECHNICAL_TOOLS_SERVICE_TOKEN") or secrets.token_urlsafe(32)
    sealing = existing.get("TECHNICAL_CONNECTIONS_KEY") or base64.b64encode(secrets.token_bytes(32)).decode()
    # Set by hand to reach a test MCP server over plain http on this machine; kept as it is.
    origins = existing.get("TECHNICAL_CONNECTIONS_HTTP_ORIGINS", "")
    # The catalogue comes from the tools themselves, so what is registered is what the host runs.
    bun = shutil.which("bun")  # on Windows the launcher is not found by its bare name
    if bun is None:
        raise RuntimeError("bun is required to read the tool catalogue")
    catalogue = json.loads(subprocess.run([bun, "scripts/print_technical_tools.ts"], cwd=ROOT / "server",
                                          check=True, capture_output=True, text=True, encoding="utf-8").stdout)
    grants = (ROOT / "server/scripts/grant_technical_api_role.sql").read_text(encoding="utf-8")
    db = await asyncpg.connect(owner_url)
    try:
        async with db.transaction():
            literal = "'" + password.replace("'", "''") + "'"
            verb = "ALTER" if await db.fetchval("select 1 from pg_roles where rolname=$1", role) else "CREATE"
            await db.execute(f"{verb} ROLE {role} LOGIN PASSWORD {literal} NOSUPERUSER NOBYPASSRLS")
            await db.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {role}")
            await db.execute(grants.replace("vinhomes_technical_api", role))
            await db.execute("select set_config('app.tenant_id',$1,true)", tenant)
            await db.execute("""
                insert into mcp_servers(id,title,vendor,url,provenance,tenant_id)
                values($1,'Công cụ kỹ thuật','Team Quang','internal:/internal/technical/v1','first-party',$2)
                on conflict (id) do update set title=excluded.title,updated_at=now()
            """, SERVER, tenant)
            for tool in catalogue:
                await db.execute("""
                    insert into mcp_tools(server_id,name,description,input_schema,effect,destructive,version,tenant_id)
                    values($1,$2,$3,cast($4 as jsonb),$5,false,$6,$7)
                    on conflict (server_id,name) do update set description=excluded.description,
                      input_schema=excluded.input_schema,effect=excluded.effect,version=excluded.version
                """, SERVER, tool["name"], tool["description"], json.dumps(tool["input_schema"]),
                    tool["side_effect"], tool["version"], tenant)
            # The gateway's own tools: the same registration the container upgrade runs.
            from vinhomes_api.tool_catalogue import register
            await register(db, tenant)
    finally:
        await db.close()
    url = urlunsplit((address.scheme, f"{role}:{quote(password)}@{address.hostname}:{address.port}", address.path, "", ""))
    path.write_text(f"TECHNICAL_API_DATABASE_URL={url}\nTECHNICAL_API_TENANT_ID={tenant}\n"
                    f"TECHNICAL_TOOLS_SERVICE_TOKEN={token}\nTECHNICAL_CONNECTIONS_KEY={sealing}\n"
                    + (f"TECHNICAL_CONNECTIONS_HTTP_ORIGINS={origins}\n" if origins else ""), encoding="utf-8")
    print(f"Technical tools ready for sessions: role {role}, {len(catalogue)} tools registered under '{SERVER}'. "
          f"Settings saved in {path} (keep it out of git).")


if __name__ == "__main__":
    arguments = sys.argv[1:]
    asyncio.run(main("--connected" in arguments,
                     Path(arguments[arguments.index("--local") + 1]) if "--local" in arguments else None))
