"""Provision the restricted Technical A2 role in the existing local faker database."""
import asyncio
from pathlib import Path
import secrets
from urllib.parse import quote, urlsplit, urlunsplit
import asyncpg

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "services/vinhomes-api/.local-v3-faker"

def environment(path):
    return dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines()
                if line and not line.startswith("#"))

async def main():
    owner_url = environment(LOCAL / "migration.env")["DATABASE_URL"]
    address = urlsplit(owner_url)
    if address.hostname not in ("localhost", "127.0.0.1") or address.path != "/vinhomes_v3":
        raise RuntimeError("Technical demo setup requires the local vinhomes_v3 database")
    path = LOCAL / "technical-api.env"
    existing = environment(path) if path.exists() else {}
    runtime_url = existing.get("TECHNICAL_API_DATABASE_URL")
    password = urlsplit(runtime_url).password if runtime_url else secrets.token_hex(24)
    db = await asyncpg.connect(owner_url)
    try:
        async with db.transaction():
            if await db.fetchval("select count(*) from tenants where id<>'11111111-1111-5111-a111-111111111111'"):
                raise RuntimeError("Refusing to seed a database containing another tenant")
            literal = "'" + password.replace("'", "''") + "'"
            if not await db.fetchval("select 1 from pg_roles where rolname='vinhomes_technical_api'"):
                await db.execute(f"CREATE ROLE vinhomes_technical_api LOGIN PASSWORD {literal} NOSUPERUSER NOBYPASSRLS")
            else:
                await db.execute(f"ALTER ROLE vinhomes_technical_api PASSWORD {literal} NOSUPERUSER NOBYPASSRLS")
            await db.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM vinhomes_technical_api")
            await db.execute((ROOT / "server/scripts/grant_technical_api_role.sql").read_text(encoding="utf-8"))
        await db.execute((ROOT / "server/scripts/seed_technical_api.sql").read_text(encoding="utf-8"))
    finally:
        await db.close()
    runtime_url = urlunsplit((address.scheme, f"vinhomes_technical_api:{quote(password)}@{address.hostname}:{address.port}", address.path, "", ""))
    path.write_text(f"TECHNICAL_API_DATABASE_URL={runtime_url}\nTECHNICAL_API_TENANT_ID=11111111-1111-5111-a111-111111111111\n", encoding="utf-8")
    print("Technical A2 demo role and database fixtures ready; credentials saved in ignored local configuration.")

if __name__ == "__main__":
    asyncio.run(main())
